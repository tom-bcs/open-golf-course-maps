"""Writes the per-course files, the index and the quality report."""

from __future__ import annotations

import json
from collections import Counter
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
    (out_dir / "regions.json").write_text(
        json.dumps(build_regions(out_dir), ensure_ascii=False, separators=(",", ":"))
    )
