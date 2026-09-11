from __future__ import annotations

import logging
import os
from pathlib import Path
from collections.abc import Collection
from typing import Callable

from .classifier import classify_element, parse_plate_designation
from .materials import extract_material, extract_profile_name
from .models import ElementKind, ParseResult, SteelElement
from .quantities import flattened_properties, number
from .steel_sections import profile_mass_per_m
from .units import UnitConverter

LOGGER = logging.getLogger(__name__)
EXCLUDED = {
    "IfcFastener", "IfcMechanicalFastener", "IfcOpeningElement", "IfcGrid",
    "IfcAnnotation", "IfcReinforcingBar", "IfcReinforcingMesh", "IfcDistributionElement",
    "IfcVoidingFeature",
}


class IfcParser:
    def detect_phases(self, path: str | Path) -> list[str]:
        try:
            import ifcopenshell
            model = ifcopenshell.open(str(Path(path)))
        except Exception as exc:
            raise ValueError(f"Nie można odczytać faz z pliku IFC: {exc}") from exc
        phases = {
            str(value).strip()
            for element in model.by_type("IfcElement")
            if (value := flattened_properties(element).get("phase")) is not None
            and str(value).strip()
        }
        return sorted(phases, key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value))

    def parse(self, path: str | Path, log: Callable[[str], None] | None = None,
              phase: str | Collection[str] | None = None) -> ParseResult:
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
        geometry_settings = self._geometry_settings()
        result = ParseResult(source=source)
        seen: set[int] = set()
        skipped_phases: dict[str, int] = {}
        pending_geometry: list[tuple[object, SteelElement]] = []
        for element in model.by_type("IfcElement"):
            eid = int(element.id())
            if eid in seen or any(element.is_a(name) for name in EXCLUDED):
                continue
            seen.add(eid)
            if not getattr(element, "Representation", None):
                continue
            props = flattened_properties(element)
            element_phase = props.get("phase")
            if not self._phase_matches(element_phase, phase):
                key = str(element_phase)
                skipped_phases[key] = skipped_phases.get(key, 0) + 1
                continue
            item = self._extract(element, converter, props)
            if self._needs_geometry(item):
                pending_geometry.append((element, item))
            if item.kind is ElementKind.PROFILE:
                result.profiles.append(item)
            elif item.kind is ElementKind.PLATE:
                result.plates.append(item)
                if item.thickness_mm is None:
                    result.warnings.append(f"IFC #{eid}: nieznana grubość blachy {item.designation or '(bez nazwy)'}")
            else:
                result.unclassified.append(item)
                result.warnings.append(f"IFC #{eid}: element nierozpoznany ({item.ifc_type}, {item.designation})")
        if pending_geometry:
            if log:
                log(f"Obliczanie geometrii 3D: {len(pending_geometry)} elementów...")
            self._apply_geometry_batch(model, pending_geometry, converter, geometry_settings, result)
        if log:
            log(f"Profile: {len(result.profiles)}, blachy: {len(result.plates)}")
        if skipped_phases:
            details = ", ".join(f"{key}: {value}" for key, value in sorted(skipped_phases.items()))
            selected = ", ".join(sorted(self._selected_phases(phase)))
            result.warnings.append(f"Pominięto elementy spoza wybranych faz {selected} ({details})")
        return result

    @staticmethod
    def _selected_phases(selected_phase: str | Collection[str] | None) -> set[str]:
        if selected_phase is None:
            return set()
        if isinstance(selected_phase, str):
            return {selected_phase.strip()}
        return {str(value).strip() for value in selected_phase if str(value).strip()}

    @classmethod
    def _phase_matches(cls, element_phase: object | None,
                       selected_phase: str | Collection[str] | None) -> bool:
        selected = cls._selected_phases(selected_phase)
        return not selected or element_phase is None or str(element_phase).strip() in selected

    @staticmethod
    def _needs_geometry(item: SteelElement) -> bool:
        has_gross_weight = item.gross_weight_kg is not None and item.gross_weight_kg > 0
        if item.kind is ElementKind.PLATE:
            return not has_gross_weight and item.net_weight_kg is None and item.net_volume_m3 is None
        if item.kind is ElementKind.PROFILE:
            return item.length_mm is None or (
                not has_gross_weight
                and item.net_weight_kg is None
                and item.unit_weight_kg_m is None
                and item.net_volume_m3 is None
            )
        return False

    @staticmethod
    def _geometry_settings(disable_openings: bool = False):
        try:
            import ifcopenshell.geom
            settings = ifcopenshell.geom.settings()
            settings.set(settings.USE_WORLD_COORDS, False)
            settings.set(settings.CONTEXT_IDENTIFIERS, ["Body"])
            if disable_openings:
                settings.set("disable-opening-subtractions", True)
            return settings
        except Exception:
            return None

    def _apply_geometry_batch(self, model: object,
                              pending: list[tuple[object, SteelElement]],
                              units: UnitConverter, settings: object | None,
                              result: ParseResult) -> None:
        if settings is None:
            for element, _ in pending:
                self._geometry_warning(result, element, "moduł geometrii IfcOpenShell jest niedostępny")
            return
        processed: set[int] = set()
        by_id = {int(element.id()): (element, item) for element, item in pending}
        try:
            import ifcopenshell.geom

            threads = min(4, max(1, os.cpu_count() or 1))
            iterator = ifcopenshell.geom.iterator(
                settings, model, num_threads=threads,
                include=[element for element, _ in pending],
            )
            if iterator.initialize():
                while True:
                    shape = iterator.get()
                    eid = int(shape.id)
                    pair = by_id.get(eid)
                    if pair is not None:
                        element, item = pair
                        try:
                            self._apply_geometry_fallback(
                                element, item, units, settings, geometry=shape.geometry,
                            )
                            processed.add(eid)
                        except Exception as exc:
                            LOGGER.warning(
                                "IFC #%s: równoległy odczyt geometrii nie powiódł się (%s)",
                                eid, exc,
                            )
                    if not iterator.next():
                        break
        except Exception as exc:
            LOGGER.warning("Równoległy odczyt geometrii nie powiódł się: %s", exc)

        # Some IFC geometry engines omit an unsupported product from an
        # iterator. Retry only those products one by one so one bad object does
        # not discard the remainder of the report.
        for element, item in pending:
            eid = int(element.id())
            if eid in processed:
                continue
            try:
                self._apply_geometry_fallback(element, item, units, settings)
            except Exception as exc:
                self._geometry_warning(result, element, exc)

        # Product-level IfcOpeningElement cuts are not part of the fabrication
        # blank. Re-run only affected products, still in parallel, with opening
        # subtraction disabled. Uncut products reuse the first geometry.
        gross_pending = [
            (element, item) for element, item in pending
            if int(element.id()) in processed and getattr(element, "HasOpenings", ())
        ]
        if gross_pending:
            self._apply_gross_opening_geometry(model, gross_pending, result)

    def _apply_gross_opening_geometry(self, model: object,
                                      pending: list[tuple[object, SteelElement]],
                                      result: ParseResult) -> None:
        gross_settings = self._geometry_settings(disable_openings=True)
        if gross_settings is None:
            return
        updated: set[int] = set()
        by_id = {int(element.id()): (element, item) for element, item in pending}
        try:
            import ifcopenshell.geom

            threads = min(4, max(1, os.cpu_count() or 1))
            iterator = ifcopenshell.geom.iterator(
                gross_settings, model, num_threads=threads,
                include=[element for element, _ in pending],
            )
            if iterator.initialize():
                while True:
                    shape = iterator.get()
                    eid = int(shape.id)
                    pair = by_id.get(eid)
                    if pair is not None:
                        _, item = pair
                        self._set_gross_geometry(item, shape.geometry)
                        updated.add(eid)
                    if not iterator.next():
                        break
        except Exception as exc:
            LOGGER.warning("Równoległy odczyt geometrii brutto nie powiódł się: %s", exc)

        for element, item in pending:
            if int(element.id()) in updated:
                continue
            try:
                gross_volume, gross_area = self._gross_geometry(element, gross_settings)
                self._set_gross_values(item, gross_volume, gross_area)
            except Exception as exc:
                self._geometry_warning(result, element, f"geometria brutto: {exc}")

    @staticmethod
    def _set_gross_geometry(item: SteelElement, geometry: object) -> None:
        import ifcopenshell.util.shape

        gross_volume = ifcopenshell.util.shape.get_volume(geometry)
        gross_area = ifcopenshell.util.shape.get_area(geometry)
        IfcParser._set_gross_values(item, gross_volume, gross_area)

    @staticmethod
    def _set_gross_values(item: SteelElement, gross_volume: float | None,
                          gross_area: float | None) -> None:
        if gross_volume is not None:
            item.gross_volume_m3 = gross_volume
            item.mass_volume_m3 = gross_volume
        if item.kind is ElementKind.PLATE and gross_area is not None:
            item.gross_area_m2 = gross_area
        if gross_volume is not None and item.kind is ElementKind.PLATE:
            item.mass_source = "geometria brutto IFC"

    @staticmethod
    def _geometry_warning(result: ParseResult, element: object, exc: object) -> None:
        warning = f"IFC #{int(element.id())}: nie można odczytać ilości z geometrii ({exc})"
        result.warnings.append(warning)
        LOGGER.warning(warning)

    def _apply_geometry_fallback(self, element: object, item: SteelElement,
                                 units: UnitConverter, settings: object | None,
                                 geometry: object | None = None) -> None:
        if settings is None:
            raise RuntimeError("moduł geometrii IfcOpenShell jest niedostępny")
        import ifcopenshell.geom
        import ifcopenshell.util.shape

        if geometry is None:
            shape = ifcopenshell.geom.create_shape(settings, element)
            geometry = shape.geometry
        dimensions = (
            ifcopenshell.util.shape.get_x(geometry),
            ifcopenshell.util.shape.get_y(geometry),
            ifcopenshell.util.shape.get_z(geometry),
        )
        try:
            net_volume = ifcopenshell.util.shape.get_volume(geometry)
        except Exception:
            net_volume = None
        try:
            surface_area = ifcopenshell.util.shape.get_area(geometry)
        except Exception:
            surface_area = None
        if item.net_volume_m3 is None and net_volume is not None:
            item.net_volume_m3 = net_volume
        if item.outer_surface_area_m2 is None and surface_area is not None:
            item.outer_surface_area_m2 = surface_area
        if item.net_area_m2 is None and item.kind is ElementKind.PLATE and surface_area is not None:
            item.net_area_m2 = surface_area
        if item.length_mm is None and item.kind is ElementKind.PROFILE:
            standard_prefixes = ("HEA", "HEB", "HEM", "IPE", "IPN", "UPE", "UPN", "UNP", "HS", "SHS", "RHS", "CHS", "MSH", "L", "N", "D")
            extrusion = self._main_extrusion(element) if item.designation.upper().replace(" ", "").startswith(standard_prefixes) else None
            bounding_length = self._profile_geometry_length(geometry, dimensions)
            extrusion_length = units.length_mm(float(extrusion.Depth)) if extrusion is not None else None
            # For sloped columns the visible cut solid can be materially shorter
            # than the stock extrusion. Ordinary beams and straight columns use
            # their geometric extent, which avoids including Boolean-tool excess.
            use_stock = (
                extrusion_length is not None
                and getattr(element, "is_a", lambda *_: False)("IfcColumn")
                and extrusion_length > bounding_length + 20.0
            )
            item.length_mm = extrusion_length if use_stock else bounding_length

        # Creating the same Body representation a second time was the largest
        # performance bottleneck and did not restore a pre-cut blank for BRep
        # exports.  Keep the actual IFC solid as the explicit fallback basis.
        gross_volume, gross_area = net_volume, surface_area
        if item.gross_volume_m3 is None and gross_volume is not None:
            item.gross_volume_m3 = gross_volume
        if item.gross_area_m2 is None and item.kind is ElementKind.PLATE and gross_area is not None:
            item.gross_area_m2 = gross_area

        # A fabrication list reports the material blank before openings. When
        # the IFC contains no quantities, that gross solid is the reliable mass
        # basis. It is an exact representation item, not a guessed bounding box.
        if item.kind is ElementKind.PLATE:
            item.mass_volume_m3 = gross_volume
            if not item.mass_source and gross_volume is not None:
                item.mass_source = "geometria IFC"
        elif item.kind is ElementKind.PROFILE:
            item.mass_volume_m3 = gross_volume
            if not item.mass_source and gross_volume is not None:
                item.mass_source = "geometria IFC"

    @staticmethod
    def _profile_geometry_length(geometry: object,
                                 dimensions: tuple[float, float, float]) -> float:
        """Return length along the solid's principal axis, in millimetres.

        An axis-aligned bounding box shortens every sloped member. Surface
        normals recover the longitudinal axis, including BRep-only exports
        which do not expose an IfcExtrudedAreaSolid or a Length quantity.
        """
        try:
            import numpy as np

            vertices = np.asarray(getattr(geometry, "verts"), dtype=float).reshape((-1, 3))
            if len(vertices) < 3:
                raise ValueError("za mało wierzchołków")
            direction = None
            faces = np.asarray(getattr(geometry, "faces", ()), dtype=int)
            if len(faces) >= 3:
                triangles = vertices[faces.reshape((-1, 3))]
                crosses = np.cross(
                    triangles[:, 1] - triangles[:, 0],
                    triangles[:, 2] - triangles[:, 0],
                )
                twice_area = np.linalg.norm(crosses, axis=1)
                valid = twice_area > 1e-12
                normals = crosses[valid] / twice_area[valid, None]
                areas = twice_area[valid] / 2.0
                # Side-face normals are perpendicular to the member axis and
                # dominate by area. The least represented normal direction is
                # therefore the stock axis, even with angled cuts and holes.
                normal_covariance = np.einsum(
                    "i,ij,ik->jk", areas, normals, normals,
                )
                values, vectors = np.linalg.eigh(normal_covariance)
                direction = vectors[:, int(np.argmin(values))]
            if direction is None:
                centered = vertices - vertices.mean(axis=0)
                covariance = np.cov(centered, rowvar=False)
                values, vectors = np.linalg.eigh(covariance)
                direction = vectors[:, int(np.argmax(values))]
            span_m = float(np.ptp(vertices @ direction))
            if span_m > 0:
                return span_m * 1000.0
        except Exception:
            pass
        return max(dimensions) * 1000.0

    @staticmethod
    def _body_items(element: object) -> list[object]:
        definition = getattr(element, "Representation", None)
        representations = getattr(definition, "Representations", []) or []
        body = [r for r in representations if str(getattr(r, "RepresentationIdentifier", "")).lower() == "body"]
        selected = body or list(representations[:1])
        return [part for rep in selected for part in (getattr(rep, "Items", []) or [])]

    def _gross_geometry(self, element: object, settings: object) -> tuple[float, float]:
        import ifcopenshell.geom
        import ifcopenshell.util.shape

        volumes: list[float] = []
        areas: list[float] = []
        for representation_item in self._body_items(element):
            created = ifcopenshell.geom.create_shape(settings, representation_item)
            geometry = getattr(created, "geometry", created)
            volumes.append(ifcopenshell.util.shape.get_volume(geometry))
            areas.append(ifcopenshell.util.shape.get_area(geometry))
        if not volumes:
            raise ValueError("brak reprezentacji Body")
        return sum(volumes), sum(areas)

    def _nominal_profile_area(self, element: object, units: UnitConverter) -> float | None:
        """Returns analytical nominal cross-section area for common IFC profiles."""
        for representation_item in self._body_items(element):
            swept = self._find_swept_area(representation_item)
            if swept is None:
                continue
            if swept.is_a("IfcRectangleProfileDef"):
                raw = float(swept.XDim) * float(swept.YDim)
                return units.area_m2(raw)
            if swept.is_a("IfcIShapeProfileDef"):
                h = float(swept.OverallDepth); b = float(swept.OverallWidth)
                tw = float(swept.WebThickness); tf = float(swept.FlangeThickness)
                r = float(getattr(swept, "FilletRadius", None) or 0.0)
                raw = 2.0 * b * tf + (h - 2.0 * tf) * tw + 4.0 * r * r * (1.0 - 3.141592653589793 / 4.0)
                # Rolled section tables publish nominal areas to 10 mm².
                if units.length_to_m == 0.001:
                    raw = round(raw / 10.0) * 10.0
                return units.area_m2(raw)
        return None

    @staticmethod
    def _find_swept_area(root: object, seen: set[int] | None = None):
        seen = seen or set()
        entity_id = getattr(root, "id", lambda: 0)()
        marker = (str(getattr(root, "is_a", lambda: "")()), entity_id) if entity_id else id(root)
        if marker in seen:
            return None
        seen.add(marker)
        swept = getattr(root, "SweptArea", None)
        if swept is not None:
            return swept
        info = getattr(root, "get_info", lambda: {})()
        for key, value in info.items():
            if key in {"id", "type", "OwnerHistory"}:
                continue
            values = value if isinstance(value, (list, tuple)) else [value]
            for child in values:
                if hasattr(child, "is_a"):
                    found = IfcParser._find_swept_area(child, seen)
                    if found is not None:
                        return found
        return None

    @staticmethod
    def _main_extrusion(root: object, seen: set[int] | None = None):
        """Find the stock extrusion, following the first operand before cuts."""
        seen = seen or set()
        entity_id = getattr(root, "id", lambda: 0)()
        marker = (str(getattr(root, "is_a", lambda: "")()), entity_id) if entity_id else id(root)
        if marker in seen:
            return None
        seen.add(marker)
        if getattr(root, "is_a", lambda *_: False)("IfcExtrudedAreaSolid"):
            return root
        if getattr(root, "is_a", lambda *_: False)("IfcBooleanResult"):
            return IfcParser._main_extrusion(getattr(root, "FirstOperand", None), seen)
        info = getattr(root, "get_info", lambda: {})()
        for key, value in info.items():
            if key in {"id", "type", "OwnerHistory", "SecondOperand"}:
                continue
            values = value if isinstance(value, (list, tuple)) else [value]
            for child in values:
                if hasattr(child, "is_a"):
                    found = IfcParser._main_extrusion(child, seen)
                    if found is not None:
                        return found
        return None

    def _extract(self, element: object, units: UnitConverter,
                 props: dict[str, object] | None = None) -> SteelElement:
        ifc_type = str(element.is_a())
        props = props if props is not None else flattened_properties(element)
        profile_name = extract_profile_name(element)
        fallback = next((str(v) for v in (
            getattr(element, "ObjectType", None), getattr(element, "Description", None),
            getattr(element, "Name", None),
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
            gross_weight_kg=units.mass_kg(number(props, "gross_weight")),
            net_weight_kg=units.mass_kg(number(props, "net_weight")),
            outer_surface_area_m2=units.area_m2(number(props, "outer_surface_area")),
        )
        if kind is ElementKind.PLATE:
            item.thickness_mm = units.length_mm(thickness) if thickness is not None else plate_dims.thickness_mm
            item.nominal_width_mm = plate_dims.width_mm
            if item.nominal_width_mm is None and plate_dims.thickness_mm is not None:
                raw_width = number(props, "length")
                if raw_width is not None:
                    item.nominal_width_mm = units.length_mm(raw_width)
                    width = item.nominal_width_mm
                    width_text = str(int(round(width))) if abs(width - round(width)) < 1e-6 else f"{width:g}"
                    item.designation = f"{designation}*{width_text}"
            if item.net_weight_kg is not None:
                item.mass_source = "IFC WeightNet"
            elif item.gross_weight_kg is not None:
                item.mass_source = "IFC Weight"
        elif kind is ElementKind.PROFILE:
            item.unit_weight_kg_m, table_source = profile_mass_per_m(designation)
            if item.gross_weight_kg is not None and item.gross_weight_kg > 0:
                item.mass_source = "IFC Weight"
            elif item.unit_weight_kg_m is not None:
                item.mass_source = table_source
            elif item.net_weight_kg is not None:
                item.mass_source = "IFC WeightNet"
        return item
