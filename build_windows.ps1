$ErrorActionPreference = "Stop"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest
$VersionLine = Select-String -Path "$PSScriptRoot\pyproject.toml" -Pattern '^version\s*=\s*"([^"]+)"'
if (-not $VersionLine) { throw "Nie znaleziono numeru wersji w pyproject.toml" }
$AppVersion = $VersionLine.Matches[0].Groups[1].Value
$AppName = "IFC_Steel_List_Generator_v$AppVersion"
python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name $AppName `
  --collect-all ifcopenshell `
  --collect-all PySide6 `
  --paths src `
  run_app.py
Write-Host "Gotowe: dist/$AppName.exe"
