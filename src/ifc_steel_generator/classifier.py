from __future__ import annotations

import re
from dataclasses import dataclass

from .models import ElementKind

PLATE_RE = re.compile(
    r"(?i)(?:^|[^A-Z0-9])(?:PL|BL)\s*(\d+(?:[.,]\d+)?)\s*(?:[*x×-])\s*(\d+(?:[.,]\d+)?)"
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
    # PL is an explicit plate convention and may correct an unusual exported
    # entity type. BL is parsed for dimensions, but does not override a beam,
    # column or member classification because it is also used for flat bars.
    explicit_plate = designation.strip().lstrip("*").upper().startswith("PL")
    if explicit_plate and parse_plate_designation(designation).thickness_mm is not None:
        return ElementKind.PLATE
    if entity in {"IFCBEAM", "IFCCOLUMN", "IFCMEMBER"} or has_profile:
        return ElementKind.PROFILE
    return ElementKind.UNCLASSIFIED
