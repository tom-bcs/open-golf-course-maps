"""The one input shape the normaliser reads, whatever the source."""

from __future__ import annotations

from dataclasses import dataclass

# (latitude, longitude), as OpenStreetMap and CoreLocation order them.
LatLon = tuple[float, float]


@dataclass(frozen=True)
class Feature:
    """A node, way or multipolygon ring with its tags and coordinates.

    Both readers (Overpass JSON for the test fixtures, the Geofabrik extract
    for the real run) produce these, so the normaliser never knows where the
    data came from.
    """

    osm_type: str  # "node", "way" or "relation" (one outer ring of a multipolygon)
    osm_id: int
    tags: dict[str, str]
    coords: tuple[LatLon, ...]
    # Which outer ring, for a multipolygon relation with more than one.
    part: int = 0

    @property
    def ref(self) -> str:
        return f"{self.osm_type}/{self.osm_id}" + (f"#{self.part}" if self.part else "")

    @property
    def golf(self) -> str | None:
        return self.tags.get("golf")

    @property
    def is_closed(self) -> bool:
        return len(self.coords) >= 4 and self.coords[0] == self.coords[-1]
