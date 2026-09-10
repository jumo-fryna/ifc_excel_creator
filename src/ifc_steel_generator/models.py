from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ElementKind(str, Enum):
    PROFILE = "PROFILE"
    PLATE = "PLATE"
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(slots=True)
class SteelElement:
    ifc_id: int
    ifc_type: str
    kind: ElementKind
    designation: str = ""
    tag: str = ""
    material: str = ""
    length_mm: float | None = None
    thickness_mm: float | None = None
    nominal_width_mm: float | None = None
    net_area_m2: float | None = None
    gross_area_m2: float | None = None
    net_volume_m3: float | None = None
    gross_volume_m3: float | None = None
    net_weight_kg: float | None = None
    outer_surface_area_m2: float | None = None

    def mass_kg(self, density: float) -> float | None:
        if self.kind is ElementKind.PROFILE and self.net_weight_kg is not None:
            return self.net_weight_kg
        if self.net_volume_m3 is not None:
            return self.net_volume_m3 * density
        return None


@dataclass(slots=True)
class ParseResult:
    source: Path
    profiles: list[SteelElement] = field(default_factory=list)
    plates: list[SteelElement] = field(default_factory=list)
    unclassified: list[SteelElement] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def unknown_plate_thickness(self) -> int:
        return sum(p.thickness_mm is None for p in self.plates)


@dataclass(slots=True)
class BatchItemResult:
    source: Path
    output: Path | None = None
    profiles: int = 0
    plates: int = 0
    mass_kg: float = 0.0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

