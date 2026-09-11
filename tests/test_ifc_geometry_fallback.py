from pathlib import Path

import ifcopenshell
import numpy as np
import pytest

from ifc_steel_generator.parser import IfcParser


def _shape(model, profile, depth):
    origin=model.create_entity("IfcCartesianPoint",Coordinates=(0.0,0.0,0.0))
    axis=model.create_entity("IfcAxis2Placement3D",Location=origin)
    direction=model.create_entity("IfcDirection",DirectionRatios=(0.0,0.0,1.0))
    solid=model.create_entity("IfcExtrudedAreaSolid",SweptArea=profile,Position=axis,ExtrudedDirection=direction,Depth=depth)
    context=model.create_entity("IfcGeometricRepresentationContext",ContextIdentifier="Body",ContextType="Model",CoordinateSpaceDimension=3,Precision=1e-5,WorldCoordinateSystem=axis)
    representation=model.create_entity("IfcShapeRepresentation",ContextOfItems=context,RepresentationIdentifier="Body",RepresentationType="SweptSolid",Items=[solid])
    return model.create_entity("IfcProductDefinitionShape",Representations=[representation])


def test_geometry_fallback_for_plate_and_rolled_profile(tmp_path):
    model=ifcopenshell.file(schema="IFC2X3")
    mm=model.create_entity("IfcSIUnit",UnitType="LENGTHUNIT",Prefix="MILLI",Name="METRE")
    m2=model.create_entity("IfcSIUnit",UnitType="AREAUNIT",Name="SQUARE_METRE")
    m3=model.create_entity("IfcSIUnit",UnitType="VOLUMEUNIT",Name="CUBIC_METRE")
    kg=model.create_entity("IfcSIUnit",UnitType="MASSUNIT",Prefix="KILO",Name="GRAM")
    units=model.create_entity("IfcUnitAssignment",Units=[mm,m2,m3,kg])
    model.create_entity("IfcProject",GlobalId=ifcopenshell.guid.new(),UnitsInContext=units)
    p2=model.create_entity("IfcAxis2Placement2D",Location=model.create_entity("IfcCartesianPoint",Coordinates=(0.0,0.0)))
    plate_profile=model.create_entity("IfcRectangleProfileDef",ProfileType="AREA",ProfileName="BL10*80",Position=p2,XDim=185.0,YDim=80.0)
    plate=model.create_entity("IfcPlate",GlobalId=ifcopenshell.guid.new(),Name="BL10*80",Representation=_shape(model,plate_profile,10.0))
    i_profile=model.create_entity("IfcIShapeProfileDef",ProfileType="AREA",ProfileName="HEB100",Position=p2,OverallWidth=100.0,OverallDepth=100.0,WebThickness=6.0,FlangeThickness=10.0,FilletRadius=12.0)
    beam=model.create_entity("IfcBeam",GlobalId=ifcopenshell.guid.new(),Name="HEB100",Representation=_shape(model,i_profile,150.0))
    path=tmp_path/"geometry.ifc"; model.write(str(path))
    parsed=IfcParser().parse(path)
    assert parsed.plates[0].mass_kg(7850)==pytest.approx(1.1618,abs=0.0001)
    assert parsed.profiles[0].length_mm==pytest.approx(150.0,abs=0.01)
    assert parsed.profiles[0].mass_kg(7850)==pytest.approx(3.0615,abs=0.001)


def test_profile_length_follows_sloped_principal_axis():
    class Geometry:
        pass

    # A 12 m member at roughly 22 degrees has an axis-aligned extent of only
    # 11.1 m. The parser must measure along the member, not along X/Y/Z.
    direction = np.array([12 / 13, 5 / 13, 0.0])
    transverse = np.array([-5 / 13, 12 / 13, 0.0])
    vertical = np.array([0.0, 0.0, 1.0])
    vertices = []
    for along in (0.0, 12.0):
        for across in (-0.15, 0.15):
            for height in (-0.075, 0.075):
                vertices.append(along * direction + across * transverse + height * vertical)
    geometry = Geometry()
    geometry.verts = np.asarray(vertices).reshape(-1).tolist()
    length = IfcParser._profile_geometry_length(geometry, (11.1, 4.9, 0.15))
    assert length == pytest.approx(12_000.0, abs=0.01)
