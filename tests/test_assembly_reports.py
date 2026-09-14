from pathlib import Path

import ifcopenshell
from openpyxl import load_workbook

from ifc_steel_generator.assembly_parser import IfcAssemblyParser
from ifc_steel_generator.reporting.assembly_excel_generator import (
    AssemblyExcelGenerator,
    shipping_output_filename,
    structural_output_filename,
)


def _shape(model, name: str, x: float, y: float, depth: float):
    origin = model.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
    axis = model.create_entity("IfcAxis2Placement3D", Location=origin)
    direction = model.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
    p2 = model.create_entity("IfcAxis2Placement2D", Location=model.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0)))
    profile = model.create_entity("IfcRectangleProfileDef", ProfileType="AREA", ProfileName=name, Position=p2, XDim=x, YDim=y)
    solid = model.create_entity("IfcExtrudedAreaSolid", SweptArea=profile, Position=axis, ExtrudedDirection=direction, Depth=depth)
    context = model.create_entity("IfcGeometricRepresentationContext", ContextIdentifier="Body", ContextType="Model", CoordinateSpaceDimension=3, Precision=1e-5, WorldCoordinateSystem=axis)
    representation = model.create_entity("IfcShapeRepresentation", ContextOfItems=context, RepresentationIdentifier="Body", RepresentationType="SweptSolid", Items=[solid])
    return model.create_entity("IfcProductDefinitionShape", Representations=[representation])


def _property_set(model, element, values):
    properties = [
        model.create_entity("IfcPropertySingleValue", Name=name, NominalValue=model.create_entity(kind, value))
        for name, kind, value in values
    ]
    pset = model.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), Name="Test", HasProperties=properties)
    model.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[element], RelatingPropertyDefinition=pset)


def _model(path: Path) -> None:
    model = ifcopenshell.file(schema="IFC4")
    mm = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE")
    m2 = model.create_entity("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE")
    m3 = model.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE")
    kg = model.create_entity("IfcSIUnit", UnitType="MASSUNIT", Prefix="KILO", Name="GRAM")
    units = model.create_entity("IfcUnitAssignment", Units=[mm, m2, m3, kg])
    model.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), UnitsInContext=units)
    assembly = model.create_entity("IfcElementAssembly", GlobalId=ifcopenshell.guid.new(), Name="Träger", Tag="A-01", PredefinedType="NOTDEFINED")
    plate = model.create_entity("IfcPlate", GlobalId=ifcopenshell.guid.new(), Name="PL10x100", Tag="P1", Representation=_shape(model, "PL10x100", 10.0, 100.0, 1000.0))
    beam = model.create_entity("IfcBeam", GlobalId=ifcopenshell.guid.new(), Name="IPE100", Tag="B1", Representation=_shape(model, "IPE100", 100.0, 10.0, 2000.0))
    model.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=assembly, RelatedObjects=[plate, beam])
    _property_set(model, assembly, [
        ("ASSEMBLY_POS", "IfcIdentifier", "A-01"),
        ("ShippingMark", "IfcIdentifier", "S-01"),
        ("PHASE", "IfcInteger", 10),
        ("Assembly/Cast unit weight", "IfcMassMeasure", 25.0),
    ])
    path.parent.mkdir(parents=True, exist_ok=True); model.write(str(path))


def test_assembly_parser_and_two_workbooks(tmp_path):
    source = tmp_path / "model.ifc"; _model(source)
    result = IfcAssemblyParser().parse(source, phase=("10",))
    assert len(result.assemblies) == 1
    assert result.assemblies[0].mark == "A-01"
    assert result.assemblies[0].shipping_mark == "S-01"
    assert len(result.parts) == 2
    assert result.assemblies[0].report_mass_kg(7850) == 25.0
    assert result.assemblies[0].surface_area_m2 > 0

    structural, shipping = AssemblyExcelGenerator().generate(result, tmp_path)
    assert structural.name == structural_output_filename(source)
    assert shipping.name == shipping_output_filename(source)
    assert load_workbook(structural).sheetnames == ["ZESPOŁY", "STRUKTURA", "UWAGI"]
    assert load_workbook(shipping).sheetnames == ["ELEMENTY WYSYŁKOWE", "SKŁAD", "UWAGI"]
