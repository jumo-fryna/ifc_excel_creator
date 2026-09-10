from ifc_steel_generator.units import UnitConverter, kg_to_t, mass_from_volume, mm_to_m


def test_conversions():
    assert mm_to_m(297701.64)==297.70164
    assert kg_to_t(26252.57)==26.25257
    assert mass_from_volume(1.0,7850)==7850


def test_independent_area_and_volume_units():
    converter=UnitConverter(length_to_m=0.001,area_to_m2=1.0,volume_to_m3=1.0)
    assert converter.length_mm(1000)==1000
    assert converter.area_m2(2.5)==2.5
    assert converter.volume_m3(0.25)==0.25
