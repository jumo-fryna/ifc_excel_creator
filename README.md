# IFC Steel List Generator

Lokalna aplikacja Windows tworząca osobne zestawienie Excel dla każdego modelu IFC konstrukcji stalowej. Pliki nie są wysyłane do chmury; analiza odbywa się na komputerze użytkownika.

> Miejsce na zrzut ekranu aplikacji.

## Najprostsze użycie

1. Pobierz `IFC_Steel_List_Generator.exe` z **Actions → ostatni udany Build Windows EXE → Artifacts**.
2. Uruchom aplikację (Python nie jest potrzebny).
3. Przeciągnij jeden lub więcej plików `.ifc` na okno.
4. Wybierz folder wynikowy i kliknij **GENERUJ ZESTAWIENIA**.
5. Dla każdego IFC powstanie osobny plik `.xlsx`.

## Arkusze raportu

- `PODSUMOWANIE` – liczby elementów, długość, objętość i masa, podział według materiału i grubości.
- `PROFILE` – profile pogrupowane według oznaczenia i materiału.
- `BLACHY` – blachy pogrupowane według oznaczenia i materiału.
- `DANE_PROFILE` – jeden wiersz na każdy fizyczny profil.
- `DANE_BLACHY` – jeden wiersz na każdą fizyczną blachę.

Program preferuje `NetWeight` zapisane w IFC dla profili. Gdy go brakuje, używa `NetVolume × gęstość`. Masa blach zawsze wynika z `NetVolume × gęstość`, dzięki czemu otwory i wycięcia są uwzględnione. Domyślna gęstość stali wynosi **7850 kg/m³** i można ją zmienić w oknie aplikacji.

Program nie zgaduje gatunku, grubości ani wymiarów. Niepewne wartości pozostają puste i są rejestrowane jako ostrzeżenia.

## Uruchomienie deweloperskie

Wymagany Python 3.12 lub nowszy:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test,build]"
python -m ifc_steel_generator.main
```

Testy:

```powershell
python -m pytest -v
```

Opcjonalny test referencyjnego modelu:

```powershell
$env:IFC_REFERENCE_FILE="C:\modele\22084-3-00-015-TD-C-002-rev0-BOILER AND ECO SUPPORT.ifc"
python -m pytest tests/test_ifc_parser.py -v
```

## Budowanie EXE

Uruchom `build_windows.bat` albo:

```powershell
.\build_windows.ps1
```

Gotowy plik znajduje się w `dist\IFC_Steel_List_Generator.exe`. GitHub Actions wykonuje te same testy i budowę automatycznie po każdym zapisie do `main`. Tag `v*` dołącza EXE do GitHub Release.

## Ograniczenia IFC

- Wynik zależy od ilości i materiałów faktycznie zapisanych przez program eksportujący IFC.
- Obsługiwane są typowe modele IFC2x3 i IFC4; nietypowe własne właściwości mogą wymagać rozszerzenia aliasów.
- Element bez reprezentacji geometrycznej nie jest liczony jako część fizyczna.
- Nierozpoznane elementy są pomijane w zestawieniu i zapisywane w logu.
- Grubość oznaczenia `D35` pozostaje pusta, jeśli IFC nie zawiera wiarygodnej właściwości grubości.

Log diagnostyczny: `%USERPROFILE%\IFC Steel List Generator\logs\ifc_steel_generator.log`.

## Prywatność i uwierzytelnianie

Aplikacja nie posiada kont użytkowników, nie wymaga logowania i nie przechowuje haseł ani tokenów. GitHub Actions korzysta wyłącznie z krótkotrwałego `GITHUB_TOKEN`, tworzonego automatycznie przez GitHub dla danego uruchomienia workflow.

