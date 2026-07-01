from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class Attribute:
    Value: object
    Type: Literal["string", "int", "float", "bool"]
    IsEnum: bool
    EnumName: Optional[str] = None   # store which enum this refers to

class Product:
    def __init__(self, UPC: str, name: str) -> None:
        self.UPC = Attribute(UPC, "string", False)
        self.Name = Attribute(name, "string", False)
        self.GenerateSKU()

    def AddAttribute(self, name: str, value: object,
                     type: Literal["string", "int", "float", "bool"],
                     isEnum: bool, enumName: Optional[str] = None):
        if hasattr(self, name):
            return
        setattr(self, name, Attribute(value, type, isEnum, enumName))
        self.GenerateSKU()

    def EditAttribute(self, name: str, value: object,
                      type: Literal["string", "int", "float", "bool"] = None,
                      isEnum: bool = None, enumName: Optional[str] = None):
        if not hasattr(self, name):
            return
        attr = getattr(self, name)
        setattr(self, name, Attribute(
            value,
            type or attr.Type,
            isEnum if isEnum is not None else attr.IsEnum,
            enumName if enumName is not None else attr.EnumName
        ))
        self.GenerateSKU()

    def RemoveAttribute(self, name: str):
        if hasattr(self, name):
            delattr(self, name)
            self.GenerateSKU()

    def GetAttributes(self):
        """Return list of (name, value, is_enum, enum_name, type) for all non‑built‑in attributes."""
        result = []
        for attr_name in dir(self):
            if attr_name.startswith("_") or attr_name in ("UPC", "Name", "SKU"):
                continue
            attr = getattr(self, attr_name)
            if isinstance(attr, Attribute):
                result.append((attr_name, attr.Value, attr.IsEnum, attr.EnumName, attr.Type))
        return result

    def GetAttributeEnumName(self, name: str) -> Optional[str]:
        if hasattr(self, name):
            attr = getattr(self, name)
            if isinstance(attr, Attribute):
                return attr.EnumName
        return None

    def GenerateSKU(self) -> None:
        self.SKU = Attribute(f"{self.UPC.Value}-{self.Name.Value}", "string", False)

    def Display(self):
        for attr, value in self.__dict__.items():
            print(attr, value)