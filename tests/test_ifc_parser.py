import os
from pathlib import Path

import pytest

from ifc_steel_generator.parser import IfcParser


@pytest.mark.skipif(not os.getenv("IFC_REFERENCE_FILE"), reason="Ustaw IFC_REFERENCE_FILE dla testu regresji")
def test_reference_ifc_regression():
    result=IfcParser().parse(Path(os.environ["IFC_REFERENCE_FILE"]))
    assert len(result.profiles)==73
    assert len(result.plates)==781
    assert sum((p.length_mm or 0) for p in result.profiles)/1000 == pytest.approx(297.70164,abs=0.01)
    mass=sum((e.mass_kg(7850) or 0) for e in result.profiles+result.plates)
    assert mass==pytest.approx(26252.57,abs=1.0)

