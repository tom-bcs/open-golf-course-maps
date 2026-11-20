"""Reads golf features from a Geofabrik `.osm.pbf` extract."""

from __future__ import annotations

from pathlib import Path

import osmium

from .model import Feature
from .normalise import HAZARD_KINDS
from .overpass import Loaded

# Everything the normaliser reads. The filter runs in osmium's C++ and keeps
# an object matching any one of these tags, so Python only ever sees golf.
_GOLF_VALUES = ("hole", "green", "tee", "pin", *HAZARD_KINDS)
_WANTED_TAGS = [("leisure", "golf_course"), *[("golf", value) for value in _GOLF_VALUES]]


def data_timestamp(path: Path) -> str | None:
    """When the extract's data was current, from its header."""
    with osmium.io.Reader(str(path)) as reader:
        return reader.header().get("osmosis_replication_timestamp") or None


def load_pbf(path: Path) -> Loaded:
    processor = (
        osmium.FileProcessor(str(path), osmium.osm.NODE | osmium.osm.WAY | osmium.osm.RELATION)
        # Locations first: ways have none until every node has been seen.
        .with_locations()
        .with_filter(osmium.filter.TagFilter(*_WANTED_TAGS))
    )
    features: list[Feature] = []
    skipped_relations = 0
    for element in processor:
        tags = {tag.k: tag.v for tag in element.tags}
        if element.is_node():
            features.append(Feature("node", element.id, tags, ((element.lat, element.lon),)))
        elif element.is_way():
            coords = tuple((node.lat, node.lon) for node in element.nodes if node.location.valid())
            if len(coords) == len(element.nodes):
                features.append(Feature("way", element.id, tags, coords))
        else:
            skipped_relations += 1
    return Loaded(features, skipped_relations, data_timestamp(path))
