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
    name: str = ""
    tag: str = ""
    material: str = ""
    assembly_mark: str = ""
    part_position: str = ""
    phase: str = ""
    length_mm: float | None = None
    stock_length_mm: float | None = None
    thickness_mm: float | None = None
    nominal_width_mm: float | None = None
    net_area_m2: float | None = None
    gross_area_m2: float | None = None
    net_volume_m3: float | None = None
    gross_volume_m3: float | None = None
    gross_weight_kg: float | None = None
    net_weight_kg: float | None = None
    outer_surface_area_m2: float | None = None
    mass_volume_m3: float | None = None
    unit_weight_kg_m: float | None = None
    unit_surface_m2_m: float | None = None
    mass_source: str = ""

    def mass_kg(self, density: float) -> float | None:
        if self.kind is ElementKind.PROFILE:
            if self.gross_weight_kg is not None and self.gross_weight_kg > 0:
                return self.gross_weight_kg
            if self.unit_weight_kg_m is not None and self.length_mm is not None:
                return self.unit_weight_kg_m * self.length_mm / 1000.0
        # For plates preserve the fabrication-list convention used by the
        # supported exporters: WeightNet describes the cut plate, while Weight
        # is used only when no explicit net weight is present.
        if self.net_weight_kg is not None:
            return self.net_weight_kg
        if self.gross_weight_kg is not None:
            return self.gross_weight_kg
        if self.mass_volume_m3 is not None:
            return self.mass_volume_m3 * density
        if self.net_volume_m3 is not None:
            return self.net_volume_m3 * density
        return None

    def net_mass_kg(self, density: float) -> float | None:
        """Control value based only on IFC net quantities."""
        if self.net_weight_kg is not None:
            return self.net_weight_kg
        if self.net_volume_m3 is not None:
            return self.net_volume_m3 * density
        return None

    @property
    def fabrication_length_mm(self) -> float | None:
        """Length used by workshop lists (uncut extrusion when available)."""
        return self.stock_length_mm or self.length_mm

    def fabrication_mass_kg(self, density: float) -> float | None:
        """Precise workshop mass, with section tables taking precedence."""
        length = self.fabrication_length_mm
        if self.kind is ElementKind.PROFILE and self.unit_weight_kg_m is not None and length is not None:
            return self.unit_weight_kg_m * length / 1000.0
        if self.mass_volume_m3 is not None:
            return self.mass_volume_m3 * density
        return self.mass_kg(density)

    def fabrication_surface_m2(self) -> float | None:
        length = self.fabrication_length_mm
        if self.kind is ElementKind.PROFILE and self.unit_surface_m2_m is not None and length is not None:
            return self.unit_surface_m2_m * length / 1000.0
        return self.outer_surface_area_m2


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
class AssemblyPart:
    assembly_id: int
    assembly_mark: str
    assembly_name: str
    shipping_mark: str
    phase: str
    lot_number: str
    level: int
    association_source: str
    element: SteelElement


@dataclass(slots=True)
class AssemblyRecord:
    ifc_id: int
    mark: str
    name: str = ""
    shipping_mark: str = ""
    phase: str = ""
    lot_number: str = ""
    position_code: str = ""
    declared_mass_kg: float | None = None
    length_mm: float | None = None
    parts: list[AssemblyPart] = field(default_factory=list)

    def parts_mass_kg(self, density: float) -> float:
        return sum(part.element.fabrication_mass_kg(density) or 0.0 for part in self.parts)

    def report_mass_kg(self, density: float) -> float:
        mass = self.parts_mass_kg(density)
        if mass > 0:
            return mass
        return self.declared_mass_kg or 0.0

    @property
    def surface_area_m2(self) -> float:
        return sum(part.element.fabrication_surface_m2() or 0.0 for part in self.parts)


@dataclass(slots=True)
class AssemblyParseResult:
    source: Path
    assemblies: list[AssemblyRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def parts(self) -> list[AssemblyPart]:
        return [part for assembly in self.assemblies for part in assembly.parts]


@dataclass(slots=True)
class BatchItemResult:
    source: Path
    output: Path | None = None
    profiles: int = 0
    plates: int = 0
    mass_kg: float = 0.0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(slots=True)
class AssemblyBatchItemResult:
    source: Path
    structural_output: Path | None = None
    shipping_output: Path | None = None
    assemblies: int = 0
    parts: int = 0
    mass_kg: float = 0.0
    surface_area_m2: float = 0.0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
