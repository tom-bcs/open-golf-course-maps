import io
import json
from pathlib import Path

import pytest

from golf_course_maps import cli, fetch
from golf_course_maps.publish import build_regions, render_site_index

FIXTURE = Path(__file__).parent / "fixtures" / "mannings_heath.overpass.json"


# MARK: - The regions list


def test_parse_regions_ignores_comments_blank_lines_and_repeats() -> None:
    text = "# header\n\neurope/great-britain  # the island\neurope/ireland-and-northern-ireland\neurope/great-britain\n"
    assert fetch.parse_regions(text) == ["europe/great-britain", "europe/ireland-and-northern-ireland"]


@pytest.mark.parametrize("bad", ["../etc/passwd", "/europe/great-britain", "Europe/Great-Britain", "europe//uk", "europe/gb.pbf", "http://example.com/x"])
def test_parse_regions_rejects_anything_that_is_not_a_geofabrik_path(bad: str) -> None:
    with pytest.raises(ValueError, match="not a Geofabrik path"):
        fetch.parse_regions(f"europe/great-britain\n{bad}\n")


def test_the_shipped_regions_file_parses() -> None:
    regions = fetch.parse_regions((Path(__file__).parent.parent / "regions.txt").read_text())
    assert "europe/great-britain" in regions


# MARK: - Downloading


class _Response(io.BytesIO):
    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def test_urls_and_paths_follow_the_geofabrik_layout(tmp_path: Path) -> None:
    assert fetch.region_url("europe/great-britain") == "https://download.geofabrik.de/europe/great-britain-latest.osm.pbf"
    assert fetch.region_path(tmp_path, "europe/great-britain") == tmp_path / "europe" / "great-britain-latest.osm.pbf"


def test_download_fetches_once_and_identifies_itself(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return _Response(b"pbf-bytes")

    monkeypatch.setattr(fetch, "urlopen", fake_urlopen)
    path = fetch.download("europe/great-britain", tmp_path)
    assert path.read_bytes() == b"pbf-bytes"
    assert requests[0].get_header("User-agent") == fetch.USER_AGENT
    assert "@" not in fetch.USER_AGENT  # no personal address goes to a third party

    fetch.download("europe/great-britain", tmp_path)  # already there
    assert len(requests) == 1
    fetch.download("europe/great-britain", tmp_path, refresh=True)
    assert len(requests) == 2


def test_a_failed_download_leaves_no_file_that_looks_complete(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Broken(_Response):
        def read(self, size: int = -1) -> bytes:
            raise OSError("connection reset")

    monkeypatch.setattr(fetch, "urlopen", lambda request, timeout: Broken(b"x"))
    with pytest.raises(OSError):
        fetch.download("europe/great-britain", tmp_path)
    assert not fetch.region_path(tmp_path, "europe/great-britain").exists()


# MARK: - build-all and the site


def test_build_all_builds_every_region_and_writes_the_site(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    regions_file = tmp_path / "regions.txt"
    regions_file.write_text("europe/great-britain\neurope/ireland-and-northern-ireland\n")
    fetched = []
    monkeypatch.setattr(cli, "download", lambda region, data_dir, refresh: fetched.append(region) or FIXTURE)

    out = tmp_path / "out"
    assert cli.main(["build-all", str(regions_file), str(tmp_path / "data"), str(out)]) == 0

    assert fetched == ["europe/great-britain", "europe/ireland-and-northern-ireland"]
    regions = json.loads((out / "regions.json").read_text())
    assert [r["path"] for r in regions["regions"]] == fetched
    assert (out / "europe/great-britain/index.json").exists()
    assert (out / ".nojekyll").exists()
    assert "Open golf course maps" in (out / "index.html").read_text()


def test_build_all_with_no_regions_fails(tmp_path: Path) -> None:
    regions_file = tmp_path / "regions.txt"
    regions_file.write_text("# nothing\n")
    assert cli.main(["build-all", str(regions_file), str(tmp_path), str(tmp_path / "out")]) == 1


def test_the_landing_page_credits_openstreetmap_and_links_each_region(tmp_path: Path) -> None:
    regions = {"regions": [{
        "path": "europe/great-britain", "index": "europe/great-britain/index.json", "courseCount": 3,
        "statusCounts": {"ready": 1, "partial": 1, "outline": 1}, "bounds": None, "dataTimestamp": None,
    }]}
    page = render_site_index(regions)
    assert "© OpenStreetMap contributors" in page
    assert 'href="europe/great-britain/index.json"' in page
    assert "Open Database Licence" in page


def test_the_landing_page_escapes_what_it_prints() -> None:
    regions = {"regions": [{
        "path": "<script>", "index": "x", "courseCount": 0,
        "statusCounts": {"ready": 0, "partial": 0, "outline": 0}, "bounds": None, "dataTimestamp": None,
    }]}
    assert "<script>" not in render_site_index(regions)


def test_build_regions_on_an_empty_folder_gives_an_empty_list(tmp_path: Path) -> None:
    assert build_regions(tmp_path)["regions"] == []
