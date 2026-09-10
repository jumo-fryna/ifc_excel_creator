from pathlib import Path

from openpyxl import load_workbook

from ifc_steel_generator.models import ElementKind, ParseResult, SteelElement
from ifc_steel_generator.reporting.excel_generator import ExcelGenerator, SHEETS, output_filename


def sample():
    return ParseResult(Path("model.ifc"),profiles=[SteelElement(1,"IfcBeam",ElementKind.PROFILE,"HEA300",material="S355",length_mm=1000,net_weight_kg=88.3)],plates=[SteelElement(2,"IfcPlate",ElementKind.PLATE,"PL16x144",material="S355",thickness_mm=16,nominal_width_mm=144,net_volume_m3=0.01)])


def test_workbook(tmp_path):
    target=ExcelGenerator().generate(sample(),tmp_path/"out.xlsx")
    wb=load_workbook(target,data_only=False)
    assert wb.sheetnames==SHEETS
    assert wb["DANE_BLACHY"]["K2"].value.startswith("=IF(")
    assert wb["PODSUMOWANIE"]["B7"].value==7850


def test_filename():
    assert output_filename("abc-C-003-rev1.ifc")=="Zestawienie_stali_IFC_C-003.xlsx"
    assert output_filename("abc.ifc")=="Zestawienie_stali_IFC_.xlsx"

