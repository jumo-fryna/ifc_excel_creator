import pytest

from ifc_steel_generator.steel_sections import profile_mass_per_m


@pytest.mark.parametrize(("name", "mass"), [
    ("IPE100", 8.0855),
    ("HEA 300", 88.3),
    ("HEB100", 20.41),
    ("L60x4", 3.56),
    ("N33.7/3.2", 2.407),
    ("O452*6", 65.994),
])
def test_profile_table(name, mass):
    value, source = profile_mass_per_m(name)
    assert value == pytest.approx(mass)
    assert source
