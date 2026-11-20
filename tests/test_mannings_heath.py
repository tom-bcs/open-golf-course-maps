"""Mannings Heath is a real 27-hole club: one 18-hole course with no course
tag and a 9-hole course tagged "Kingfisher Course", in separate outlines."""

import json
import math

from shapely.geometry import Polygon

from bcs_golf_maps.geo import METRES_PER_YARD, Projector
from bcs_golf_maps.normalise import ATTRIBUTION, BuildResult
from bcs_golf_maps.publish import build_index, render_report, write_output

WATERFALL_PARS = [4, 4, 4, 4, 3, 4, 4, 5, 4, 3, 4, 4, 5, 3, 4, 4, 5, 4]


def test_two_courses_and_one_unnamed_outline_skipped(mannings_heath: BuildResult) -> None:
    assert sorted(c["holeCount"] for c in mannings_heath.courses) == [9, 18]
    assert mannings_heath.skipped == ["way/1033352014: unnamed outline with no holes"]


def test_course_names(waterfall: dict, kingfisher: dict) -> None:
    assert waterfall["name"] == "Mannings Heath Golf Club"
    assert kingfisher["name"] == "Kingfisher Course"
    assert kingfisher["club"] == "Mannings Heath Golf Course"
    assert waterfall["id"] == "w386407226"
    assert kingfisher["id"] == "w424340558-kingfisher-course"


def test_both_courses_are_ready(waterfall: dict, kingfisher: dict) -> None:
    for course in (waterfall, kingfisher):
        assert course["status"] == "ready"
        assert course["issues"] == []
        assert [h["number"] for h in course["holes"]] == list(range(1, course["holeCount"] + 1))


def test_pars_come_from_osm_and_a_missing_par_is_a_note_not_a_failure(waterfall: dict, kingfisher: dict) -> None:
    assert waterfall["pars"] == WATERFALL_PARS
    assert waterfall["parComplete"] is True
    assert kingfisher["pars"] == [None] * 9
    assert kingfisher["parComplete"] is False
    assert "hole 1: no par" in kingfisher["notes"]


def test_every_hole_has_a_tee_and_a_green_with_its_centre_inside(waterfall: dict, kingfisher: dict) -> None:
    for course in (waterfall, kingfisher):
        for hole in course["holes"]:
            assert hole["tees"], hole["number"]
            green = hole["green"]
            assert green is not None, hole["number"]
            projector = Projector(tuple(green["polygon"][0]))
            polygon = Polygon([projector.xy(tuple(p)) for p in green["polygon"]])
            assert polygon.contains(projector.point(tuple(green["centre"])))


def test_hole_five_length_matches_the_distance_walked_in_the_gpx(waterfall: dict) -> None:
    """The GPX walk of the 5th is 162 m (177 yd) tee to pin."""
    line = next(h for h in waterfall["holes"] if h["number"] == 5)["line"]
    projector = Projector(tuple(line[0]))
    metres = projector.line([tuple(p) for p in line]).length
    assert math.isclose(metres / METRES_PER_YARD, 177, abs_tol=15)


def test_pins_are_found_for_all_18_holes(waterfall: dict, kingfisher: dict) -> None:
    assert all(h["pin"] is not None for h in waterfall["holes"])
    assert all(h["pin"] is None for h in kingfisher["holes"])


def test_each_hazard_belongs_to_one_hole_only(waterfall: dict, kingfisher: dict) -> None:
    seen: set[tuple] = set()
    for course in (waterfall, kingfisher):
        for hole in course["holes"]:
            for hazard in hole["hazards"]:
                key = tuple(map(tuple, hazard["polygon"]))
                assert key not in seen
                seen.add(key)
                assert hazard["kind"] == "bunker"
    assert len(seen) > 50


def test_each_tee_belongs_to_one_hole_only(waterfall: dict, kingfisher: dict) -> None:
    seen: set[tuple] = set()
    for course in (waterfall, kingfisher):
        for hole in course["holes"]:
            for tee in hole["tees"]:
                key = tuple(map(tuple, tee))
                assert key not in seen
                seen.add(key)


def test_polygons_have_no_repeated_closing_point_and_coordinates_are_rounded(waterfall: dict) -> None:
    green = waterfall["holes"][0]["green"]["polygon"]
    assert green[0] != green[-1]
    for lat, lon in green:
        assert round(lat, 7) == lat and round(lon, 7) == lon


def test_every_course_carries_the_attribution(mannings_heath: BuildResult) -> None:
    assert all(c["attribution"] == ATTRIBUTION for c in mannings_heath.courses)


def test_output_files_round_trip(mannings_heath: BuildResult, tmp_path) -> None:
    write_output(mannings_heath, tmp_path, data_timestamp="2026-11-20T09:39:35Z")
    index = json.loads((tmp_path / "index.json").read_text())
    assert index["courseCount"] == 2
    assert index["attribution"] == ATTRIBUTION
    for entry in index["courses"]:
        course = json.loads((tmp_path / entry["file"]).read_text())
        assert course["id"] == entry["id"]
        assert course["holeCount"] == entry["holeCount"] == len(course["holes"])
    assert "ready: 2" in (tmp_path / "report.md").read_text()


def test_output_is_byte_for_byte_repeatable(mannings_heath: BuildResult, tmp_path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    write_output(mannings_heath, first)
    write_output(mannings_heath, second)
    for path in first.rglob("*.json"):
        assert path.read_bytes() == (second / path.relative_to(first)).read_bytes()


def test_report_and_index_agree_on_counts(mannings_heath: BuildResult) -> None:
    index = build_index(mannings_heath, None)
    assert index["courseCount"] == len(index["courses"]) == 2
    assert "Skipped: 1" in render_report(mannings_heath, None)
