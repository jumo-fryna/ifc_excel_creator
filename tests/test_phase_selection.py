from pathlib import Path
from unittest.mock import patch

from ifc_steel_generator.batch import process_batch
from ifc_steel_generator.models import ParseResult
from ifc_steel_generator.parser import IfcParser


def test_batch_passes_selected_phases(tmp_path):
    source = tmp_path / "model.ifc"
    with patch("ifc_steel_generator.batch.IfcParser.parse", return_value=ParseResult(source)) as parse:
        process_batch([source], tmp_path, phases={str(source): ("10", "32")})
    assert parse.call_args.kwargs["phase"] == ("10", "32")


def test_phase_matching():
    assert IfcParser._phase_matches(10, "10")
    assert not IfcParser._phase_matches(16, "10")
    assert IfcParser._phase_matches(10, ("10", "32"))
    assert IfcParser._phase_matches(32, ("10", "32"))
    assert not IfcParser._phase_matches(16, ("10", "32"))
    assert IfcParser._phase_matches(16, None)
