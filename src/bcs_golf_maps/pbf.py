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
        osmium.FileProcessor(str(path), osmium.osm.NODE | osmium.osm.WAY | osmium.osm.AREA)
        # Locations first: ways have none until every node has been seen.
        .with_locations()
        # Builds multipolygon relations into areas. The filter limits the first
        # pass to golf relations, so it doesn't assemble every lake and wood.
        .with_areas(osmium.filter.TagFilter(*_WANTED_TAGS))
        .with_filter(osmium.filter.TagFilter(*_WANTED_TAGS))
    )
    features: list[Feature] = []
    relations_read = 0
    for element in processor:
        tags = {tag.k: tag.v for tag in element.tags}
        if element.is_area():
            # Closed ways arrive as ways too, which is what the normaliser reads.
            if element.from_way():
                continue
            relations_read += 1
            for part, ring in enumerate(element.outer_rings()):
                coords = [(node.lat, node.lon) for node in ring]
                if coords and coords[0] != coords[-1]:
                    coords.append(coords[0])
                features.append(Feature("relation", element.orig_id(), tags, tuple(coords), part))
        elif element.is_node():
            features.append(Feature("node", element.id, tags, ((element.lat, element.lon),)))
        else:
            coords = tuple((node.lat, node.lon) for node in element.nodes if node.location.valid())
            if len(coords) == len(element.nodes):
                features.append(Feature("way", element.id, tags, coords))
    return Loaded(features, 0, data_timestamp(path), relations_read)
