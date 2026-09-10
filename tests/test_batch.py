from pathlib import Path
from unittest.mock import patch

from ifc_steel_generator.batch import process_batch
from ifc_steel_generator.models import ParseResult


def test_batch_continues_after_error(tmp_path):
    files=[tmp_path/"a.ifc",tmp_path/"b.ifc"]
    def parse(path, log=None, phase=None):
        if Path(path).name=="a.ifc": raise ValueError("bad")
        return ParseResult(Path(path))
    with patch("ifc_steel_generator.batch.IfcParser.parse",side_effect=parse):
        results=process_batch(files,tmp_path)
    assert results[0].error and results[1].error is None
    assert (tmp_path/"b lista profili analiza.xlsx").exists()
