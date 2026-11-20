"""Tiny hand-made courses, laid out in metres east and north of one origin."""

from __future__ import annotations

from golf_course_maps.geo import Projector
from golf_course_maps.model import Feature

ORIGIN = (51.0, -0.27)
_projector = Projector(ORIGIN)
_next_id = 0


def _id() -> int:
    global _next_id
    _next_id += 1
    return _next_id


def at(east: float, north: float) -> tuple[float, float]:
    return _projector.latlon(east, north)


def square(east: float, north: float, half: float, tags: dict[str, str], closed: bool = True) -> Feature:
    corners = [(-half, -half), (half, -half), (half, half), (-half, half)]
    coords = [at(east + dx, north + dy) for dx, dy in corners]
    if closed:
        coords.append(coords[0])
    return Feature("way", _id(), tags, tuple(coords))


def hole(start: tuple[float, float], end: tuple[float, float], ref: str | None, **tags: str) -> Feature:
    all_tags = {"golf": "hole", **tags}
    if ref is not None:
        all_tags["ref"] = ref
    return Feature("way", _id(), all_tags, (at(*start), at(*end)))


def green(east: float, north: float, half: float = 12) -> Feature:
    return square(east, north, half, {"golf": "green"})


def tee(east: float, north: float, half: float = 4) -> Feature:
    return square(east, north, half, {"golf": "tee"})


def bunker(east: float, north: float) -> Feature:
    return square(east, north, 3, {"golf": "bunker"})


def pin(east: float, north: float) -> Feature:
    return Feature("node", _id(), {"golf": "pin"}, (at(east, north),))


def outline(east: float, north: float, half: float, name: str | None = None) -> Feature:
    tags = {"leisure": "golf_course"}
    if name:
        tags["name"] = name
    return square(east, north, half, tags)


def complete_hole(ref: str, east: float, north: float = 0, par: str | None = "4", **tags: str) -> list[Feature]:
    """A 300 m hole running north from (east, north), with a tee and a green."""
    extra = {"par": par} if par else {}
    return [
        hole((east, north), (east, north + 300), ref, **extra, **tags),
        tee(east, north),
        green(east, north + 300),
    ]


def as_relation(feature: Feature, relation_id: int, part: int = 0) -> Feature:
    """The same ring, as one outer ring of a multipolygon relation."""
    return Feature("relation", relation_id, feature.tags, feature.coords, part)
