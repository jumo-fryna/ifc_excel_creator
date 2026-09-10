$ErrorActionPreference = "Stop"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest
python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name IFC_Steel_List_Generator `
  --collect-all ifcopenshell `
  --collect-all PySide6 `
  --paths src `
  run_app.py
Write-Host "Gotowe: dist/IFC_Steel_List_Generator.exe"
