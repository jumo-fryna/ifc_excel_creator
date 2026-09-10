from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Font
from openpyxl.worksheet.table import Table, TableStyleInfo

from ..models import ElementKind, ParseResult, SteelElement
from .styles import NOTE_FILL, TITLE_FILL, WHITE_BOLD, autosize, style_header, style_total

SHEETS = ["PODSUMOWANIE", "PROFILE", "BLACHY", "DANE_PROFILE", "DANE_BLACHY"]


def output_filename(source: str | Path) -> str:
    match = re.search(r"(?i)(C-\d+)", Path(source).stem)
    suffix = match.group(1).upper() if match else ""
    name = f"Zestawienie_stali_IFC_{suffix}.xlsx"
    return re.sub(r'[<>:"/\\|?*]', "_", name)


class ExcelGenerator:
    def generate(self, result: ParseResult, output: str | Path, density: float = 7850.0) -> Path:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        wb = Workbook()
        wb.remove(wb.active)
        for name in SHEETS:
            wb.create_sheet(name)
        try:
            wb.calculation.fullCalcOnLoad = True
            wb.calculation.forceFullCalc = True
            wb.calculation.calcMode = "auto"
        except AttributeError:
            pass
        self._summary(wb["PODSUMOWANIE"], result, density)
        self._profiles(wb["PROFILE"], result.profiles, density)
        self._plates(wb["BLACHY"], result.plates, density)
        self._profile_data(wb["DANE_PROFILE"], result.profiles)
        self._plate_data(wb["DANE_BLACHY"], result.plates)
        for ws in wb.worksheets:
            self._number_formats(ws)
            autosize(ws)
        try:
            wb.save(target)
        except PermissionError as exc:
            raise PermissionError(f"Nie można zapisać {target.name}. Zamknij plik w Excelu.") from exc
        return target

    @staticmethod
    def _mass(elements: list[SteelElement], density: float) -> float:
        return sum(x.mass_kg(density) or 0 for x in elements)

    def _summary(self, ws, result: ParseResult, density: float) -> None:
        ws.append(["ZESTAWIENIE STALI Z MODELU IFC"])
        ws.merge_cells("A1:F1")
        ws["A1"].fill = TITLE_FILL; ws["A1"].font = WHITE_BOLD
        ws.append([])
        ws.append(["Grupa", "Szt.", "Długość [m]", "NetVolume [m³]", "Masa [kg]", "Masa [t]"])
        style_header(ws[3])
        pm = self._mass(result.profiles, density); bm = self._mass(result.plates, density)
        plen = sum((p.length_mm or 0) / 1000 for p in result.profiles)
        pv = sum(p.net_volume_m3 or 0 for p in result.profiles); bv = sum(p.net_volume_m3 or 0 for p in result.plates)
        ws.append(["Profile", len(result.profiles), plen, pv, pm, pm / 1000])
        ws.append(["Blachy", len(result.plates), 0, bv, bm, bm / 1000])
        ws.append(["RAZEM", len(result.profiles)+len(result.plates), plen, pv+bv, pm+bm, (pm+bm)/1000])
        style_total(ws[6])
        ws.append(["Gęstość stali [kg/m³]", density])
        ws.append(["Blachy bez grubości w nazwie", result.unknown_plate_thickness])
        ws.append([]); ws.append(["PODSUMOWANIE WG MATERIAŁU"]); ws["A10"].font = Font(bold=True)
        ws.append(["Materiał", "Profile [szt.]", "Blachy [szt.]", "Masa [kg]", "Masa [t]"]); style_header(ws[11])
        materials = sorted({x.material or "brak danych" for x in result.profiles + result.plates})
        for mat in materials:
            ps=[x for x in result.profiles if (x.material or "brak danych")==mat]
            bs=[x for x in result.plates if (x.material or "brak danych")==mat]
            mass=self._mass(ps+bs,density); ws.append([mat,len(ps),len(bs),mass,mass/1000])
        row=ws.max_row+2; ws.cell(row,1,"PODSUMOWANIE BLACH WG GRUBOŚCI").font=Font(bold=True)
        row+=1; headers=["Grubość [mm]","Szt.","NetArea [m²]","NetVolume [m³]","Masa [kg]"]
        for c,v in enumerate(headers,1): ws.cell(row,c,v)
        style_header(ws[row])
        groups: dict[float | None,list[SteelElement]]=defaultdict(list)
        for p in result.plates: groups[p.thickness_mm].append(p)
        for key in sorted(groups, key=lambda x:(x is None,x or 0)):
            values=groups[key]; mass=self._mass(values,density); row+=1
            ws.append(["brak danych" if key is None else key,len(values),sum(x.net_area_m2 or 0 for x in values),sum(x.net_volume_m3 or 0 for x in values),mass])
        row=ws.max_row+2
        notes=["Źródło:","Profile: długość i masa pochodzą z ilości IFC.","Blachy: masa jest obliczana jako NetVolume × gęstość stali.","Dla oznaczeń bez pewnej informacji o grubości pola grubości pozostają puste."]
        for note in notes:
            ws.cell(row,1,note).fill=NOTE_FILL; row+=1
        ws.freeze_panes="A4"
        for col in ("C","D","E","F"): 
            for cell in ws[col][3:]: cell.number_format = "0.000"

    def _profiles(self, ws, elements: list[SteelElement], density: float) -> None:
        headers=["Profil","Materiał","Szt.","Długość łączna [m]","Masa łączna [kg]","Masa [t]","Średnio [kg/m]"]
        ws.append(headers); style_header(ws[1]); groups=defaultdict(list)
        for e in elements: groups[(e.designation,e.material)].append(e)
        for (name,mat),values in sorted(groups.items()):
            length=sum((x.length_mm or 0)/1000 for x in values); mass=self._mass(values,density)
            ws.append([name,mat,len(values),length,mass,mass/1000,mass/length if length else None])
        ws.append(["RAZEM PROFILE","",len(elements),sum((x.length_mm or 0)/1000 for x in elements),self._mass(elements,density),self._mass(elements,density)/1000,None]); style_total(ws[ws.max_row])
        ws.auto_filter.ref=f"A1:G{max(1,ws.max_row-1)}"; ws.freeze_panes="A2"

    def _plates(self, ws, elements: list[SteelElement], density: float) -> None:
        headers=["Oznaczenie","Grubość [mm]","Szer. nom. [mm]","Materiał","Szt.","NetArea [m²]","GrossArea [m²]","NetVolume [m³]","GrossVolume [m³]","Masa [kg]","Masa [t]"]
        ws.append(headers); style_header(ws[1]); groups=defaultdict(list)
        for e in elements: groups[(e.designation,e.material)].append(e)
        for (name,mat),values in sorted(groups.items()):
            first=values[0]; mass=self._mass(values,density)
            ws.append([name,first.thickness_mm,first.nominal_width_mm,mat,len(values),sum(x.net_area_m2 or 0 for x in values),sum(x.gross_area_m2 or 0 for x in values),sum(x.net_volume_m3 or 0 for x in values),sum(x.gross_volume_m3 or 0 for x in values),mass,mass/1000])
        mass=self._mass(elements,density)
        ws.append(["RAZEM BLACHY","","","",len(elements),sum(x.net_area_m2 or 0 for x in elements),sum(x.gross_area_m2 or 0 for x in elements),sum(x.net_volume_m3 or 0 for x in elements),sum(x.gross_volume_m3 or 0 for x in elements),mass,mass/1000]); style_total(ws[ws.max_row])
        ws.auto_filter.ref=f"A1:K{max(1,ws.max_row-1)}"; ws.freeze_panes="A2"

    def _profile_data(self, ws, elements: list[SteelElement]) -> None:
        headers=["IFC ID","Typ IFC","Profil","Marka/Tag","Materiał","Długość [mm]","NetVolume [m³]","NetWeight [kg]","OuterSurfaceArea [m²]"]
        ws.append(headers); style_header(ws[1])
        for e in elements: ws.append([e.ifc_id,e.ifc_type,e.designation,e.tag,e.material,e.length_mm,e.net_volume_m3,e.net_weight_kg,e.outer_surface_area_m2])
        self._table(ws,"DaneProfile")

    def _plate_data(self, ws, elements: list[SteelElement]) -> None:
        headers=["IFC ID","Oznaczenie blachy","Marka/Tag","Materiał","Grubość [mm]","Szerokość nominalna [mm]","NetArea [m²]","GrossArea [m²]","NetVolume [m³]","GrossVolume [m³]","Masa obliczona [kg]"]
        ws.append(headers); style_header(ws[1])
        for idx,e in enumerate(elements,2):
            ws.append([e.ifc_id,e.designation,e.tag,e.material,e.thickness_mm,e.nominal_width_mm,e.net_area_m2,e.gross_area_m2,e.net_volume_m3,e.gross_volume_m3,f'=IF(I{idx}="","",I{idx}*\'PODSUMOWANIE\'!$B$7)'])
        self._table(ws,"DaneBlachy")

    @staticmethod
    def _table(ws, name: str) -> None:
        if ws.max_row >= 2:
            table=Table(displayName=name,ref=f"A1:{ws.cell(1,ws.max_column).column_letter}{ws.max_row}")
            table.tableStyleInfo=TableStyleInfo(name="TableStyleMedium2",showRowStripes=True)
            ws.add_table(table)
        else:
            ws.auto_filter.ref=f"A1:{ws.cell(1,ws.max_column).column_letter}1"
        ws.freeze_panes="A2"

    @staticmethod
    def _number_formats(ws) -> None:
        """Applies formats based on Polish report header semantics."""
        header_rows = []
        for row in ws.iter_rows():
            values = [str(c.value or "") for c in row]
            if any("[m³]" in v or "[kg]" in v or "[mm]" in v or "[m²]" in v or "[t]" in v for v in values):
                header_rows.append(row[0].row)
        for header_row in header_rows:
            for cell in ws[header_row]:
                title = str(cell.value or "")
                if "[m³]" in title:
                    fmt = '0.000000 "m³"'
                elif "[m²]" in title:
                    fmt = '0.000 "m²"'
                elif "[kg]" in title:
                    fmt = '0.00 "kg"'
                elif "[t]" in title:
                    fmt = '0.000 "t"'
                elif "[mm]" in title:
                    fmt = '0.00 "mm"'
                elif "[m]" in title:
                    fmt = '0.000 "m"'
                else:
                    continue
                for row in range(header_row + 1, ws.max_row + 1):
                    ws.cell(row, cell.column).number_format = fmt
