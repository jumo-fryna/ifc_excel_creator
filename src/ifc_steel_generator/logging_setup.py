from __future__ import annotations

import logging
from pathlib import Path


def configure_logging() -> None:
    folder = Path.home() / "IFC Steel List Generator" / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(folder / "ifc_steel_generator.log", encoding="utf-8")],
    )

