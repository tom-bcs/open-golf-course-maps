"""Writes the per-course files, the index and the quality report."""

from __future__ import annotations

import json
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

from .normalise import ATTRIBUTION, SCHEMA_VERSION, BuildResult

STATUSES = ("ready", "partial", "outline")


def index_entry(course: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": course["id"],
        "name": course["name"],
        "club": course["club"],
        "status": course["status"],
        "holeCount": course["holeCount"],
        "parComplete": course["parComplete"],
        "centre": course["centre"],
        "bounds": course["bounds"],
        "file": f"courses/{course['id']}.json",
    }


def build_index(result: BuildResult, region: str, data_timestamp: str | None) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "attribution": ATTRIBUTION,
        "region": region,
        "dataTimestamp": data_timestamp,
        "courseCount": len(result.courses),
        "courses": [index_entry(c) for c in result.courses],
    }


def render_report(result: BuildResult, region: str, data_timestamp: str | None) -> str:
    counts = Counter(c["status"] for c in result.courses)
    lines = [
        f"# Quality report: {region}",
        "",
        f"Source data: {data_timestamp or 'unknown'}. {ATTRIBUTION}.",
        "",
        f"- Courses: {len(result.courses)}",
        *[f"- {status}: {counts.get(status, 0)}" for status in STATUSES],
        f"- Skipped: {len(result.skipped)}",
        "",
    ]
    partial = [c for c in result.courses if c["status"] == "partial"]
    if partial:
        lines += ["## Partial courses", ""]
        for course in partial:
            lines.append(f"- **{course['name'] or course['id']}** ({course['id']}): " + "; ".join(course["issues"]))
        lines.append("")
    if result.skipped:
        lines += ["## Skipped", "", *[f"- {reason}" for reason in result.skipped], ""]
    return "\n".join(lines)


def write_output(
    result: BuildResult, out_dir: Path, region: str, data_timestamp: str | None = None
) -> Path:
    """Writes one region under `out_dir/<region>/` and returns that folder.

    The region is the Geofabrik path (`europe/great-britain`), so the folders
    group by continent without a table of our own to maintain.
    """
    region_dir = out_dir / region
    courses_dir = region_dir / "courses"
    courses_dir.mkdir(parents=True, exist_ok=True)
    for course in result.courses:
        (courses_dir / f"{course['id']}.json").write_text(
            json.dumps(course, ensure_ascii=False, separators=(",", ":"))
        )
    (region_dir / "index.json").write_text(
        json.dumps(build_index(result, region, data_timestamp), ensure_ascii=False, separators=(",", ":"))
    )
    (region_dir / "report.md").write_text(render_report(result, region, data_timestamp))
    write_regions(out_dir)
    return region_dir


def build_regions(out_dir: Path) -> dict[str, Any]:
    """Summarises every region index found under `out_dir`.

    Read from disk, not from the current run, so building one region never
    drops the others from the list.
    """
    regions = []
    for path in sorted(out_dir.glob("**/index.json")):
        index = json.loads(path.read_text())
        courses = index["courses"]
        bounds = None
        if courses:
            bounds = [
                min(c["bounds"][0] for c in courses),
                min(c["bounds"][1] for c in courses),
                max(c["bounds"][2] for c in courses),
                max(c["bounds"][3] for c in courses),
            ]
        regions.append({
            "path": index["region"],
            "index": f"{index['region']}/index.json",
            "courseCount": index["courseCount"],
            "statusCounts": {s: sum(1 for c in courses if c["status"] == s) for s in STATUSES},
            "bounds": bounds,
            "dataTimestamp": index["dataTimestamp"],
        })
    return {"schema": SCHEMA_VERSION, "attribution": ATTRIBUTION, "regions": regions}


def write_regions(out_dir: Path) -> None:
    regions = build_regions(out_dir)
    (out_dir / "regions.json").write_text(json.dumps(regions, ensure_ascii=False, separators=(",", ":")))
    (out_dir / "index.html").write_text(render_site_index(regions))
    (out_dir / ".nojekyll").write_text("")  # serve the files as they are


def render_site_index(regions: dict[str, Any]) -> str:
    """The landing page, so the site root isn't a 404."""
    rows = "\n".join(
        "<tr>"
        f'<td><a href="{escape(r["index"])}">{escape(r["path"])}</a></td>'
        f'<td>{r["courseCount"]}</td>'
        f'<td>{r["statusCounts"]["ready"]}</td>'
        f'<td>{r["statusCounts"]["partial"]}</td>'
        f'<td>{r["statusCounts"]["outline"]}</td>'
        f'<td>{escape(r["dataTimestamp"] or "unknown")}</td>'
        f'<td><a href="{escape(r["path"])}/report.md">report</a></td>'
        "</tr>"
        for r in regions["regions"]
    )
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Open golf course maps</title>
<style>
body {{ font: 16px/1.5 system-ui, sans-serif; margin: 2rem auto; max-width: 52rem; padding: 0 1rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #ccc; padding: .4rem .6rem; text-align: left; }}
</style>
</head>
<body>
<h1>Open golf course maps</h1>
<p>Golf course maps built from OpenStreetMap: one JSON file per course, grouped by region.
Start from <a href="regions.json">regions.json</a>.</p>
<table>
<thead><tr><th>Region</th><th>Courses</th><th>Ready</th><th>Partial</th><th>Outline only</th><th>Data from</th><th></th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
<p>{escape(ATTRIBUTION)}. The data is available under the
<a href="https://opendatacommons.org/licenses/odbl/1-0/">Open Database Licence 1.0</a>.
Source and code (MIT): <a href="https://github.com/tom-bcs/open-golf-course-maps">tom-bcs/open-golf-course-maps</a>.
Not affiliated with or endorsed by the OpenStreetMap Foundation.</p>
</body>
</html>
"""
