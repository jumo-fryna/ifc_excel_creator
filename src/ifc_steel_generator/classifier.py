from __future__ import annotations

import re
from dataclasses import dataclass

from .models import ElementKind

PLATE_RE = re.compile(
    r"(?i)(?:^|[^A-Z0-9])(?:PL|BL)\s*(\d+(?:[.,]\d+)?)\s*(?:[*x×-])\s*(\d+(?:[.,]\d+)?)"
)
PLATE_SINGLE_RE = re.compile(r"(?i)^\s*(?:PL|BL)\s*(\d+(?:[.,]\d+)?)\s*$")
PROFILE_RE = re.compile(
    r"(?i)^\s*(?:HE[ABM]|IPE|IPN|UPE|UPN|UNP|SHS|RHS|CHS|HS|MSH|"
    r"L\s*\d|[NO]\s*\d|D\s*\d|HI\s*\d|WT[AC]\s*\d)"
)


@dataclass(frozen=True, slots=True)
class PlateDimensions:
    thickness_mm: float | None
    width_mm: float | None


def parse_plate_designation(value: str | None) -> PlateDimensions:
    if not value:
        return PlateDimensions(None, None)
    match = PLATE_RE.search(value.strip())
    if not match:
        single = PLATE_SINGLE_RE.search(value.strip())
        if single:
            return PlateDimensions(float(single.group(1).replace(",", ".")), None)
        return PlateDimensions(None, None)
    return PlateDimensions(
        float(match.group(1).replace(",", ".")),
        float(match.group(2).replace(",", ".")),
    )


def classify_element(ifc_type: str, designation: str, has_profile: bool = False) -> ElementKind:
    entity = ifc_type.upper()
    if entity in {"IFCFASTENER", "IFCMECHANICALFASTENER", "IFCREINFORCINGBAR"}:
        return ElementKind.UNCLASSIFIED
    if entity == "IFCPLATE":
        return ElementKind.PLATE
    # PL and BL are explicit plate/flat-bar conventions. Exporters sometimes
    # save them as IfcBeam or IfcMember, so the designation must take priority.
    explicit_plate = designation.strip().lstrip("*").upper().startswith(("PL", "BL"))
    if explicit_plate and parse_plate_designation(designation).thickness_mm is not None:
        return ElementKind.PLATE
    if entity in {"IFCBEAM", "IFCCOLUMN", "IFCMEMBER"} or has_profile:
        return ElementKind.PROFILE
    # Several plant-design exporters save fabricated beams, pipes and angles
    # as IfcDiscreteAccessory and put the real section name in ObjectType.
    if PROFILE_RE.search(designation or ""):
        return ElementKind.PROFILE
    return ElementKind.UNCLASSIFIED
