from bcs_golf_maps.normalise import build_courses

from .builders import bunker, complete_hole, green, hole, outline, pin, square, tee


def _course(features: list, index: int = 0) -> dict:
    return build_courses(features).courses[index]


def _eighteen(skip: set[int] = frozenset()) -> list:
    features = []
    for number in range(1, 19):
        if number not in skip:
            features += complete_hole(str(number), east=number * 100)
    return features


# MARK: - Status


def test_a_complete_course_is_ready() -> None:
    course = _course(_eighteen())
    assert course["status"] == "ready"
    assert course["holeCount"] == 18
    assert course["issues"] == []


def test_a_hole_with_no_green_makes_the_course_partial() -> None:
    features = _eighteen(skip={7})
    features.append(hole((700, 0), (700, 300), "7", par="4"))
    features.append(tee(700, 0))
    course = _course(features)
    assert course["status"] == "partial"
    assert course["issues"] == ["hole 7: no green"]


def test_a_hole_with_no_tee_makes_the_course_partial() -> None:
    features = _eighteen(skip={3})
    features += [hole((300, 0), (300, 300), "3"), green(300, 300)]
    course = _course(features)
    assert course["status"] == "partial"
    assert course["issues"] == ["hole 3: no tee"]


def test_a_gap_in_the_numbers_makes_the_course_partial() -> None:
    course = _course(_eighteen(skip={9}))
    assert course["status"] == "partial"
    assert course["issues"] == ["missing hole numbers: [9]"]


def test_repeated_numbers_make_the_course_partial() -> None:
    features = _eighteen() + complete_hole("4", east=2_000)
    course = _course(features)
    assert course["status"] == "partial"
    assert "repeated hole numbers: [4]" in course["issues"]


def test_a_hole_with_no_number_makes_the_course_partial() -> None:
    features = _eighteen(skip={18}) + [
        hole((1800, 0), (1800, 300), None),
        tee(1800, 0),
        green(1800, 300),
    ]
    course = _course(features)
    assert course["status"] == "partial"
    assert "a hole has no readable number" in course["issues"]


def test_a_missing_par_is_a_note_and_not_a_failure() -> None:
    features = []
    for number in range(1, 10):
        features += complete_hole(str(number), east=number * 100, par=None)
    course = _course(features)
    assert course["status"] == "ready"
    assert course["parComplete"] is False
    assert "hole 1: no par" in course["notes"]


def test_an_unusual_hole_count_is_a_note() -> None:
    features = []
    for number in range(1, 7):
        features += complete_hole(str(number), east=number * 100)
    course = _course(features)
    assert course["status"] == "ready"
    assert "unusual hole count: 6" in course["notes"]


def test_an_unnumbered_unclosed_green_is_ignored() -> None:
    features = _eighteen(skip={2})
    features += [
        hole((200, 0), (200, 300), "2"),
        tee(200, 0),
        square(200, 300, 12, {"golf": "green"}, closed=False),
    ]
    assert _course(features)["issues"] == ["hole 2: no green"]


# MARK: - Matching


def test_the_green_containing_the_end_of_the_hole_is_chosen() -> None:
    features = complete_hole("1", east=0) + [green(60, 300)]
    hole_one = _course(features)["holes"][0]
    assert abs(hole_one["green"]["centre"][1] - hole_one["line"][1][1]) < 0.0001


def test_two_holes_may_share_one_green() -> None:
    features = [
        hole((0, 0), (0, 300), "1"),
        hole((100, 0), (20, 300), "2"),
        tee(0, 0),
        tee(100, 0),
        green(10, 300, half=25),
    ]
    holes = _course(features)["holes"]
    assert holes[0]["green"] == holes[1]["green"] != None  # noqa: E711


def test_a_tee_belongs_to_the_nearest_hole_only() -> None:
    features = [
        hole((0, 0), (0, 300), "1"),
        hole((20, 0), (20, 300), "2"),
        green(0, 300),
        green(20, 300),
        tee(8, 0),
    ]
    holes = _course(features)["holes"]
    assert len(holes[0]["tees"]) == 1
    assert holes[1]["tees"] == []


def test_a_tee_too_far_from_every_hole_is_dropped() -> None:
    features = complete_hole("1", east=0) + [tee(0, -200)]
    assert len(_course(features)["holes"][0]["tees"]) == 1


def test_hazards_go_to_the_nearest_hole_and_far_ones_are_dropped() -> None:
    features = [
        hole((0, 0), (0, 300), "1"),
        hole((100, 0), (100, 300), "2"),
        tee(0, 0), green(0, 300), tee(100, 0), green(100, 300),
        bunker(10, 150),
        bunker(90, 150),
        bunker(50, 150),
    ]
    holes = _course(features)["holes"]
    assert len(holes[0]["hazards"]) == 1
    assert len(holes[1]["hazards"]) == 1


def test_a_pin_inside_the_green_is_attached() -> None:
    features = complete_hole("1", east=0) + [pin(2, 301)]
    assert _course(features)["holes"][0]["pin"] is not None


def test_a_pin_far_from_the_green_is_ignored() -> None:
    features = complete_hole("1", east=0) + [pin(200, 301)]
    assert _course(features)["holes"][0]["pin"] is None


# MARK: - Grouping


def test_two_courses_in_one_outline_are_told_apart_by_the_course_tag() -> None:
    features = [outline(0, 0, 3_000, "Big Club")]
    for number in range(1, 10):
        features += complete_hole(str(number), east=number * 100)
        features += complete_hole(str(number), east=number * 100, north=1_000, **{"golf:course:name": "Second"})
    courses = build_courses(features).courses
    assert {c["name"] for c in courses} == {"Big Club", "Second"}
    assert all(c["holeCount"] == 9 and c["status"] == "ready" for c in courses)


def test_the_smallest_containing_outline_wins() -> None:
    features = [outline(500, 150, 2_000, "Whole Estate"), outline(500, 150, 700, "The Course")]
    for number in range(1, 10):
        features += complete_hole(str(number), east=number * 100)
    courses = build_courses(features).courses
    assert [c["club"] for c in courses] == ["The Course"]


def test_an_outline_around_a_course_outline_is_not_a_course_of_its_own() -> None:
    features = [outline(500, 150, 2_000, "Whole Estate"), outline(500, 150, 700, "The Course")]
    for number in range(1, 10):
        features += complete_hole(str(number), east=number * 100)
    courses = build_courses(features).courses
    assert len(courses) == 1
    assert courses[0]["status"] == "ready"


def test_holes_outside_any_outline_are_grouped_by_tag_alone() -> None:
    features = []
    for number in range(1, 10):
        features += complete_hole(str(number), east=number * 100)
    course = _course(features)
    assert course["club"] is None
    assert course["name"] is None
    assert course["id"].startswith("h")


def test_a_named_outline_with_no_holes_is_listed_as_outline_only() -> None:
    result = build_courses([outline(0, 0, 500, "Pitch And Putt")])
    course = result.courses[0]
    assert course["status"] == "outline"
    assert course["holes"] == []
    assert course["issues"] == ["no holes mapped"]
    assert result.skipped == []


def test_an_unnamed_outline_with_no_holes_is_skipped_and_reported() -> None:
    outline_feature = outline(0, 0, 500)
    result = build_courses([outline_feature])
    assert result.courses == []
    assert result.skipped == [f"{outline_feature.ref}: unnamed outline with no holes"]


def test_an_outline_that_holds_holes_is_not_also_listed_as_outline_only() -> None:
    features = [outline(500, 150, 1_000, "Club")]
    for number in range(1, 10):
        features += complete_hole(str(number), east=number * 100)
    assert len(build_courses(features).courses) == 1


def test_no_features_gives_no_courses() -> None:
    result = build_courses([])
    assert result.courses == [] and result.skipped == []
