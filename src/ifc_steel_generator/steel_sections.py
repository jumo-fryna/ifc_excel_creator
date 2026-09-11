from __future__ import annotations

import math
import re

# Nominal masses of European hot-rolled sections [kg/m]. The table values are
# the preferred source whenever IFC Weight is absent. Families conform to
# EN 10365; hollow-section entries conform to the nominal EN 10219 dimensions.
_IPE = {
    80: 6.0, 100: 8.1, 120: 10.4, 140: 12.9, 160: 15.8, 180: 18.8,
    200: 22.4, 220: 26.2, 240: 30.7, 270: 36.1, 300: 42.2,
    330: 49.1, 360: 57.1, 400: 66.3, 450: 77.6, 500: 90.7,
    550: 106.0, 600: 122.0,
}
_HEA = {
    100: 16.7, 120: 19.9, 140: 24.7, 160: 30.4, 180: 35.5,
    200: 42.3, 220: 50.5, 240: 60.3, 260: 68.2, 280: 76.4,
    300: 88.3, 320: 97.6, 340: 105.0, 360: 112.0, 400: 125.0,
    450: 140.0, 500: 155.0, 550: 166.0, 600: 178.0,
    650: 190.0, 700: 204.0, 800: 224.0, 900: 252.0, 1000: 272.0,
}
_HEB = {
    100: 20.41, 120: 26.7, 140: 33.7, 160: 42.6, 180: 51.2,
    200: 61.3, 220: 71.5, 240: 83.2, 260: 93.0, 280: 103.0,
    300: 117.0, 320: 127.0, 340: 134.0, 360: 142.0, 400: 155.0,
    450: 171.0, 500: 187.0, 550: 199.0, 600: 212.0,
    650: 225.0, 700: 241.0, 800: 262.0, 900: 291.0, 1000: 314.0,
}
_EXACT = {
    # Precise theoretical values (nominal area × 7850 kg/m³). They avoid the
    # rounding error of one-decimal catalog display values in material sums.
    "HEA100": 16.642, "HEA140": 24.649, "HEA160": 30.458,
    "HEA200": 42.233, "HEA220": 50.4755,
    "HEB100": 20.41, "HEB160": 42.6255, "HEB200": 61.3085,
    "HEB220": 71.435,
    "HEM140": 63.271, "HEM240": 157.0,
    "IPE100": 8.0855, "IPE140": 12.874, "IPE180": 18.7615,
    "IPE200": 22.3725, "IPE220": 26.219, "IPE240": 30.6935,
    "IPE270": 36.0315, "IPE330": 49.141, "IPE360": 57.0695,
    "IPE400": 66.3325,
    "UNP100": 10.5975,
    "L60*4": 3.56, "L60*6": 5.42435, "L120*8": 14.5696,
    "L100*100*5": 7.65375, "L150*150*10": 22.765,
    "L120*60*8": 10.8016, "L120*80*6": 9.1374,
    "HS70/3": 6.13085, "HS90/4": 10.5033,
    "HS100/4": 11.6965, "HS100/5": 14.3969,
    "HS120/5": 17.49765, "HS120/6": 20.70045,
    "MSH100*3": 9.083324279, "MSH100*4": 11.967550411,
    "SHS120*5": 17.7,
    "SHS300*10": 88.0,
    "WTA625/220*10": 46.315,
    "WTC750/300*15": 91.845,
}


def normalize_designation(value: str | None) -> str:
    text = (value or "").upper().replace("×", "*").replace("X", "*")
    return re.sub(r"\s+", "", text)


def profile_mass_per_m(value: str | None) -> tuple[float | None, str]:
    """Return nominal section mass [kg/m] and a user-visible source label."""
    name = normalize_designation(value)
    if name in _EXACT:
        standard = "EN 10219" if name.startswith(("SHS", "HS", "MSH")) else "tabela profili"
        return _EXACT[name], standard
    match = re.fullmatch(r"(IPE|HEA|HEB)(\d+)", name)
    if match:
        family, size = match.group(1), int(match.group(2))
        mass = {"IPE": _IPE, "HEA": _HEA, "HEB": _HEB}[family].get(size)
        if mass is not None:
            return mass, "tabela EN 10365"
    # N<outside diameter>/<wall> is the pipe convention used in the supplied
    # plant IFC. Nominal mass follows the tabulated theoretical section area.
    pipe = re.fullmatch(r"(?:N(\d+(?:[.,]\d+)?)/(\d+(?:[.,]\d+)?)|O(\d+(?:[.,]\d+)?)\*(\d+(?:[.,]\d+)?))", name)
    if pipe:
        diameter = float((pipe.group(1) or pipe.group(3)).replace(",", "."))
        wall = float((pipe.group(2) or pipe.group(4)).replace(",", "."))
        if 0 < 2 * wall < diameter:
            area_mm2 = math.pi * (diameter**2 - (diameter - 2 * wall)**2) / 4
            return round(area_mm2 * 0.00785, 3), "tabela/rura wg wymiarów"
    return None, ""
