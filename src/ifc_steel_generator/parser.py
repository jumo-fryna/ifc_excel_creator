from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from .classifier import classify_element, parse_plate_designation
from .materials import extract_material, extract_profile_name
from .models import ElementKind, ParseResult, SteelElement
from .quantities import flattened_properties, number
from .units import UnitConverter

LOGGER = logging.getLogger(__name__)
EXCLUDED = {
    "IfcFastener", "IfcMechanicalFastener", "IfcOpeningElement", "IfcGrid",
    "IfcAnnotation", "IfcReinforcingBar", "IfcReinforcingMesh", "IfcDistributionElement",
}


class IfcParser:
    def parse(self, path: str | Path, log: Callable[[str], None] | None = None) -> ParseResult:
        try:
            import ifcopenshell
        except ImportError as exc:
            raise RuntimeError("Brak biblioteki IfcOpenShell. Zainstaluj wymagania programu.") from exc
        source = Path(path)
        try:
            model = ifcopenshell.open(str(source))
        except Exception as exc:
            raise ValueError(f"Nie można otworzyć pliku IFC: {exc}") from exc
        converter = UnitConverter.from_ifc(model)
        result = ParseResult(source=source)
        seen: set[int] = set()
        for element in model.by_type("IfcElement"):
            eid = int(element.id())
            if eid in seen or any(element.is_a(name) for name in EXCLUDED):
                continue
            seen.add(eid)
            if not getattr(element, "Representation", None):
                continue
            item = self._extract(element, converter)
            if item.kind is ElementKind.PROFILE:
                result.profiles.append(item)
            elif item.kind is ElementKind.PLATE:
                result.plates.append(item)
                if item.thickness_mm is None:
                    result.warnings.append(f"IFC #{eid}: nieznana grubość blachy {item.designation or '(bez nazwy)'}")
            else:
                result.unclassified.append(item)
                result.warnings.append(f"IFC #{eid}: element nierozpoznany ({item.ifc_type}, {item.designation})")
        if log:
            log(f"Profile: {len(result.profiles)}, blachy: {len(result.plates)}")
        return result

    def _extract(self, element: object, units: UnitConverter) -> SteelElement:
        ifc_type = str(element.is_a())
        props = flattened_properties(element)
        profile_name = extract_profile_name(element)
        fallback = next((str(v) for v in (
            getattr(element, "Name", None), getattr(element, "ObjectType", None),
            getattr(element, "Tag", None),
        ) if v), "")
        property_profile = props.get("profile")
        # Some IFC2x3 steel exporters store the authoritative fabrication
        # profile in a property set while Name/ProfileName describes a cut or
        # auxiliary geometry. Prefer that explicit fabrication property.
        designation = (str(property_profile) if property_profile else profile_name) or fallback
        kind = classify_element(ifc_type, designation, bool(profile_name))
        plate_dims = parse_plate_designation(designation)
        thickness = number(props, "thickness")
        item = SteelElement(
            ifc_id=int(element.id()), ifc_type=ifc_type, kind=kind,
            designation=designation, tag=str(getattr(element, "Tag", None) or ""),
            material=extract_material(element),
            length_mm=units.length_mm(number(props, "length")),
            net_area_m2=units.area_m2(number(props, "net_area")),
            gross_area_m2=units.area_m2(number(props, "gross_area")),
            net_volume_m3=units.volume_m3(number(props, "net_volume")),
            gross_volume_m3=units.volume_m3(number(props, "gross_volume")),
            net_weight_kg=units.mass_kg(number(props, "net_weight")),
            outer_surface_area_m2=units.area_m2(number(props, "outer_surface_area")),
        )
        if kind is ElementKind.PLATE:
            item.thickness_mm = units.length_mm(thickness) if thickness is not None else plate_dims.thickness_mm
            item.nominal_width_mm = plate_dims.width_mm
        return item
