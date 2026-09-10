from __future__ import annotations

from collections.abc import Mapping

ALIASES = {
    "length": ("length", "netlength"),
    "net_volume": ("netvolume", "net volume", "volume"),
    "gross_volume": ("grossvolume", "gross volume"),
    "net_weight": ("netweight", "net weight", "weight"),
    "outer_surface_area": ("outersurfacearea", "outer surface area", "surfacearea"),
    "net_area": ("netarea", "net area", "area"),
    "gross_area": ("grossarea", "gross area"),
    "thickness": ("thickness", "plate thickness", "nominalthickness"),
}


def flattened_properties(element: object) -> dict[str, object]:
    try:
        from ifcopenshell.util.element import get_psets
        psets = get_psets(element, psets_only=False, qtos_only=False)
    except Exception:
        psets = {}
    result: dict[str, object] = {}

    def visit(value: object) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key != "id" and not isinstance(child, Mapping):
                    result.setdefault(normalize(key), child)
                visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)

    visit(psets)
    return result


def normalize(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def number(props: Mapping[str, object], field: str) -> float | None:
    for alias in ALIASES[field]:
        value = props.get(normalize(alias))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        wrapped = getattr(value, "wrappedValue", None)
        if isinstance(wrapped, (int, float)):
            return float(wrapped)
    return None

