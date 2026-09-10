import pytest

from ifc_steel_generator.classifier import classify_element, parse_plate_designation
from ifc_steel_generator.models import ElementKind


@pytest.mark.parametrize(("name","thickness","width"),[
    ("PL16*144",16,144),("PL16x144",16,144),("PL16X144",16,144),
    ("PL16×144",16,144),("PL12.5x200",12.5,200),("D35",None,None),
    ("BL10*108",10,108),
    ("PL10",10,None),
])
def test_plate_dimensions(name,thickness,width):
    value=parse_plate_designation(name); assert value.thickness_mm==thickness; assert value.width_mm==width


def test_classification():
    assert classify_element("IfcPlate","D35") is ElementKind.PLATE
    assert classify_element("IfcBeam","HEA300") is ElementKind.PROFILE
    assert classify_element("IfcBuildingElementProxy","PL8-120") is ElementKind.PLATE
    assert classify_element("IfcBeam","BL12*150") is ElementKind.PLATE
    assert classify_element("IfcDiscreteAccessory","IPE100") is ElementKind.PROFILE
    assert classify_element("IfcDiscreteAccessory","N33.7/3.2") is ElementKind.PROFILE
    assert classify_element("IfcDiscreteAccessory","O452*6") is ElementKind.PROFILE
    assert classify_element("IfcDiscreteAccessory","PL10*146") is ElementKind.PLATE
