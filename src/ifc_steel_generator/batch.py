from __future__ import annotations

from pathlib import Path
from collections.abc import Collection
from typing import Callable

from .models import BatchItemResult
from .parser import IfcParser
from .reporting.excel_generator import ExcelGenerator, output_filename


def process_batch(files: list[str | Path], output_dir: str | Path, density: float = 7850.0,
                  status: Callable[[str], None] | None = None,
                  progress: Callable[[int, int], None] | None = None,
                  phases: dict[str, Collection[str] | str | None] | None = None) -> list[BatchItemResult]:
    target = Path(output_dir)
    if not target.exists() or not target.is_dir():
        raise ValueError("Folder wynikowy nie istnieje.")
    results: list[BatchItemResult] = []
    used_names: set[str] = set()
    parser, generator = IfcParser(), ExcelGenerator()
    for file in files:
        source = Path(file); item = BatchItemResult(source=source)
        try:
            if status: status(f"Wczytywanie {source.name}...")
            selected_phase = (phases or {}).get(str(source), None)
            parsed = parser.parse(source, status, phase=selected_phase)
            if status: status("Generowanie Excel...")
            name = output_filename(source)
            if name.casefold() in used_names:
                safe_stem = "".join(c if c not in '<>:"/\\|?*' else "_" for c in source.stem)
                name = f"{safe_stem} lista profili analiza.xlsx"
            used_names.add(name.casefold())
            output = generator.generate(parsed, target / name, density)
            item.output=output; item.profiles=len(parsed.profiles); item.plates=len(parsed.plates)
            item.mass_kg=sum((x.mass_kg(density) or 0) for x in parsed.profiles+parsed.plates)
            item.warnings=parsed.warnings
            if status: status(f"Zapisano {output.name}")
        except Exception as exc:
            item.error=str(exc)
            if status: status(f"BŁĄD {source.name}: {exc}")
        results.append(item)
        if progress: progress(len(results), len(files))
    return results
