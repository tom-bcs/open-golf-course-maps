"""The published files must match schema/*.schema.json and docs/schema.md.

The schemas are strict (no unknown fields), so adding a field to the output
fails here until the schema and the docs describe it.
"""

import copy
import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from shapely.geometry import Point, Polygon

from golf_course_maps import cli
from golf_course_maps.geo import Projector
from golf_course_maps.publish import SCHEMA_DIR, write_output

FIXTURE = Path(__file__).parent / "fixtures" / "mannings_heath.overpass.json"
LOCAL_BUILD = Path(__file__).parent.parent / "out" / "europe" / "great-britain"


def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text()))


@pytest.fixture(scope="module")
def built(mannings_heath, tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("site")
    write_output(mannings_heath, out, "europe/great-britain", "2026-11-20T09:39:35Z")
    return out


@pytest.fixture(scope="module")
def courses(built: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((built / "europe/great-britain/courses").glob("*.json"))]


# MARK: - The schemas themselves


@pytest.mark.parametrize("name", ["course", "index", "regions"])
def test_each_schema_is_itself_valid(name: str) -> None:
    Draft202012Validator.check_schema(json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text()))


# MARK: - Real output matches


def test_every_course_file_matches_the_course_schema(courses: list[dict]) -> None:
    assert courses
    for course in courses:
        _validator("course").validate(course)


def test_the_index_and_regions_files_match_their_schemas(built: Path) -> None:
    _validator("index").validate(json.loads((built / "europe/great-britain/index.json").read_text()))
    _validator("regions").validate(json.loads((built / "regions.json").read_text()))


@pytest.mark.skipif(
    not (os.environ.get("FULL_BUILD_CHECK") and LOCAL_BUILD.exists()),
    reason="slow (about 12 minutes): set FULL_BUILD_CHECK=1 after a local build-all",
)
def test_a_full_local_build_matches_the_schemas() -> None:
    """Checks every real GB course in out/, not just the fixture."""
    validator = _validator("course")
    for path in (LOCAL_BUILD / "courses").glob("*.json"):
        validator.validate(json.loads(path.read_text()))
    _validator("index").validate(json.loads((LOCAL_BUILD / "index.json").read_text()))


# MARK: - What the schema can't say


def _holes(course: dict):
    return course["holes"]


def test_hole_count_pars_and_bounds_agree_with_the_holes(courses: list[dict]) -> None:
    for course in courses:
        assert course["holeCount"] == len(_holes(course))
        assert course["pars"] == [h["par"] for h in _holes(course)]
        assert course["parComplete"] == all(h["par"] is not None for h in _holes(course))
        south, west, north, east = course["bounds"]
        assert south <= north and west <= east
        assert south <= course["centre"][0] <= north and west <= course["centre"][1] <= east


def test_status_means_what_the_docs_say(courses: list[dict]) -> None:
    for course in courses:
        holes = _holes(course)
        if course["status"] == "ready":
            assert course["issues"] == []
            assert [h["number"] for h in holes] == list(range(1, len(holes) + 1))
            assert len(holes) in (9, 18)
            assert all(h["green"] is not None for h in holes)
        elif course["status"] == "partial":
            assert course["issues"]
        else:
            assert holes == [] and course["holeCount"] == 0


def test_rings_do_not_repeat_their_closing_point(courses: list[dict]) -> None:
    for course in courses:
        for hole in _holes(course):
            rings = list(hole["tees"]) + [h["polygon"] for h in hole["hazards"]]
            if hole["green"]:
                rings.append(hole["green"]["polygon"])
            for ring in rings:
                assert ring[0] != ring[-1]


def test_the_green_centre_is_inside_the_green(courses: list[dict]) -> None:
    for course in courses:
        for hole in _holes(course):
            green = hole["green"]
            if not green:
                continue
            projector = Projector(tuple(green["polygon"][0]))
            polygon = Polygon([projector.xy(tuple(p)) for p in green["polygon"]])
            assert polygon.buffer(0.5).contains(Point(projector.xy(tuple(green["centre"]))))


def test_the_hole_line_runs_from_the_tee_end_to_the_green(courses: list[dict]) -> None:
    """The green's centre is nearer the line's last point than its first."""
    for course in courses:
        for hole in _holes(course):
            if not hole["green"]:
                continue
            projector = Projector(tuple(hole["line"][0]))
            centre = Point(projector.xy(tuple(hole["green"]["centre"])))
            first = Point(projector.xy(tuple(hole["line"][0])))
            last = Point(projector.xy(tuple(hole["line"][-1])))
            assert centre.distance(last) < centre.distance(first)


def test_file_paths_in_the_index_exist(built: Path) -> None:
    index = json.loads((built / "europe/great-britain/index.json").read_text())
    for entry in index["courses"]:
        assert (built / "europe/great-britain" / entry["file"]).exists()


# MARK: - Bad data is rejected


def _broken(course: dict, mutate) -> dict:
    copy_ = copy.deepcopy(course)
    mutate(copy_)
    return copy_


@pytest.mark.parametrize("mutate", [
    lambda c: c.update(status="great"),
    lambda c: c.update(schema=2),
    lambda c: c.update(surprise=1),
    lambda c: c.pop("attribution"),
    lambda c: c["centre"].append(0),
    lambda c: c.update(centre=[91, 0]),
    lambda c: c["holes"][0]["line"].pop(),
    lambda c: c["holes"][0]["green"].update(centre=[1]),
    lambda c: c["holes"][0]["hazards"].append({"kind": "tree", "polygon": c["holes"][0]["green"]["polygon"]}),
    lambda c: c["holes"][0].update(par=9),
    lambda c: c["holes"][0].update(green="yes"),
    lambda c: c["holes"][0]["tees"].append([[51, 0], [51, 1]]),
], ids=["status", "schema", "extra field", "missing field", "3 coords", "latitude", "short line",
        "bad centre", "bad hazard kind", "bad par", "bad green", "2-point ring"])
def test_the_schema_rejects_bad_courses(courses: list[dict], mutate) -> None:
    good = next(c for c in courses if c["status"] == "ready")
    _validator("course").validate(good)
    assert list(_validator("course").iter_errors(_broken(good, mutate)))


# MARK: - Publishing the schemas


def test_build_all_publishes_the_schemas_where_their_ids_point(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    regions_file = tmp_path / "regions.txt"
    regions_file.write_text("europe/great-britain\n")
    monkeypatch.setattr(cli, "download", lambda region, data_dir, refresh: FIXTURE)
    out = tmp_path / "out"
    assert cli.main(["build-all", str(regions_file), str(tmp_path), str(out)]) == 0
    for name in ("course", "index", "regions"):
        published = json.loads((out / "schema" / f"{name}.schema.json").read_text())
        assert published["$id"].endswith(f"/schema/{name}.schema.json")
