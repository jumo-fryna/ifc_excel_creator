from ifc_steel_generator.materials import material_names


class Fake:
    def __init__(self, **values): self.__dict__.update(values)


def test_recursive_material_names():
    nested=Fake(MaterialProfiles=[Fake(Material=Fake(Name="STEEL/S355JR"))])
    assert material_names(nested)==["STEEL/S355JR"]

