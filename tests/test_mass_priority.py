import pytest

from ifc_steel_generator.models import ElementKind, SteelElement


def test_ifc_weight_has_priority_over_table_and_net_weight():
    item = SteelElement(
        1, "IfcBeam", ElementKind.PROFILE, "U280",
        length_mm=10_000, gross_weight_kg=420.0, net_weight_kg=400.0,
        unit_weight_kg_m=41.8,
    )

    assert item.mass_kg(7850) == 420.0
    assert item.net_mass_kg(7850) == 400.0


def test_profile_table_has_priority_when_ifc_weight_is_missing_or_zero():
    missing = SteelElement(
        1, "IfcBeam", ElementKind.PROFILE, "U280",
        length_mm=10_000, net_weight_kg=400.0, unit_weight_kg_m=41.8,
    )
    zero = SteelElement(
        2, "IfcBeam", ElementKind.PROFILE, "U280",
        length_mm=10_000, gross_weight_kg=0.0, net_weight_kg=400.0,
        unit_weight_kg_m=41.8,
    )

    assert missing.mass_kg(7850) == pytest.approx(418.0)
    assert zero.mass_kg(7850) == pytest.approx(418.0)


def test_net_volume_is_used_only_for_control_mass_when_weight_is_available():
    item = SteelElement(
        1, "IfcPlate", ElementKind.PLATE, "BL10*80",
        gross_weight_kg=100.0, net_volume_m3=0.012,
    )

    assert item.mass_kg(7850) == 100.0
    assert item.net_mass_kg(7850) == pytest.approx(94.2)


def test_plate_net_weight_precedes_generic_weight():
    item = SteelElement(
        1, "IfcPlate", ElementKind.PLATE, "BL10*80",
        gross_weight_kg=100.0, net_weight_kg=94.0,
    )

    assert item.mass_kg(7850) == 94.0
    assert item.net_mass_kg(7850) == 94.0


def test_explicit_zero_plate_weight_is_not_replaced_by_volume():
    item = SteelElement(
        1, "IfcPlate", ElementKind.PLATE, "BL10*70",
        gross_weight_kg=0.0, net_volume_m3=0.001,
    )

    assert item.mass_kg(7850) == 0.0
    assert item.net_mass_kg(7850) == pytest.approx(7.85)
