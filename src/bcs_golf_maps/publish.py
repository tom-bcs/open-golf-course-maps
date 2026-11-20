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


def build_index(result: BuildResult, data_timestamp: str | None) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "attribution": ATTRIBUTION,
        "dataTimestamp": data_timestamp,
        "courseCount": len(result.courses),
        "courses": [index_entry(c) for c in result.courses],
    }


def render_report(result: BuildResult, data_timestamp: str | None) -> str:
    counts = Counter(c["status"] for c in result.courses)
    lines = [
        "# Quality report",
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


def write_output(result: BuildResult, out_dir: Path, data_timestamp: str | None = None) -> None:
    courses_dir = out_dir / "courses"
    courses_dir.mkdir(parents=True, exist_ok=True)
    for course in result.courses:
        (courses_dir / f"{course['id']}.json").write_text(
            json.dumps(course, ensure_ascii=False, separators=(",", ":"))
        )
    (out_dir / "index.json").write_text(
        json.dumps(build_index(result, data_timestamp), ensure_ascii=False, separators=(",", ":"))
    )
    (out_dir / "report.md").write_text(render_report(result, data_timestamp))
