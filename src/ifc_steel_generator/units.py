from __future__ import annotations

SI_PREFIX = {
    None: 1.0,
    "": 1.0,
    "MILLI": 1e-3,
    "CENTI": 1e-2,
    "DECI": 1e-1,
    "KILO": 1e3,
}


def mm_to_m(value: float) -> float:
    return value / 1000.0


def kg_to_t(value: float) -> float:
    return value / 1000.0


def mass_from_volume(volume_m3: float, density_kg_m3: float) -> float:
    return volume_m3 * density_kg_m3


class UnitConverter:
    """Converts project length/area/volume/mass units to report units."""

    def __init__(self, length_to_m: float = 1.0, mass_to_kg: float = 1.0,
                 area_to_m2: float | None = None, volume_to_m3: float | None = None):
        self.length_to_m = length_to_m
        self.mass_to_kg = mass_to_kg
        self.area_to_m2 = area_to_m2 if area_to_m2 is not None else length_to_m**2
        self.volume_to_m3 = volume_to_m3 if volume_to_m3 is not None else length_to_m**3

    @classmethod
    def from_ifc(cls, model: object) -> "UnitConverter":
        length_to_m = 1.0
        mass_to_kg = 1.0
        area_to_m2: float | None = None
        volume_to_m3: float | None = None
        projects = model.by_type("IfcProject")
        if not projects:
            return cls()
        assignment = getattr(projects[0], "UnitsInContext", None)
        for unit in getattr(assignment, "Units", []) or []:
            unit_type = str(getattr(unit, "UnitType", "")).upper()
            if unit_type == "LENGTHUNIT":
                length_to_m = cls._si_factor(unit, "METRE", 1)
            elif unit_type == "AREAUNIT":
                area_to_m2 = cls._si_factor(unit, "SQUARE_METRE", 2)
            elif unit_type == "VOLUMEUNIT":
                volume_to_m3 = cls._si_factor(unit, "CUBIC_METRE", 3)
            elif unit_type == "MASSUNIT":
                mass_to_kg = cls._si_factor(unit, "GRAM", 1) / 1000.0
        return cls(length_to_m, mass_to_kg, area_to_m2, volume_to_m3)

    @staticmethod
    def _si_factor(unit: object, base_name: str, exponent: int) -> float:
        if hasattr(unit, "is_a") and unit.is_a("IfcSIUnit"):
            name = str(getattr(unit, "Name", "")).upper()
            if name == base_name:
                return SI_PREFIX.get(str(getattr(unit, "Prefix", "")).upper(), 1.0) ** exponent
        # Conversion-based units are uncommon in steel IFCs. IfcOpenShell's
        # calculated quantities normally remain in project units; warn upstream.
        return 1.0

    def length_mm(self, value: float | None) -> float | None:
        return None if value is None else value * self.length_to_m * 1000.0

    def area_m2(self, value: float | None) -> float | None:
        return None if value is None else value * self.area_to_m2

    def volume_m3(self, value: float | None) -> float | None:
        return None if value is None else value * self.volume_to_m3

    def mass_kg(self, value: float | None) -> float | None:
        return None if value is None else value * self.mass_to_kg
