from __future__ import annotations

import bisect
from collections.abc import Collection
from pathlib import Path
from typing import Callable

from .models import AssemblyParseResult, AssemblyPart, AssemblyRecord, SteelElement
from .parser import EXCLUDED, IfcParser
from .quantities import flattened_properties, normalize
from .units import UnitConverter


ASSEMBLY_MARK_KEYS = (
    "assemblypos", "assemblymark", "assemblycastunitmark",
    "assemblypositionnumber",
)
DECLARED_MASS_KEYS = (
    "assemblycastunitweight", "weightgross", "grossweight", "weightnet",
)
SHIPPING_MARK_KEYS = ("shippingmark", "shippingposition", "shippingunit")
LOT_KEYS = ("lotnumber", "lot", "lotno")
POSITION_KEYS = ("assemblycastunitpositioncode", "positioncode")


def _text(props: dict[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = props.get(normalize(key))
        wrapped = getattr(value, "wrappedValue", value)
        if wrapped is not None and str(wrapped).strip() not in {"", "0", "0.0", "None"}:
            return str(wrapped).strip()
    return ""


def _number(props: dict[str, object], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = props.get(normalize(key))
        wrapped = getattr(value, "wrappedValue", value)
        if isinstance(wrapped, (int, float)) and not isinstance(wrapped, bool):
            return float(wrapped)
    return None


class IfcAssemblyParser:
    """Extract assembly membership and shipping-unit summaries from an IFC."""

    def __init__(self) -> None:
        self.element_parser = IfcParser()

    def parse(self, path: str | Path, density: float = 7850.0,
              log: Callable[[str], None] | None = None,
              phase: str | Collection[str] | None = None) -> AssemblyParseResult:
        try:
            import ifcopenshell
        except ImportError as exc:
            raise RuntimeError("Brak biblioteki IfcOpenShell. Zainstaluj wymagania programu.") from exc

        source = Path(path)
        if log:
            log(f"Odczyt części i powierzchni: {source.name}...")
        elements_result = self.element_parser.parse(
            source, log=log, phase=phase, require_surface=True,
        )
        try:
            model = ifcopenshell.open(str(source))
        except Exception as exc:
            raise ValueError(f"Nie można otworzyć pliku IFC: {exc}") from exc

        units = UnitConverter.from_ifc(model)
        result = AssemblyParseResult(source=source, warnings=list(elements_result.warnings))
        selected = self.element_parser._selected_phases(phase)
        assemblies = list(model.by_type("IfcElementAssembly"))
        orphan_properties = self._orphan_block_properties(model, assemblies)

        records: dict[int, AssemblyRecord] = {}
        assembly_entities: dict[int, object] = {}
        marks: dict[str, list[int]] = {}
        for assembly in assemblies:
            props = flattened_properties(assembly)
            for key, value in orphan_properties.get(int(assembly.id()), {}).items():
                props.setdefault(key, value)
            assembly_phase = _text(props, ("phase",))
            if selected and assembly_phase and assembly_phase not in selected:
                continue
            mark = _text(props, ASSEMBLY_MARK_KEYS) or str(getattr(assembly, "Tag", None) or "").strip()
            if not mark:
                mark = f"IFC-{int(assembly.id())}"
            shipping_mark = _text(props, SHIPPING_MARK_KEYS)
            record = AssemblyRecord(
                ifc_id=int(assembly.id()), mark=mark,
                name=str(getattr(assembly, "Name", None) or ""),
                shipping_mark=shipping_mark, phase=assembly_phase,
                lot_number=_text(props, LOT_KEYS),
                position_code=_text(props, POSITION_KEYS),
                declared_mass_kg=units.mass_kg(_number(props, DECLARED_MASS_KEYS)),
            )
            records[record.ifc_id] = record
            assembly_entities[record.ifc_id] = assembly
            marks.setdefault(mark.casefold(), []).append(record.ifc_id)

        steel_elements = {
            item.ifc_id: item
            for item in elements_result.profiles + elements_result.plates + elements_result.unclassified
        }
        assigned: set[int] = set()
        relation_assemblies = 0
        for assembly_id, assembly in assembly_entities.items():
            children = self._related_parts(assembly)
            if children:
                relation_assemblies += 1
            for child, level in children:
                item = steel_elements.get(int(child.id()))
                if item is None or item.ifc_id in assigned:
                    continue
                self._append(records[assembly_id], item, level, "relacja IFC")
                assigned.add(item.ifc_id)

        # Some exporters omit decomposition but repeat ASSEMBLY_POS on parts.
        for element_id, item in steel_elements.items():
            if element_id in assigned:
                continue
            mark = item.assembly_mark
            candidates = marks.get(mark.casefold(), []) if mark else []
            if candidates:
                assembly_id = self._nearest_preceding(candidates, element_id)
                self._append(records[assembly_id], item, 1, "ASSEMBLY_POS")
                assigned.add(element_id)

        # A mounting assembly does not have to be exported as an
        # IfcElementAssembly. Tekla/Zeman commonly exports one-piece assemblies
        # only as ordinary beams/plates carrying ASSEMBLY_POS and PART_POS.
        # Each main part (PART_POS == ASSEMBLY_POS) is one physical assembly.
        implicit_count = 0
        unassigned_by_mark: dict[str, list[SteelElement]] = {}
        for element_id, item in steel_elements.items():
            if element_id not in assigned and item.assembly_mark:
                unassigned_by_mark.setdefault(item.assembly_mark.casefold(), []).append(item)
        for folded_mark, items in unassigned_by_mark.items():
            if folded_mark in marks:
                continue
            mark = items[0].assembly_mark
            main_parts = [
                item for item in items
                if item.part_position.casefold() == folded_mark
            ]
            if not main_parts:
                main_parts = [min(items, key=lambda value: value.ifc_id)]
                result.warnings.append(
                    f"Zespół {mark}: brak jawnej części głównej; podział odtworzono z ASSEMBLY_POS."
                )
            seed_ids: list[int] = []
            for main in sorted(main_parts, key=lambda value: value.ifc_id):
                record = AssemblyRecord(
                    ifc_id=main.ifc_id,
                    mark=mark,
                    name=main.name,
                    shipping_mark=mark,
                    phase=main.phase,
                    declared_mass_kg=main.gross_weight_kg,
                    length_mm=main.fabrication_length_mm,
                )
                records[record.ifc_id] = record
                marks.setdefault(folded_mark, []).append(record.ifc_id)
                seed_ids.append(record.ifc_id)
                self._append(record, main, 1, "ASSEMBLY_POS/PART_POS")
                assigned.add(main.ifc_id)
                implicit_count += 1
            for item in sorted(items, key=lambda value: value.ifc_id):
                if item.ifc_id in assigned:
                    continue
                assembly_id = self._nearest_preceding(seed_ids, item.ifc_id)
                self._append(records[assembly_id], item, 1, "ASSEMBLY_POS (zespół pośredni)")
                assigned.add(item.ifc_id)

        # Last-resort support for malformed Tekla/MTA exports: the assembly,
        # its orphan property sets and its products form consecutive STEP blocks.
        if relation_assemblies == 0 and assembly_entities:
            sorted_ids = sorted(records)
            for element_id, item in steel_elements.items():
                if element_id in assigned:
                    continue
                pos = bisect.bisect_right(sorted_ids, element_id) - 1
                if pos < 0:
                    continue
                assembly_id = sorted_ids[pos]
                self._append(records[assembly_id], item, 1, "blok eksportu (awaryjnie)")
                assigned.add(element_id)
            result.warnings.append(
                "Eksporter nie zapisał relacji zespołów; przypisanie części odtworzono "
                "z kolejności bloków STEP i oznaczono jako awaryjne."
            )

        for record in records.values():
            if record.length_mm is None:
                lengths = [
                    part.element.fabrication_length_mm
                    for part in record.parts
                    if part.element.fabrication_length_mm is not None
                ]
                record.length_mm = max(lengths, default=None)
        result.assemblies = sorted(records.values(), key=lambda value: (value.mark, value.ifc_id))
        missing_surface = sum(part.element.outer_surface_area_m2 is None for part in result.parts)
        missing_mass = sum(part.element.mass_kg(density) is None for part in result.parts)
        unassigned = len(steel_elements) - len(assigned)
        empty_assemblies = sum(not record.parts for record in result.assemblies)
        if unassigned:
            result.warnings.append(f"Nie przypisano do zespołów {unassigned} elementów fizycznych.")
        if empty_assemblies:
            result.warnings.append(
                f"{empty_assemblies} zespołów nie ma przypisanych stalowych części; "
                "mogą zawierać wyłącznie łączniki albo pochodzić z niepełnego eksportu."
            )
        if missing_mass:
            result.warnings.append(f"Brak masy dla {missing_mass} części zespołów.")
        if missing_surface:
            result.warnings.append(f"Brak powierzchni dla {missing_surface} części zespołów.")
        if implicit_count:
            result.warnings.append(
                f"Zespoły jednoczęściowe wykryte z ASSEMBLY_POS/PART_POS: {implicit_count}."
            )
        if log:
            log(f"Zespoły: {len(result.assemblies)}, części w zespołach: {len(result.parts)}")
        return result

    @staticmethod
    def _append(record: AssemblyRecord, item: SteelElement, level: int, source: str) -> None:
        record.parts.append(AssemblyPart(
            assembly_id=record.ifc_id,
            assembly_mark=record.mark,
            assembly_name=record.name,
            shipping_mark=record.shipping_mark or record.mark,
            phase=record.phase,
            lot_number=record.lot_number,
            level=level,
            association_source=source,
            element=item,
        ))

    @staticmethod
    def _nearest_preceding(candidates: list[int], element_id: int) -> int:
        values = sorted(candidates)
        pos = bisect.bisect_right(values, element_id) - 1
        return values[pos] if pos >= 0 else values[0]

    @staticmethod
    def _related_parts(assembly: object) -> list[tuple[object, int]]:
        found: list[tuple[object, int]] = []
        queue: list[tuple[object, int]] = [(assembly, 0)]
        seen: set[int] = {int(assembly.id())}
        while queue:
            parent, level = queue.pop(0)
            for relation in getattr(parent, "IsDecomposedBy", ()) or ():
                for child in getattr(relation, "RelatedObjects", ()) or ():
                    child_id = int(child.id())
                    if child_id in seen:
                        continue
                    seen.add(child_id)
                    if child.is_a("IfcElementAssembly"):
                        queue.append((child, level + 1))
                    elif child.is_a("IfcElement") and not any(child.is_a(name) for name in EXCLUDED):
                        found.append((child, level + 1))
        return found

    @staticmethod
    def _orphan_block_properties(model: object, assemblies: list[object]) -> dict[int, dict[str, object]]:
        """Read exporter blocks only when property relations are absent.

        A few Tekla/MTA IFC2x3 files contain valid property sets but omit every
        IfcRelDefinesByProperties. Their STEP order still keeps each property
        block directly after its IfcElementAssembly.
        """
        if model.by_type("IfcRelDefinesByProperties"):
            return {}
        assembly_ids = {int(value.id()) for value in assemblies}
        values: dict[int, dict[str, object]] = {}
        current: int | None = None
        for entity in model:
            entity_id = int(entity.id())
            if entity_id in assembly_ids:
                current = entity_id
                values.setdefault(current, {})
                continue
            if current is None or not entity.is_a("IfcPropertySingleValue"):
                continue
            name = normalize(str(getattr(entity, "Name", "")))
            nominal = getattr(entity, "NominalValue", None)
            wrapped = getattr(nominal, "wrappedValue", nominal)
            if name and wrapped is not None:
                values[current].setdefault(name, wrapped)
        return values
