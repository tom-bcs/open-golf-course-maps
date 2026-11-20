"""Local flat-earth maths, so distances come out in metres."""

from __future__ import annotations

import math
from collections.abc import Sequence

from shapely import make_valid
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from .model import LatLon

EARTH_RADIUS_METRES = 6_371_008.8
METRES_PER_YARD = 0.9144


class Projector:
    """Equirectangular projection around an origin.

    Accurate to well under a metre over the few hundred metres a hole spans.
    Each hole or course gets its own origin, so a long country doesn't
    distort anything.
    """

    def __init__(self, origin: LatLon) -> None:
        self.lat0, self.lon0 = origin
        self._cos = math.cos(math.radians(self.lat0))

    def xy(self, point: LatLon) -> tuple[float, float]:
        lat, lon = point
        x = math.radians(lon - self.lon0) * self._cos * EARTH_RADIUS_METRES
        y = math.radians(lat - self.lat0) * EARTH_RADIUS_METRES
        return x, y

    def latlon(self, x: float, y: float) -> LatLon:
        lat = self.lat0 + math.degrees(y / EARTH_RADIUS_METRES)
        lon = self.lon0 + math.degrees(x / (EARTH_RADIUS_METRES * self._cos))
        return lat, lon

    def point(self, point: LatLon) -> Point:
        return Point(self.xy(point))

    def line(self, coords: Sequence[LatLon]) -> LineString:
        return LineString([self.xy(p) for p in coords])

    def polygon(self, coords: Sequence[LatLon]) -> BaseGeometry:
        polygon = Polygon([self.xy(p) for p in coords])
        # Hand-drawn outlines sometimes cross themselves.
        return polygon if polygon.is_valid else make_valid(polygon)
