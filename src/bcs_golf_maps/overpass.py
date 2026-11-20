"""Reads Overpass JSON (`out tags geom`) into features. Used for test fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .model import Feature


@dataclass(frozen=True)
class Loaded:
    features: list[Feature]
    # Relations (multipolygon outlines and hazards) aren't read yet. Counted
    # so a run says how much it ignored instead of ignoring it silently.
    skipped_relations: int
    data_timestamp: str | None = None


def load_overpass(path: Path) -> Loaded:
    document = json.loads(Path(path).read_text())
    elements = document["elements"]
    features: list[Feature] = []
    skipped = 0
    for element in elements:
        kind = element["type"]
        tags = element.get("tags", {})
        if kind == "node":
            coords = ((element["lat"], element["lon"]),)
        elif kind == "way":
            coords = tuple((p["lat"], p["lon"]) for p in element["geometry"])
        else:
            skipped += 1
            continue
        features.append(Feature(kind, element["id"], tags, coords))
    return Loaded(features, skipped, document.get("osm3s", {}).get("timestamp_osm_base"))
