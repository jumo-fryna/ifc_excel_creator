from pathlib import Path

import ifcopenshell

from ifc_steel_generator.parser import IfcParser


def _product_shape(model):
    return model.create_entity("IfcProductDefinitionShape", Representations=[])


def _quantity_relation(model, element, quantities):
    qset=model.create_entity("IfcElementQuantity", GlobalId=ifcopenshell.guid.new(), Name="BaseQuantities", Quantities=quantities)
    model.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[element], RelatingPropertyDefinition=qset)


def test_parser_reads_physical_instances_and_project_units(tmp_path):
    model=ifcopenshell.file(schema="IFC4")
    mm=model.create_entity("IfcSIUnit",UnitType="LENGTHUNIT",Prefix="MILLI",Name="METRE")
    m2=model.create_entity("IfcSIUnit",UnitType="AREAUNIT",Name="SQUARE_METRE")
    m3=model.create_entity("IfcSIUnit",UnitType="VOLUMEUNIT",Name="CUBIC_METRE")
    kg=model.create_entity("IfcSIUnit",UnitType="MASSUNIT",Prefix="KILO",Name="GRAM")
    units=model.create_entity("IfcUnitAssignment",Units=[mm,m2,m3,kg])
    model.create_entity("IfcProject",GlobalId=ifcopenshell.guid.new(),Name="Test",UnitsInContext=units)
    beam=model.create_entity("IfcBeam",GlobalId=ifcopenshell.guid.new(),Name="HEA300",Tag="B1",Representation=_product_shape(model))
    plate=model.create_entity("IfcPlate",GlobalId=ifcopenshell.guid.new(),Name="PL16x144",Tag="P1",Representation=_product_shape(model))
    _quantity_relation(model,beam,[model.create_entity("IfcQuantityLength",Name="Length",LengthValue=1000),model.create_entity("IfcQuantityVolume",Name="NetVolume",VolumeValue=0.02),model.create_entity("IfcQuantityWeight",Name="NetWeight",WeightValue=157)])
    _quantity_relation(model,plate,[model.create_entity("IfcQuantityArea",Name="NetArea",AreaValue=0.8),model.create_entity("IfcQuantityVolume",Name="NetVolume",VolumeValue=0.01)])
    material=model.create_entity("IfcMaterial",Name="STEEL/S355JR")
    model.create_entity("IfcRelAssociatesMaterial",GlobalId=ifcopenshell.guid.new(),RelatedObjects=[beam,plate],RelatingMaterial=material)
    path=tmp_path/"mini.ifc"; model.write(str(path))
    parsed=IfcParser().parse(path)
    assert len(parsed.profiles)==1 and len(parsed.plates)==1
    assert parsed.profiles[0].length_mm==1000
    assert parsed.profiles[0].net_volume_m3==0.02
    assert parsed.profiles[0].net_weight_kg==157
    assert parsed.plates[0].thickness_mm==16
    assert parsed.plates[0].nominal_width_mm==144
    assert parsed.plates[0].material=="STEEL/S355JR"
