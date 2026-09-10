from __future__ import annotations


def material_names(material: object | None) -> list[str]:
    """Recursively extracts names from all common IFC material containers."""
    if material is None:
        return []
    result: list[str] = []
    name = getattr(material, "Name", None)
    if name:
        result.append(str(name))
    for attr in (
        "Material", "ForLayerSet", "ForProfileSet", "MaterialLayers",
        "MaterialProfiles", "MaterialConstituents", "Materials",
    ):
        child = getattr(material, attr, None)
        if child is None:
            continue
        children = child if isinstance(child, (list, tuple)) else [child]
        for item in children:
            result.extend(material_names(item))
    return list(dict.fromkeys(x for x in result if x))


def extract_material(element: object) -> str:
    for rel in getattr(element, "HasAssociations", []) or []:
        if hasattr(rel, "is_a") and rel.is_a("IfcRelAssociatesMaterial"):
            names = material_names(getattr(rel, "RelatingMaterial", None))
            if names:
                return " / ".join(names)
    return ""


def extract_profile_name(element: object) -> str:
    """Finds ProfileName in material profiles or swept solid representations."""
    for rel in getattr(element, "HasAssociations", []) or []:
        mat = getattr(rel, "RelatingMaterial", None)
        candidates = _walk_objects(mat)
        for obj in candidates:
            profile = getattr(obj, "Profile", None)
            value = getattr(profile, "ProfileName", None)
            if value:
                return str(value)
    representation = getattr(element, "Representation", None)
    for obj in _walk_objects(representation):
        swept = getattr(obj, "SweptArea", None)
        value = getattr(swept, "ProfileName", None)
        if value:
            return str(value)
    return ""


def _walk_objects(root: object | None, seen: set[int] | None = None):
    if root is None:
        return
    seen = seen or set()
    marker = id(root)
    if marker in seen:
        return
    seen.add(marker)
    yield root
    info = getattr(root, "get_info", lambda: {})()
    for key, value in info.items():
        if key in {"id", "type", "OwnerHistory"}:
            continue
        values = value if isinstance(value, (list, tuple)) else [value]
        for item in values:
            if hasattr(item, "is_a"):
                yield from _walk_objects(item, seen)

