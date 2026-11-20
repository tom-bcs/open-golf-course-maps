"""Groups holes into playable courses and builds each course's map.

The rules, in the order they apply:

1. A hole belongs to the smallest `leisure=golf_course` outline that contains
   its first point (the tee end).
2. A playable course is the holes sharing one outline and one
   `golf:course:name`. A club with two courses in one outline is told apart by
   that tag; a club with an outline per course needs no tag.
3. Each hole claims what is near it: its green (the one containing, or
   nearest, its last point), the tee boxes nearest its first point, and the
   hazards nearest its line. Tees, hazards and pins belong to one hole only,
   the nearest. A green can be shared by two holes.
4. A course is `ready` when every hole has a green and the hole numbers run
   1..N with no gaps or repeats, with N of 9 or 18 (a lone hole or a handful
   is a stray fragment, not a course). Anything less is `partial`. An outline with
   no holes is `outline`. A missing tee polygon is only a note: the first
   point of the hole line is the tee, and a fifth of real holes have no tee
   mapped, which would fail almost every course.
5. Holes in no outline are grouped by proximity. So is a group with repeated
   hole numbers, when splitting it removes every repeat (a 27-hole club in
   one outline, with no course tag).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from shapely import STRtree
from shapely.geometry import LineString, Point, Polygon, box

from .geo import Projector
from .model import Feature, LatLon

SCHEMA_VERSION = 1
ATTRIBUTION = "© OpenStreetMap contributors (ODbL 1.0)"

TEE_MAX_METRES = 40
GREEN_MAX_METRES = 30
HAZARD_MAX_METRES = 40
PIN_MAX_METRES = 5
# How far past a hole's own extent to look for its tees, green and hazards.
# 0.001 degrees is about 110 m north-south and 60 to 70 m east-west in
# Britain and Ireland, comfortably past the 40 m limits above.
SEARCH_PAD_DEGREES = 0.001
COORD_DECIMALS = 7
# Holes whose lines come within this of each other (in degrees, roughly
# 220 m north-south and 140 m east-west) count as the same course.
CLUSTER_GAP_DEGREES = 0.002

HAZARD_KINDS = {
    "bunker": "bunker",
    "water_hazard": "water",
    "lateral_water_hazard": "lateral_water",
}


@dataclass
class BuildResult:
    courses: list[dict[str, Any]]
    skipped: list[str]


# MARK: - Spatial lookup


def _envelope(feature: Feature):
    if len(feature.coords) == 1:
        lat, lon = feature.coords[0]
        return Point(lon, lat)
    lats = [c[0] for c in feature.coords]
    lons = [c[1] for c in feature.coords]
    return box(min(lons), min(lats), max(lons), max(lats))


class _Layer:
    def __init__(self, items: list[Feature]) -> None:
        self.items = items
        self._tree = STRtree([_envelope(f) for f in items]) if items else None

    def near(self, bounds: tuple[float, float, float, float]) -> list[Feature]:
        if self._tree is None:
            return []
        return [self.items[i] for i in self._tree.query(box(*bounds))]


@dataclass
class _Layers:
    greens: _Layer
    tees: _Layer
    hazards: _Layer
    pins: _Layer


def _build_layers(features: list[Feature]) -> _Layers:
    def closed(kind: str) -> list[Feature]:
        return [f for f in features if f.osm_type == "way" and f.golf == kind and f.is_closed]

    return _Layers(
        greens=_Layer(closed("green")),
        tees=_Layer(closed("tee")),
        hazards=_Layer([f for kind in HAZARD_KINDS for f in closed(kind)]),
        pins=_Layer([f for f in features if f.osm_type == "node" and f.golf == "pin"]),
    )


# MARK: - What is near each hole


@dataclass
class _Survey:
    green: tuple[Feature, float] | None
    tees: list[tuple[Feature, float]]
    hazards: list[tuple[Feature, float]]
    pins: list[tuple[Feature, float]]


def _survey_hole(hole: Feature, layers: _Layers) -> _Survey:
    projector = Projector(hole.coords[0])
    line = projector.line(hole.coords)
    start, end = Point(line.coords[0]), Point(line.coords[-1])
    lats = [c[0] for c in hole.coords]
    lons = [c[1] for c in hole.coords]
    bounds = (
        min(lons) - SEARCH_PAD_DEGREES,
        min(lats) - SEARCH_PAD_DEGREES,
        max(lons) + SEARCH_PAD_DEGREES,
        max(lats) + SEARCH_PAD_DEGREES,
    )

    green: tuple[Feature, float] | None = None
    green_polygon = None
    for candidate in layers.greens.near(bounds):
        polygon = projector.polygon(candidate.coords)
        distance = polygon.distance(end)
        if distance <= GREEN_MAX_METRES and (green is None or distance < green[1]):
            green, green_polygon = (candidate, distance), polygon

    tees = []
    for candidate in layers.tees.near(bounds):
        distance = projector.polygon(candidate.coords).distance(start)
        if distance <= TEE_MAX_METRES:
            tees.append((candidate, distance))

    hazards = []
    for candidate in layers.hazards.near(bounds):
        distance = projector.polygon(candidate.coords).distance(line)
        if distance <= HAZARD_MAX_METRES:
            hazards.append((candidate, distance))

    pins = []
    if green_polygon is not None:
        for candidate in layers.pins.near(bounds):
            point = projector.point(candidate.coords[0])
            if point.distance(green_polygon) <= PIN_MAX_METRES:
                pins.append((candidate, point.distance(end)))

    return _Survey(green, tees, hazards, pins)


def _nearest_claims(
    surveys: dict[str, _Survey], pick: str
) -> dict[str, list[Feature]]:
    """Gives each tee, hazard or pin to the hole it is nearest to."""
    best: dict[str, tuple[float, str, Feature]] = {}
    for hole_ref, survey in surveys.items():
        for feature, distance in getattr(survey, pick):
            if feature.ref not in best or distance < best[feature.ref][0]:
                best[feature.ref] = (distance, hole_ref, feature)
    claimed: dict[str, list[Feature]] = defaultdict(list)
    for _, hole_ref, feature in best.values():
        claimed[hole_ref].append(feature)
    return claimed


# MARK: - Grouping holes into courses


@dataclass
class _Group:
    outline: Feature | None
    course_tag: str | None
    holes: list[Feature]
    # Set when proximity split one outline's holes into several courses, so
    # their ids can't collide.
    split: bool = False


def _number(hole: Feature) -> int | None:
    return _int_tag(hole, "ref", 1, 99)


def _has_repeats(holes: list[Feature]) -> bool:
    numbers = [n for n in map(_number, holes) if n is not None]
    return len(numbers) != len(set(numbers))


def _cluster(holes: list[Feature]) -> list[list[Feature]]:
    """Joins holes whose lines pass within CLUSTER_GAP_DEGREES of each other."""
    lines = [LineString([(lon, lat) for lat, lon in h.coords]) for h in holes]
    tree = STRtree(lines)
    parent = list(range(len(holes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, line in enumerate(lines):
        for j in tree.query(line.buffer(CLUSTER_GAP_DEGREES), predicate="intersects"):
            parent[find(int(j))] = find(i)
    clusters: dict[int, list[Feature]] = defaultdict(list)
    for i, hole in enumerate(holes):
        clusters[find(i)].append(hole)
    return list(clusters.values())


def _group_holes(holes: list[Feature], outlines: list[Feature]) -> tuple[list[_Group], set[str]]:
    """Returns the groups, and every outline that contains at least one hole.

    The second is wider than the groups' own outlines: an estate outline
    around a course outline holds holes without being any hole's smallest
    outline, and mustn't then be listed as a course of its own.
    """
    polygons = []
    for outline in outlines:
        polygon = Polygon([(lon, lat) for lat, lon in outline.coords])
        polygons.append(polygon if polygon.is_valid else polygon.buffer(0))
    tree = STRtree(polygons) if polygons else None

    keyed: dict[tuple[str | None, str | None], _Group] = {}
    containing: set[str] = set()
    for hole in holes:
        outline = None
        if tree is not None:
            lat, lon = hole.coords[0]
            hits = tree.query(Point(lon, lat), predicate="within")
            if len(hits):
                outline = outlines[min(hits, key=lambda i: polygons[i].area)]
                containing.update(outlines[i].ref for i in hits)
        tag = hole.tags.get("golf:course:name")
        key = (outline.ref if outline else None, tag)
        keyed.setdefault(key, _Group(outline, tag, [])).holes.append(hole)

    groups: list[_Group] = []
    for group in keyed.values():
        if group.outline is None:
            groups += [_Group(None, group.course_tag, cluster) for cluster in _cluster(group.holes)]
            continue
        if _has_repeats(group.holes):
            clusters = _cluster(group.holes)
            if len(clusters) > 1 and not any(_has_repeats(c) for c in clusters):
                groups += [_Group(group.outline, group.course_tag, c, split=True) for c in clusters]
                continue
        groups.append(group)
    return groups, containing


# MARK: - Output


def _round(point: LatLon) -> list[float]:
    return [round(point[0], COORD_DECIMALS), round(point[1], COORD_DECIMALS)]


def _ring(feature: Feature) -> list[list[float]]:
    """A polygon's vertices without the repeated closing point."""
    return [_round(p) for p in feature.coords[:-1]]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _int_tag(feature: Feature, key: str, low: int, high: int) -> int | None:
    value = feature.tags.get(key, "").strip()
    if re.fullmatch(r"\d{1,2}", value) and low <= int(value) <= high:
        return int(value)
    return None


def _green_centre(green: Feature) -> list[float]:
    projector = Projector(green.coords[0])
    centroid = projector.polygon(green.coords).centroid
    return _round(projector.latlon(centroid.x, centroid.y))


def _bounds(points: list[LatLon]) -> list[float]:
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return [round(v, COORD_DECIMALS) for v in (min(lats), min(lons), max(lats), max(lons))]


def _centre_of(bounds: list[float]) -> list[float]:
    return [round((bounds[0] + bounds[2]) / 2, COORD_DECIMALS), round((bounds[1] + bounds[3]) / 2, COORD_DECIMALS)]


def _hole_record(
    hole: Feature,
    green: Feature | None,
    tees: list[Feature],
    hazards: list[Feature],
    pins: list[Feature],
) -> dict[str, Any]:
    pin = None
    if pins:
        projector = Projector(hole.coords[0])
        end = projector.point(hole.coords[-1])
        pin = _round(min(pins, key=lambda p: projector.point(p.coords[0]).distance(end)).coords[0])
    return {
        "number": _int_tag(hole, "ref", 1, 99),
        "par": _int_tag(hole, "par", 2, 7),
        "name": hole.tags.get("name"),
        "line": [_round(p) for p in hole.coords],
        "tees": [_ring(t) for t in sorted(tees, key=lambda t: t.osm_id)],
        "green": {"polygon": _ring(green), "centre": _green_centre(green)} if green else None,
        "pin": pin,
        "hazards": [
            {"kind": HAZARD_KINDS[h.golf or ""], "polygon": _ring(h)}
            for h in sorted(hazards, key=lambda h: h.osm_id)
        ],
    }


def _hole_numbers(holes: list[dict[str, Any]], missing: str) -> str:
    """'3, 7' for the holes whose `missing` key is empty, plus unnumbered ones."""
    numbers = [h["number"] for h in holes if not h[missing] and h["number"] is not None]
    unnumbered = sum(1 for h in holes if not h[missing] and h["number"] is None)
    parts = [str(n) for n in sorted(numbers)]
    if unnumbered:
        parts.append(f"{unnumbered} unnumbered")
    return ", ".join(parts)


def _check_course(holes: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Returns (issues that stop a course being ready, notes that don't)."""
    issues: list[str] = []
    notes: list[str] = []
    numbers = [h["number"] for h in holes if h["number"] is not None]
    if len(numbers) != len(holes):
        issues.append(f"{len(holes) - len(numbers)} holes have no readable number")
    repeats = sorted({n for n in numbers if numbers.count(n) > 1})
    if repeats:
        issues.append(f"repeated hole numbers: {repeats}")
    if numbers:
        missing = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
        if missing:
            issues.append(f"missing hole numbers: {missing}")
        if max(numbers) not in (9, 18):
            issues.append(f"unusual hole count: {max(numbers)}")
    for key, label, bucket in (("green", "no green", issues), ("tees", "no tee", notes), ("par", "no par", notes)):
        listed = _hole_numbers(holes, key)
        if listed:
            bucket.append(f"{label}: holes {listed}")
    return issues, notes


def _course_record(group: _Group, holes: list[dict[str, Any]]) -> dict[str, Any]:
    outline, tag = group.outline, group.course_tag
    holes = sorted(holes, key=lambda h: (h["number"] is None, h["number"] or 0))
    issues, notes = _check_course(holes)

    points = [tuple(p) for h in holes for p in h["line"]]
    for hole in holes:
        if hole["green"]:
            points += [tuple(p) for p in hole["green"]["polygon"]]
    bounds = _bounds(points)  # type: ignore[arg-type]

    course_id = f"w{outline.osm_id}" if outline else f"h{min(h.osm_id for h in group.holes)}"
    if tag:
        course_id += f"-{_slug(tag)}"
    if group.split:
        course_id += f"-h{min(h.osm_id for h in group.holes)}"

    return {
        "schema": SCHEMA_VERSION,
        "attribution": ATTRIBUTION,
        "id": course_id,
        "name": tag or (outline.tags.get("name") if outline else None),
        "club": outline.tags.get("name") if outline else None,
        "status": "partial" if issues else "ready",
        "issues": issues,
        "notes": notes,
        "holeCount": len(holes),
        "pars": [h["par"] for h in holes],
        "parComplete": all(h["par"] is not None for h in holes),
        "centre": _centre_of(bounds),
        "bounds": bounds,
        "holes": holes,
    }


def _outline_record(outline: Feature) -> dict[str, Any]:
    bounds = _bounds(list(outline.coords))
    return {
        "schema": SCHEMA_VERSION,
        "attribution": ATTRIBUTION,
        "id": f"w{outline.osm_id}",
        "name": outline.tags.get("name"),
        "club": outline.tags.get("name"),
        "status": "outline",
        "issues": ["no holes mapped"],
        "notes": [],
        "holeCount": 0,
        "pars": [],
        "parComplete": False,
        "centre": _centre_of(bounds),
        "bounds": bounds,
        "holes": [],
    }


# MARK: - Entry point


def build_courses(features: list[Feature]) -> BuildResult:
    outlines = [
        f for f in features
        if f.osm_type == "way" and f.tags.get("leisure") == "golf_course" and f.is_closed
    ]
    holes = [f for f in features if f.osm_type == "way" and f.golf == "hole" and len(f.coords) >= 2]

    layers = _build_layers(features)
    surveys = {hole.ref: _survey_hole(hole, layers) for hole in holes}
    tees = _nearest_claims(surveys, "tees")
    hazards = _nearest_claims(surveys, "hazards")
    pins = _nearest_claims(surveys, "pins")

    courses: list[dict[str, Any]] = []
    groups, outlines_with_holes = _group_holes(holes, outlines)
    for group in groups:
        records = [
            _hole_record(
                hole,
                surveys[hole.ref].green[0] if surveys[hole.ref].green else None,
                tees[hole.ref],
                hazards[hole.ref],
                pins[hole.ref],
            )
            for hole in group.holes
        ]
        courses.append(_course_record(group, records))

    skipped: list[str] = []
    for outline in outlines:
        if outline.ref in outlines_with_holes:
            continue
        if outline.tags.get("name"):
            courses.append(_outline_record(outline))
        else:
            skipped.append(f"{outline.ref}: unnamed outline with no holes")

    courses.sort(key=lambda c: (c["name"] or "", c["id"]))
    return BuildResult(courses, skipped)
