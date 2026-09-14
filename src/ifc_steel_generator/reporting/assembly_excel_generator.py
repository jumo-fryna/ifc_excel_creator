from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.table import Table, TableStyleInfo

from ..models import AssemblyParseResult, AssemblyRecord
from .styles import NOTE_FILL, TITLE_FILL, WHITE_BOLD, autosize, style_header, style_total


def _safe_stem(source: str | Path) -> str:
    return "".join(c if c not in '<>:"/\\|?*' else "_" for c in Path(source).stem)


def structural_output_filename(source: str | Path) -> str:
    return f"{_safe_stem(source)} lista strukturalna.xlsx"


def shipping_output_filename(source: str | Path) -> str:
    return f"{_safe_stem(source)} lista elementów wysyłkowych.xlsx"


class AssemblyExcelGenerator:
    def generate(self, result: AssemblyParseResult, output_dir: str | Path,
                 density: float = 7850.0) -> tuple[Path, Path]:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        structural = target / structural_output_filename(result.source)
        shipping = target / shipping_output_filename(result.source)
        self._structural_workbook(result, structural, density)
        self._shipping_workbook(result, shipping, density)
        return structural, shipping

    def _structural_workbook(self, result: AssemblyParseResult, target: Path,
                             density: float) -> None:
        wb = self._workbook(("ZESPOŁY", "STRUKTURA", "UWAGI"))
        ws = wb["ZESPOŁY"]
        ws.append(["LISTA STRUKTURALNA ZESPOŁÓW MONTAŻOWYCH"])
        ws.merge_cells("A1:N1"); ws["A1"].fill = TITLE_FILL; ws["A1"].font = WHITE_BOLD
        ws.append([])
        headers = [
            "IFC ID zespołu", "Zespół montażowy", "Nazwa", "Element wysyłkowy",
            "Faza", "Partia/Lot", "Kod położenia", "Liczba części",
            "Masa deklarowana IFC [kg]", "Masa części (kontrolna) [kg]",
            "Masa raportowa [kg]", "Masa raportowa [t]", "Powierzchnia [m²]",
            "Sposób przypisania",
        ]
        ws.append(headers); style_header(ws[3])
        for record in result.assemblies:
            sources = ", ".join(sorted({part.association_source for part in record.parts}))
            mass = record.report_mass_kg(density)
            ws.append([
                record.ifc_id, record.mark, record.name, record.shipping_mark or record.mark,
                record.phase, record.lot_number, record.position_code, len(record.parts),
                record.declared_mass_kg, record.parts_mass_kg(density), mass, mass / 1000.0,
                record.surface_area_m2, sources,
            ])
        total_mass = sum(record.report_mass_kg(density) for record in result.assemblies)
        ws.append([
            "RAZEM", "", "", "", "", "", "", len(result.parts),
            sum(record.declared_mass_kg or 0.0 for record in result.assemblies),
            sum(record.parts_mass_kg(density) for record in result.assemblies),
            total_mass, total_mass / 1000.0,
            sum(record.surface_area_m2 for record in result.assemblies), "",
        ]); style_total(ws[ws.max_row])
        ws.freeze_panes = "A4"; ws.auto_filter.ref = f"A3:N{max(3, ws.max_row - 1)}"

        detail = wb["STRUKTURA"]
        detail_headers = [
            "IFC ID zespołu", "Zespół montażowy", "Nazwa zespołu", "Element wysyłkowy",
            "Faza", "Partia/Lot", "Poziom", "IFC ID części", "Typ IFC", "Rodzaj",
            "Oznaczenie części", "Marka/Tag", "Materiał", "Długość [mm]",
            "Grubość [mm]", "Masa [kg]", "Źródło masy", "Powierzchnia [m²]",
            "Sposób przypisania",
        ]
        detail.append(detail_headers); style_header(detail[1])
        for record in result.assemblies:
            for part in record.parts:
                element = part.element
                detail.append([
                    record.ifc_id, record.mark, record.name, part.shipping_mark,
                    part.phase, part.lot_number, part.level, element.ifc_id, element.ifc_type,
                    element.kind.value, element.designation, element.tag, element.material,
                    element.length_mm, element.thickness_mm, element.mass_kg(density),
                    element.mass_source, element.outer_surface_area_m2, part.association_source,
                ])
        self._table(detail, "ListaStrukturalna")
        self._notes(wb["UWAGI"], result, density, structural=True)
        self._finish(wb, target)

    def _shipping_workbook(self, result: AssemblyParseResult, target: Path,
                           density: float) -> None:
        wb = self._workbook(("ELEMENTY WYSYŁKOWE", "SKŁAD", "UWAGI"))
        ws = wb["ELEMENTY WYSYŁKOWE"]
        ws.append(["LISTA ELEMENTÓW WYSYŁKOWYCH"])
        ws.merge_cells("A1:N1"); ws["A1"].fill = TITLE_FILL; ws["A1"].font = WHITE_BOLD
        ws.append([])
        headers = [
            "Element wysyłkowy", "Zespół montażowy", "Nazwa", "Faza", "Partia/Lot",
            "Szt.", "Części łącznie", "Masa jedn. średnia [kg]", "Masa łączna [kg]",
            "Masa łączna [t]", "Masa części (kontrolna) [kg]",
            "Powierzchnia jedn. średnia [m²]", "Powierzchnia łączna [m²]", "Źródło masy",
        ]
        ws.append(headers); style_header(ws[3])
        groups: dict[tuple[str, ...], list[AssemblyRecord]] = defaultdict(list)
        for record in result.assemblies:
            shipping_mark = record.shipping_mark or record.mark
            groups[(shipping_mark, record.mark, record.name, record.phase, record.lot_number)].append(record)
        for key, records in sorted(groups.items()):
            total_mass = sum(record.report_mass_kg(density) for record in records)
            total_surface = sum(record.surface_area_m2 for record in records)
            sources = "masa zespołu IFC" if any(
                record.declared_mass_kg is not None and record.declared_mass_kg > 0
                for record in records
            ) else "suma mas części"
            ws.append([
                *key, len(records), sum(len(record.parts) for record in records),
                total_mass / len(records), total_mass, total_mass / 1000.0,
                sum(record.parts_mass_kg(density) for record in records),
                total_surface / len(records), total_surface, sources,
            ])
        total_mass = sum(record.report_mass_kg(density) for record in result.assemblies)
        total_surface = sum(record.surface_area_m2 for record in result.assemblies)
        ws.append([
            "RAZEM", "", "", "", "", len(result.assemblies), len(result.parts), "",
            total_mass, total_mass / 1000.0,
            sum(record.parts_mass_kg(density) for record in result.assemblies), "",
            total_surface, "",
        ]); style_total(ws[ws.max_row])
        ws.freeze_panes = "A4"; ws.auto_filter.ref = f"A3:N{max(3, ws.max_row - 1)}"

        detail = wb["SKŁAD"]
        detail.append([
            "Element wysyłkowy", "IFC ID zespołu", "Zespół montażowy", "IFC ID części",
            "Typ IFC", "Rodzaj", "Oznaczenie części", "Marka/Tag", "Materiał",
            "Masa [kg]", "Powierzchnia [m²]", "Sposób przypisania",
        ]); style_header(detail[1])
        for record in result.assemblies:
            for part in record.parts:
                element = part.element
                detail.append([
                    part.shipping_mark, record.ifc_id, record.mark, element.ifc_id,
                    element.ifc_type, element.kind.value, element.designation, element.tag,
                    element.material, element.mass_kg(density), element.outer_surface_area_m2,
                    part.association_source,
                ])
        self._table(detail, "SkladWysylkowy")
        self._notes(wb["UWAGI"], result, density, structural=False)
        self._finish(wb, target)

    @staticmethod
    def _workbook(names: tuple[str, ...]) -> Workbook:
        wb = Workbook(); wb.remove(wb.active)
        for name in names:
            ws = wb.create_sheet(name); ws.sheet_view.showGridLines = False
        return wb

    @staticmethod
    def _table(ws, name: str) -> None:
        if ws.max_row >= 2:
            table = Table(displayName=name, ref=f"A1:{ws.cell(1, ws.max_column).column_letter}{ws.max_row}")
            table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
            ws.add_table(table)
        else:
            ws.auto_filter.ref = f"A1:{ws.cell(1, ws.max_column).column_letter}1"
        ws.freeze_panes = "A2"

    @staticmethod
    def _notes(ws, result: AssemblyParseResult, density: float, structural: bool) -> None:
        title = "INFORMACJE O RAPORCIE"
        ws.append([title]); ws["A1"].font = Font(bold=True, size=14)
        rows = [
            ("Plik IFC", result.source.name),
            ("Typ raportu", "lista strukturalna" if structural else "lista elementów wysyłkowych"),
            ("Gęstość [kg/m³]", density),
            ("Zespoły", len(result.assemblies)),
            ("Części przypisane", len(result.parts)),
            ("Reguła masy", "masa zespołu z IFC; przy braku suma mas części"),
            ("Reguła powierzchni", "suma zewnętrznych powierzchni części z IFC/geometrii"),
        ]
        for row in rows:
            ws.append(list(row))
        ws.append([]); ws.append(["OSTRZEŻENIA"]); ws[ws.max_row][0].font = Font(bold=True)
        for warning in result.warnings:
            ws.append([warning]); ws[ws.max_row][0].fill = NOTE_FILL

    @staticmethod
    def _finish(wb: Workbook, target: Path) -> None:
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    title = str(ws.cell(1 if ws.title in {"STRUKTURA", "SKŁAD"} else 3, cell.column).value or "")
                    if "[kg]" in title:
                        cell.number_format = '0.00 "kg"'
                    elif "[t]" in title:
                        cell.number_format = '0.000 "t"'
                    elif "[m²]" in title:
                        cell.number_format = '0.000 "m²"'
                    elif "[mm]" in title:
                        cell.number_format = '0.00 "mm"'
            autosize(ws, maximum=38)
        try:
            wb.save(target)
        except PermissionError as exc:
            raise PermissionError(f"Nie można zapisać {target.name}. Zamknij plik w Excelu.") from exc
