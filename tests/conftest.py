from pathlib import Path

import pytest

from golf_course_maps.normalise import BuildResult, build_courses
from golf_course_maps.overpass import load_overpass

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def mannings_heath() -> BuildResult:
    return build_courses(load_overpass(FIXTURES / "mannings_heath.overpass.json").features)


@pytest.fixture(scope="session")
def waterfall(mannings_heath: BuildResult) -> dict:
    """The 18 untagged holes: OSM doesn't name this course, so it takes the club's name."""
    return next(c for c in mannings_heath.courses if c["holeCount"] == 18)


@pytest.fixture(scope="session")
def kingfisher(mannings_heath: BuildResult) -> dict:
    return next(c for c in mannings_heath.courses if c["holeCount"] == 9)
