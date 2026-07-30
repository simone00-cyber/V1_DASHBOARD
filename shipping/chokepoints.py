"""Geographic definitions used by the maritime dashboard."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chokepoint:
    name: str
    south: float
    west: float
    north: float
    east: float
    center_lat: float
    center_lon: float
    zoom: float

    @property
    def ais_bounding_box(self) -> list[list[float]]:
        return [[self.south, self.west], [self.north, self.east]]


CHOKEPOINTS: dict[str, Chokepoint] = {
    "Strait of Hormuz": Chokepoint(
        name="Strait of Hormuz",
        south=24.30,
        west=54.20,
        north=27.90,
        east=59.10,
        center_lat=26.25,
        center_lon=56.55,
        zoom=6.4,
    ),
    "Bab el-Mandeb": Chokepoint(
        name="Bab el-Mandeb",
        south=11.80,
        west=42.20,
        north=13.70,
        east=44.60,
        center_lat=12.65,
        center_lon=43.35,
        zoom=7.0,
    ),
    "Suez Canal": Chokepoint(
        name="Suez Canal",
        south=29.25,
        west=31.85,
        north=31.45,
        east=33.15,
        center_lat=30.35,
        center_lon=32.45,
        zoom=7.0,
    ),
}
