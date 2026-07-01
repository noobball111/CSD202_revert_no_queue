import copy
import re
import time
import random
import string
import datetime as dt
from imgui_bundle import imgui, hello_imgui, ImVec2, ImVec4, em_size
from typing import List, Optional, Set
from Classes.Product import Product
from Classes.Batch import Batch
from Classes.SearchEngine import SearchEngine
from Classes.Trie import Trie

# Debug logging
def debug_print(*args, **kwargs):
    print(f"[DEBUG {time.strftime('%M:%S')}]", *args, **kwargs)


# ---------- EnumEditor ----------
class EnumEditor:
    def __init__(self, productEnum):
        self.ProductEnum = productEnum
        self._newEnumName = ""
        self._newEnumType = "string"
        self._generateCount = 5

    def _GetEnumNoCollision(self):
        return ""

    def _GetUniquePlaceholder(self, enumName: str, enum_type: str):
        values = self.ProductEnum.GetValues(enumName)
        if enum_type == "int":
            candidate = 0
            while candidate in values:
                candidate += 1
            return candidate
        elif enum_type == "float":
            candidate = 0.0
            while candidate in values:
                candidate += 1.0
            return candidate
        else:  # string
            candidate = ""
            idx = 0
            while candidate in values:
                candidate = f"__{idx}"
                idx += 1
            return candidate

    def _GenerateRandomEnums(self, count: int):
        import random
        debug_print(f"Generating {count} random enums...")
        adjectives = ["Color", "Size", "Flavor", "Category", "Status", "Priority", "Type", "Grade", "Level"]
        values_pool = {
            "string": ["Red", "Green", "Blue", "Large", "Medium", "Small", "Sweet", "Sour", "High", "Low"],
            "int": [1, 2, 3, 5, 10, 20, 50, 100],
            "float": [1.0, 2.5, 3.14, 5.99, 10.5, 20.0]
        }
        for i in range(count):
            name = f"{random.choice(adjectives)}_{i+1}"
            typ = random.choice(["string", "int", "float"])
            if typ == "string":
                values = random.sample(values_pool["string"], k=min(4, len(values_pool["string"])))
            elif typ == "int":
                values = random.sample(values_pool["int"], k=min(4, len(values_pool["int"])))
            else:
                values = random.sample(values_pool["float"], k=min(4, len(values_pool["float"])))
            self.ProductEnum.NewEnum(name, typ)
            for val in values:
                self.ProductEnum.AddToEnum(name, val)
            debug_print(f"Created enum '{name}' with type '{typ}' and values {values}")

    def ShowEnums(self):
        for enumName in list(self.ProductEnum.EnumNames()):
            enum_type = self.ProductEnum.GetType(enumName)
            if imgui.collapsing_header(f"{enumName}  (type: {enum_type})"):
                imgui.push_id(enumName)
                values = self.ProductEnum.GetValues(enumName)

                for value in values:
                    imgui.push_id(str(value))
                    current_str = str(value)
                    changed, new_str = imgui.input_text("##Value", current_str)
                    if changed and imgui.is_item_deactivated_after_edit():
                        try:
                            if enum_type == "int":
                                new_val = int(new_str)
                            elif enum_type == "float":
                                new_val = float(new_str)
                            else:
                                new_val = new_str
                        except (ValueError, TypeError):
                            new_val = value
                        if new_val != value:
                            self.ProductEnum.RemoveFromEnum(enumName, value)
                            self.ProductEnum.AddToEnum(enumName, new_val)
                            debug_print(f"Enum '{enumName}': changed '{value}' -> '{new_val}'")
                    imgui.same_line()
                    if imgui.button("X"):
                        self.ProductEnum.RemoveFromEnum(enumName, value)
                        debug_print(f"Enum '{enumName}': removed '{value}'")
                    imgui.pop_id()

                if imgui.button("Add Option"):
                    placeholder = self._GetUniquePlaceholder(enumName, enum_type)
                    self.ProductEnum.AddToEnum(enumName, placeholder)
                    debug_print(f"Enum '{enumName}': added placeholder")
                imgui.pop_id()

    def Draw(self):
        imgui.push_id("EnumEditor")
        imgui.text("ENUMS:")
        imgui.same_line()
        if imgui.button("+"):
            imgui.open_popup("AddEnumPopup")

        imgui.same_line()
        imgui.text("Generate:")
        imgui.same_line()
        changed, self._generateCount = imgui.input_int("##enum_gen_count", self._generateCount)
        if changed:
            self._generateCount = max(1, self._generateCount)
        imgui.same_line()
        imgui.set_next_item_width(em_size(2))
        if imgui.button("Generate Enums"):
            self._GenerateRandomEnums(self._generateCount)

        if imgui.begin_popup("AddEnumPopup"):
            changed, self._newEnumName = imgui.input_text("##NewEnum", self._newEnumName)
            enum_types = ["string", "int", "float"]
            current_type_idx = enum_types.index(self._newEnumType) if self._newEnumType in enum_types else 0
            if imgui.begin_combo("Type", enum_types[current_type_idx]):
                for i, t in enumerate(enum_types):
                    if imgui.selectable(t, i == current_type_idx)[0]:
                        self._newEnumType = t
                    if i == current_type_idx:
                        imgui.set_item_default_focus()
                imgui.end_combo()
            if imgui.button("Create") and self._newEnumName != "" and not self.ProductEnum.EnumExists(self._newEnumName):
                self.ProductEnum.NewEnum(self._newEnumName, self._newEnumType)
                debug_print(f"Created enum '{self._newEnumName}' with type '{self._newEnumType}'")
                self._newEnumName = ""
                self._newEnumType = "string"
                imgui.close_current_popup()
            imgui.end_popup()

        imgui.separator()
        if imgui.begin_child("Enums", size=ImVec2(400, 300)):
            self.ShowEnums()
        imgui.end_child()
        imgui.pop_id()


# ---------- ProductEditor ----------
class ProductEditor:
    def __init__(self, storageManager, productEnum):
        self.ToBeProducts = []
        self.ProductErrors = {}
        self.StoredProductSearch = ""

        self.StorageManager = storageManager
        self.ProductEnum = productEnum

        self._productTemplate = {
            "UPC": {"Value": "", "Type": "string", "Essential": True},
            "Name": {"Value": "", "Type": "string", "Essential": True},
        }
        self._productBaseFieldName = "__field__"
        self._productBaseValue = {
            "string": "text",
            "int": 0,
            "float": 0,
            "bool": True,
        }

        self.searchEngine = SearchEngine(storageManager)
        self.searchQuery = ""
        self.searchSuggestions = []
        self.showSuggestions = False

        self._searching = False
        self._searchTime = 0.0
        self._searchResultsCount = 0
        self._suggestionIndex = 0
        self._justSelected = False
        self._enterConsumed = False
        self._prevSearchQuery = ""
        self._refocus = False

        self.filteredProducts = []
        self._productToDelete = None
        self._deletePopupOpen = False
        self.numProductsToGenerate = 5
        self.generate_random_fields = True
        self.generate_use_enums = True

        self._PrefillDemoProducts()

    # ---------- Demo and generation ----------
    def _PrefillDemoProducts(self):
        if self.StorageManager.Products:
            return
        debug_print("Prefilling demo products...")
        demo_data = [
            {"UPC": "12345", "Name": "Chocolate Milk", "Size": "XL", "Price": 4.99, "InStock": True},
            {"UPC": "67890", "Name": "Strawberry Yogurt", "Size": "M", "Price": 3.49, "InStock": False},
            {"UPC": "11111", "Name": "Vanilla Ice Cream", "Size": "L", "Price": 5.99, "InStock": True},
            {"UPC": "22222", "Name": "Blueberry Muffin", "Size": "S", "Price": 2.49, "InStock": True},
        ]
        for data in demo_data:
            upc = data["UPC"]
            name = data["Name"]
            product = Product(upc, name)
            for field, value in data.items():
                if field in ("UPC", "Name"):
                    continue
                typ = "string" if isinstance(value, str) else "int" if isinstance(value, int) else "float" if isinstance(value, float) else "bool"
                product.AddAttribute(field, value, typ, False)
            self.StorageManager.AddProduct(product)
        self.searchEngine.Rebuild()
        self._UpdateFilteredProducts()
        debug_print("Demo products added.")

    def _GenerateRandomProducts(self, count: int):
        debug_print(f"Generating {count} random products...")
        adjectives = ["Big", "Small", "Tasty", "Fresh", "Organic", "Premium", "Deluxe", "Classic", "Chewy", "Crispy"]
        nouns = ["Apple", "Banana", "Cherry", "Date", "Elderberry", "Fig", "Grape", "Honeydew", "Kiwi", "Lemon"]
        enum_names = list(self.ProductEnum.EnumNames()) if self.ProductEnum else []

        for i in range(count):
            name = f"{random.choice(adjectives)} {random.choice(nouns)} {i+1}"
            upc = ''.join(random.choices(string.digits, k=8))
            product = Product(upc, name)
            attrs = {
                "Size": random.choice(["S", "M", "L", "XL"]),
                "Price": round(random.uniform(1.0, 20.0), 2),
                "OnSale": random.choice([True, False])
            }
            for field, value in attrs.items():
                typ = "string" if isinstance(value, str) else "int" if isinstance(value, int) else "float" if isinstance(value, float) else "bool"
                product.AddAttribute(field, value, typ, False)

            if self.generate_use_enums and enum_names:
                enum_choices = random.sample(enum_names, k=min(2, len(enum_names)))
                for enum_name in enum_choices:
                    values = self.ProductEnum.GetValues(enum_name)
                    if not values:
                        continue
                    value = random.choice(values)
                    product.AddAttribute(enum_name, value, self.ProductEnum.GetType(enum_name), True, enum_name)

            if self.generate_random_fields:
                extra_fields = random.randint(1, 3)
                for j in range(extra_fields):
                    field_name = self._GetFieldNoCollision(product.__dict__)
                    value = random.choice(["Extra", "Option", "Value", 1, 2, 3, 4.5, False])
                    typ = "string" if isinstance(value, str) else "int" if isinstance(value, int) else "float" if isinstance(value, float) else "bool"
                    product.AddAttribute(field_name, value, typ, False)

            self.StorageManager.AddProduct(product)
        self.searchEngine.Rebuild()
        self._UpdateFilteredProducts()
        debug_print(f"Generated {count} products.")

    # ---------- Helpers ----------
    def _GetFieldNoCollision(self, tbProd):
        fieldName = self._productBaseFieldName
        idx = 0
        while fieldName in tbProd:
            idx += 1
            fieldName = f"{fieldName}{idx}"
        return fieldName

    def _FieldValue_String(self, data):
        changed, fieldValue = imgui.input_text("##Field value", data["Value"])
        if changed and imgui.is_item_deactivated_after_edit():
            data["Value"] = fieldValue
            return True, fieldValue
        return False, data["Value"]

    def _FieldValue_Int(self, data):
        changed, fieldValue = imgui.input_int("##Field value", data["Value"])
        if changed:
            data["Value"] = fieldValue
        return changed, fieldValue

    def _FieldValue_Float(self, data):
        changed, fieldValue = imgui.input_float("##Field value", data["Value"])
        if changed:
            data["Value"] = fieldValue
        return changed, fieldValue

    def _FieldValue_Bool(self, data):
        changed, fieldValue = imgui.checkbox("##Field value", data["Value"])
        if changed:
            data["Value"] = fieldValue
        return changed, fieldValue

    # ---------- Get used enums ----------
    def _GetUsedEnums(self, tbProd):
        used = set()
        for field, data in tbProd.items():
            if field in ("UPC", "Name"):
                continue
            if "Enum" in data:
                used.add(data["Enum"])
        return used

    def _GetUsedEnumsReal(self, product):
        used = set()
        for attr_name, value, is_enum, enum_name, attr_type in product.GetAttributes():
            if is_enum and enum_name:
                used.add(enum_name)
        return used

    # ---------- Validation ----------
    def ValidateProduct(self, tbProd) -> List[str]:
        errors = []
        if tbProd["UPC"]["Value"] == "":
            errors.append("UPC is required")
        if tbProd["Name"]["Value"] == "":
            errors.append("Name is required")

        for field, data in tbProd.items():
            if field in ("UPC", "Name"):
                continue
            if field.startswith(self._productBaseFieldName):
                errors.append(f"Field name is required (found placeholder)")
            if data["Type"] == "string" and data["Value"] == "":
                errors.append(f"Field '{field}' has empty value")

        upc = tbProd["UPC"]["Value"]
        if upc and upc in self.StorageManager.Products:
            errors.append("UPC already exists")
        for field, data in tbProd.items():
            if field in ("UPC", "Name"):
                continue
            if "Enum" in data:
                enum_name = data["Enum"]
                if data["Value"] not in self.ProductEnum.GetValues(enum_name):
                    errors.append(f"Field '{field}' has invalid enum value")
        return errors

    def _ValidateAll(self) -> bool:
        self.ProductErrors = {}
        all_valid = True
        for idx, tbProd in enumerate(self.ToBeProducts):
            errs = self.ValidateProduct(tbProd)
            if errs:
                all_valid = False
                self.ProductErrors[idx] = {"__general__": errs}
        return all_valid

    # ---------- Build ----------
    def BuildProduct(self, tbProd):
        product = Product(tbProd["UPC"]["Value"], tbProd["Name"]["Value"])
        for field, data in tbProd.items():
            if field in ("UPC", "Name"):
                continue
            is_enum = "Enum" in data
            enum_name = data.get("Enum", None)
            product.AddAttribute(field, data["Value"], data["Type"], is_enum, enum_name)
        return product

    # ---------- Save ----------
    def _SaveProducts(self):
        if not self.ToBeProducts:
            debug_print("No products to save.")
            return
        debug_print("Validating products before save...")
        if not self._ValidateAll():
            debug_print("Validation failed. Errors:", self.ProductErrors)
            imgui.open_popup("SaveErrorsPopup")
            return
        debug_print("All products valid. Saving...")
        for tbProd in self.ToBeProducts:
            product = self.BuildProduct(tbProd)
            self.StorageManager.AddProduct(product)
            debug_print(f"Saved product: {product.UPC.Value} - {product.Name.Value}")
        self.ToBeProducts.clear()
        self.ProductErrors.clear()
        self.searchEngine.Rebuild()
        self._UpdateFilteredProducts()
        debug_print("All products saved.")

    # ---------- Search / Filter ----------
    def _ParseQuery(self, query: str) -> tuple[List[str], List[str]]:
        include = []
        exclude = []
        for token in query.split():
            token = token.strip()
            if not token:
                continue
            if token.startswith('-'):
                exclude.append(token[1:].strip().lower())
            else:
                include.append(token.strip().lower())
        return include, exclude

    def _FilterProducts(self, query: str) -> List[Product]:
        if not query.strip():
            return list(self.StorageManager.Products.values())

        include, exclude = self._ParseQuery(query)
        include_sets = []
        for kw in include:
            s = self.StorageManager.GetProductsByKeyword(kw)
            if s:
                include_sets.append(s)

        if include_sets:
            result = min(include_sets, key=len)
            for s in include_sets:
                if s is not result:
                    result = result.intersection(s)
        else:
            result = set(self.StorageManager.Products.keys())

        for kw in exclude:
            s = self.StorageManager.GetProductsByKeyword(kw)
            if s:
                result = result.difference(s)

        return [self.StorageManager.Products[upc] for upc in result if upc in self.StorageManager.Products]

    def _UpdateFilteredProducts(self):
        self._searching = True
        start = time.perf_counter()
        self.filteredProducts = self._FilterProducts(self.searchQuery)
        self._searchTime = time.perf_counter() - start
        self._searchResultsCount = len(self.filteredProducts)
        self._searching = False

    # ---------- Show To‑Be Products ----------
    def ShowToBeProducts(self):
        for i, tbProd in enumerate(self.ToBeProducts):
            header_name = tbProd["Name"]["Value"] if tbProd["Name"]["Value"] != "" else f"Product {i}"
            is_error = i in self.ProductErrors

            if is_error:
                imgui.push_style_color(imgui.Col_.header, ImVec4(1.0, 0.3, 0.3, 1.0))
                imgui.push_style_color(imgui.Col_.header_hovered, ImVec4(1.0, 0.2, 0.2, 1.0))
            opened = imgui.collapsing_header(f"[{header_name}]")
            if is_error:
                imgui.pop_style_color(2)

            if opened:
                imgui.push_id(f"ToBeProduct{i}")

                if i in self.ProductErrors and imgui.is_item_hovered():
                    imgui.begin_tooltip()
                    for err in self.ProductErrors[i].get("__general__", []):
                        imgui.text(err)
                    imgui.end_tooltip()

                used_enums = self._GetUsedEnums(tbProd)

                for key, data in copy.copy(tbProd).items():
                    imgui.push_id(f"Field{key}")

                    imgui.set_next_item_width(em_size(6))
                    is_essential = data.get("Essential", False)
                    is_enum = "Enum" in data

                    if is_enum:
                        all_enums = list(self.ProductEnum.EnumNames())
                        available = [e for e in all_enums if e not in used_enums or e == data["Enum"]]
                        current_enum = data["Enum"]
                        if imgui.begin_combo("Field name", current_enum):
                            for enum_name in available:
                                if imgui.selectable(enum_name, enum_name == current_enum)[0]:
                                    if enum_name != current_enum:
                                        new_key = enum_name
                                        if new_key in tbProd and new_key != key:
                                            idx2 = 0
                                            while f"{new_key}_{idx2}" in tbProd:
                                                idx2 += 1
                                            new_key = f"{new_key}_{idx2}"
                                        data["Enum"] = enum_name
                                        values = self.ProductEnum.GetValues(enum_name)
                                        data["Value"] = values[0] if values else (0 if self.ProductEnum.GetType(enum_name) == "int" else (0.0 if self.ProductEnum.GetType(enum_name) == "float" else ""))
                                        tbProd[new_key] = data
                                        del tbProd[key]
                                        debug_print(f"Changed enum field from '{key}' to '{new_key}' referencing enum '{enum_name}'")
                                if enum_name == current_enum:
                                    imgui.set_item_default_focus()
                            imgui.end_combo()
                    else:
                        flags = imgui.InputTextFlags_.read_only if is_essential else 0
                        display_key = "" if self._productBaseFieldName in key else key
                        fieldKeyChanged, fieldKey = imgui.input_text("Field name", display_key, flags=flags)
                        if fieldKeyChanged and imgui.is_item_deactivated_after_edit():
                            if fieldKey and fieldKey not in tbProd:
                                tbProd[fieldKey] = data
                                del tbProd[key]
                                debug_print(f"Renamed field '{key}' -> '{fieldKey}'")

                    imgui.same_line()
                    imgui.set_next_item_width(em_size(6))

                    if is_enum:
                        enum_name = data["Enum"]
                        enum_values = self.ProductEnum.GetValues(enum_name)
                        current_val = data["Value"]
                        current_str = str(current_val)
                        selected_idx = -1
                        for idx_val, val in enumerate(enum_values):
                            if str(val) == current_str:
                                selected_idx = idx_val
                                break
                        if imgui.begin_combo("##Field value", current_str):
                            for idx_val, val in enumerate(enum_values):
                                val_str = str(val)
                                is_selected = (idx_val == selected_idx)
                                if imgui.selectable(val_str, is_selected)[0]:
                                    data["Value"] = val
                                    debug_print(f"Changed enum field '{key}' to '{val}'")
                                if is_selected:
                                    imgui.set_item_default_focus()
                            imgui.end_combo()
                    else:
                        field_type = data["Type"]
                        fieldValueFn = getattr(self, f"_FieldValue_{field_type.capitalize()}")
                        changed, _ = fieldValueFn(data)
                        if changed:
                            debug_print(f"Changed field '{key}' to '{data['Value']}'")

                    if not is_essential:
                        imgui.push_style_color(imgui.Col_.button, ImVec4(1.0, 0.0, 0.0, 1.0))
                        imgui.push_style_color(imgui.Col_.button_hovered, ImVec4(1.0, 0.3, 0.3, 1.0))
                        imgui.push_style_color(imgui.Col_.button_active, ImVec4(0.6, 0.0, 0.0, 1.0))
                        imgui.same_line()
                        if imgui.button("X"):
                            del_key = key
                            del tbProd[del_key]
                            debug_print(f"Deleted field '{del_key}'")
                        imgui.pop_style_color(3)

                    imgui.pop_id()

                if imgui.button("Add Field"):
                    imgui.set_next_window_pos(imgui.get_mouse_pos())
                    imgui.open_popup("AddFieldPopup")

                if imgui.begin_popup("AddFieldPopup"):
                    for type_name, default_val in self._productBaseValue.items():
                        if imgui.selectable(type_name, False)[0]:
                            new_key = self._GetFieldNoCollision(tbProd)
                            tbProd[new_key] = {
                                "Value": default_val,
                                "Type": type_name,
                                "Essential": False,
                            }
                            debug_print(f"Added field '{new_key}' of type '{type_name}'")
                    imgui.separator()
                    imgui.text("Enums")
                    available_enums = [e for e in self.ProductEnum.EnumNames() if e not in used_enums]
                    for enum_name in available_enums:
                        enum_type = self.ProductEnum.GetType(enum_name)
                        label = f"{enum_name}  (type: {enum_type})"
                        if imgui.selectable(label, False)[0]:
                            values = self.ProductEnum.GetValues(enum_name)
                            default_value = values[0] if values else (0 if enum_type == "int" else (0.0 if enum_type == "float" else ""))
                            new_key = enum_name
                            if new_key in tbProd:
                                idx2 = 0
                                while f"{new_key}_{idx2}" in tbProd:
                                    idx2 += 1
                                new_key = f"{new_key}_{idx2}"
                            tbProd[new_key] = {
                                "Value": default_value,
                                "Type": enum_type,
                                "Enum": enum_name,
                                "Essential": False,
                            }
                            debug_print(f"Added enum field '{new_key}' referencing '{enum_name}'")
                            imgui.close_current_popup()
                    imgui.end_popup()

                # Delete Product button
                imgui.same_line()
                imgui.push_style_color(imgui.Col_.button, ImVec4(1.0, 0.0, 0.0, 1.0))
                imgui.push_style_color(imgui.Col_.button_hovered, ImVec4(1.0, 0.3, 0.3, 1.0))
                imgui.push_style_color(imgui.Col_.button_active, ImVec4(0.6, 0.0, 0.0, 1.0))
                if imgui.button("Delete Product"):
                    debug_print(f"Pending delete button clicked for index {i}")
                    self._productToDelete = ("pending", i)
                imgui.pop_style_color(3)

                imgui.pop_id()

    # ---------- Show Real Products ----------
    def _DrawRealProduct(self, product):
        upc = product.UPC.Value
        name = product.Name.Value
        header_label = f"{upc} - {name}"

        opened = imgui.collapsing_header(header_label)

        if opened:
            imgui.push_id(f"RealProduct{upc}")

            essential_fields = [("UPC", upc, False, None, "string"), ("Name", name, False, None, "string")]
            attrs = product.GetAttributes()  # (name, value, is_enum, enum_name, type)

            used_enums = self._GetUsedEnumsReal(product)

            for field_name, field_value, is_enum, enum_name, attr_type in essential_fields + attrs:
                imgui.push_id(f"Field{field_name}")

                imgui.set_next_item_width(em_size(6))
                is_essential = field_name in ("UPC", "Name")

                # ---- Field name ----
                if is_enum and not is_essential:
                    all_enums = list(self.ProductEnum.EnumNames())
                    available = [e for e in all_enums if e not in used_enums or e == enum_name]
                    current_enum = enum_name
                    if imgui.begin_combo("Field name", current_enum):
                        for enum_candidate in available:
                            if imgui.selectable(enum_candidate, enum_candidate == current_enum)[0]:
                                if enum_candidate != current_enum:
                                    product.RemoveAttribute(field_name)
                                    new_values = self.ProductEnum.GetValues(enum_candidate)
                                    default_val = new_values[0] if new_values else (0 if self.ProductEnum.GetType(enum_candidate) == "int" else (0.0 if self.ProductEnum.GetType(enum_candidate) == "float" else ""))
                                    new_field_name = enum_candidate
                                    existing = [a[0] for a in product.GetAttributes() if a[0] != field_name]
                                    if new_field_name in existing:
                                        idx2 = 0
                                        while f"{new_field_name}_{idx2}" in existing:
                                            idx2 += 1
                                        new_field_name = f"{new_field_name}_{idx2}"
                                    product.AddAttribute(new_field_name, default_val, self.ProductEnum.GetType(enum_candidate), True, enum_candidate)
                                    debug_print(f"Real product {upc}: changed enum field from '{field_name}' to '{new_field_name}' referencing '{enum_candidate}'")
                            if enum_candidate == current_enum:
                                imgui.set_item_default_focus()
                        imgui.end_combo()
                else:
                    flags = imgui.InputTextFlags_.read_only if is_essential else 0
                    display_name = field_name
                    fieldKeyChanged, new_field_name = imgui.input_text("Field name", display_name, flags=flags)
                    if fieldKeyChanged and imgui.is_item_deactivated_after_edit():
                        if new_field_name and new_field_name != field_name and not is_essential:
                            if new_field_name not in [a[0] for a in product.GetAttributes()]:
                                old_val = field_value
                                old_is_enum = is_enum
                                old_enum_name = enum_name
                                old_type = attr_type
                                product.RemoveAttribute(field_name)
                                product.AddAttribute(new_field_name, old_val, old_type, old_is_enum, old_enum_name)
                                debug_print(f"Renamed attribute '{field_name}' -> '{new_field_name}' in product {upc}")
                            else:
                                debug_print(f"Rename failed: '{new_field_name}' already exists")

                imgui.same_line()
                imgui.set_next_item_width(em_size(6))

                # ---- Value widget ----
                if is_enum and not is_essential:
                    enum_name_for_field = enum_name or product.GetAttributeEnumName(field_name)
                    if enum_name_for_field:
                        enum_values = self.ProductEnum.GetValues(enum_name_for_field)
                        current_str = str(field_value)
                        selected_idx = -1
                        for idx_val, val in enumerate(enum_values):
                            if str(val) == current_str:
                                selected_idx = idx_val
                                break
                        if imgui.begin_combo("##Field value", current_str):
                            for idx_val, val in enumerate(enum_values):
                                val_str = str(val)
                                is_selected = (idx_val == selected_idx)
                                if imgui.selectable(val_str, is_selected)[0]:
                                    product.EditAttribute(field_name, val, isEnum=True, enumName=enum_name_for_field)
                                    debug_print(f"Changed enum '{field_name}' of {upc} to '{val}'")
                                if is_selected:
                                    imgui.set_item_default_focus()
                            imgui.end_combo()
                    else:
                        changed, new_val = imgui.input_text("##Field value", str(field_value))
                        if changed and imgui.is_item_deactivated_after_edit():
                            product.EditAttribute(field_name, new_val, isEnum=False)
                            debug_print(f"Changed '{field_name}' of {upc} to '{new_val}'")
                else:
                    if attr_type == "int":
                        changed, new_val = imgui.input_int("##Field value", field_value)
                        if changed:
                            product.EditAttribute(field_name, new_val, type="int")
                            debug_print(f"Changed int '{field_name}' of {upc} to {new_val}")
                    elif attr_type == "float":
                        changed, new_val = imgui.input_float("##Field value", field_value)
                        if changed:
                            product.EditAttribute(field_name, new_val, type="float")
                            debug_print(f"Changed float '{field_name}' of {upc} to {new_val}")
                    elif attr_type == "bool":
                        changed, new_val = imgui.checkbox("##Field value", field_value)
                        if changed:
                            product.EditAttribute(field_name, new_val, type="bool")
                            debug_print(f"Changed bool '{field_name}' of {upc} to {new_val}")
                    else:  # string
                        changed, new_val = imgui.input_text("##Field value", str(field_value))
                        if changed and imgui.is_item_deactivated_after_edit():
                            product.EditAttribute(field_name, new_val, type="string")
                            debug_print(f"Changed string '{field_name}' of {upc} to '{new_val}'")

                # ---- Delete button ----
                if not is_essential:
                    imgui.same_line()
                    imgui.push_style_color(imgui.Col_.button, ImVec4(1.0, 0.0, 0.0, 1.0))
                    imgui.push_style_color(imgui.Col_.button_hovered, ImVec4(1.0, 0.3, 0.3, 1.0))
                    imgui.push_style_color(imgui.Col_.button_active, ImVec4(0.6, 0.0, 0.0, 1.0))
                    if imgui.button("X"):
                        product.RemoveAttribute(field_name)
                        debug_print(f"Removed attribute '{field_name}' from {upc}")
                    imgui.pop_style_color(3)

                imgui.pop_id()

            # ---- Add Field ----
            if imgui.button("Add Field##real"):
                imgui.set_next_window_pos(imgui.get_mouse_pos())
                imgui.open_popup("AddRealFieldPopup")

            if imgui.begin_popup("AddRealFieldPopup"):
                for type_name, default_val in self._productBaseValue.items():
                    if imgui.selectable(type_name, False)[0]:
                        new_name = f"field_{len(product.GetAttributes())}"
                        product.AddAttribute(new_name, default_val, type_name, False)
                        debug_print(f"Added field '{new_name}' (type {type_name}) to {upc}")
                        imgui.close_current_popup()
                imgui.separator()
                imgui.text("Enums")
                used = self._GetUsedEnumsReal(product)
                available = [e for e in self.ProductEnum.EnumNames() if e not in used]
                for enum_name2 in available:
                    enum_type = self.ProductEnum.GetType(enum_name2)
                    label = f"{enum_name2}  (type: {enum_type})"
                    if imgui.selectable(label, False)[0]:
                        values = self.ProductEnum.GetValues(enum_name2)
                        default_value = values[0] if values else (0 if enum_type == "int" else (0.0 if enum_type == "float" else ""))
                        new_name = enum_name2
                        existing_attrs = [a[0] for a in product.GetAttributes()]
                        if new_name in existing_attrs:
                            idx2 = 0
                            while f"{new_name}_{idx2}" in existing_attrs:
                                idx2 += 1
                            new_name = f"{new_name}_{idx2}"
                        product.AddAttribute(new_name, default_value, enum_type, True, enum_name2)
                        debug_print(f"Added enum field '{new_name}' referencing '{enum_name2}' to {upc}")
                        imgui.close_current_popup()
                imgui.end_popup()

            # ---- Delete Product ----
            imgui.same_line()
            imgui.push_style_color(imgui.Col_.button, ImVec4(1.0, 0.0, 0.0, 1.0))
            imgui.push_style_color(imgui.Col_.button_hovered, ImVec4(1.0, 0.3, 0.3, 1.0))
            imgui.push_style_color(imgui.Col_.button_active, ImVec4(0.6, 0.0, 0.0, 1.0))
            if imgui.button("Delete Product"):
                debug_print(f"Real delete button clicked for product {upc}")
                self._productToDelete = ("real", upc)
            imgui.pop_style_color(3)

            imgui.pop_id()

    # ---------- Show Products with Search ----------
    def ShowProducts(self):
        # Refocus on the search bar if a suggestion was just selected
        if self._refocus:
            imgui.set_keyboard_focus_here()
            self._refocus = False

        # ---- Generate button ----
        imgui.text("Generate:")
        imgui.same_line()
        changed, self.numProductsToGenerate = imgui.input_int("##gen_count", self.numProductsToGenerate)
        if changed:
            self.numProductsToGenerate = max(1, self.numProductsToGenerate)
        imgui.same_line()
        imgui.set_next_item_width(em_size(2))
        if imgui.button("Generate Products"):
            self._GenerateRandomProducts(self.numProductsToGenerate)
        imgui.same_line()
        if imgui.button("Use Enums"):
            self.generate_use_enums = not self.generate_use_enums
        imgui.same_line()
        imgui.text("Enums: ")
        imgui.same_line()
        imgui.text_colored(ImVec4(0.2, 1.0, 0.2, 1.0) if self.generate_use_enums else ImVec4(1.0, 0.2, 0.2, 1.0), "ON" if self.generate_use_enums else "OFF")
        imgui.same_line()
        if imgui.button("Random Fields"):
            self.generate_random_fields = not self.generate_random_fields
        imgui.same_line()
        imgui.text("Fields: ")
        imgui.same_line()
        imgui.text_colored(ImVec4(0.2, 1.0, 0.2, 1.0) if self.generate_random_fields else ImVec4(1.0, 0.2, 0.2, 1.0), "ON" if self.generate_random_fields else "OFF")
        imgui.same_line()
        if self._searching:
            imgui.text("Searching...")
        else:
            if self.searchQuery.strip():
                imgui.text(f"{self._searchResultsCount} results in {self._searchTime:.4f}s")
            else:
                imgui.text(f"{len(self.filteredProducts)} products")
        imgui.separator()

        # ---- Search bar with enter_returns_true ----
        imgui.text("Search Products:")
        imgui.same_line()
        if self._refocus:
            imgui.set_keyboard_focus_here()
        flags = imgui.InputTextFlags_.enter_returns_true
        if self._refocus:
            flags |= imgui.InputTextFlags_.auto_select_all
        changed, self.searchQuery = imgui.input_text("##search", self.searchQuery, flags=flags)
        self._refocus = False

        # ---- Live suggestions ----
        is_active = imgui.is_item_active()
        if is_active and self.searchQuery != self._prevSearchQuery:
            self._prevSearchQuery = self.searchQuery
            debug_print(f"Live update: '{self.searchQuery}'")
            self._UpdateSuggestions()

        # ---- Enter handling ----
        if changed:
            # Enter was pressed
            if self.showSuggestions and len(self.searchSuggestions) > 0:
                selected_suggestion = self.searchSuggestions[self._suggestionIndex]
                debug_print(f"Selected suggestion via Enter: '{selected_suggestion}'")
                self._apply_suggestion(selected_suggestion)
            else:
                debug_print(f"Enter pressed (no suggestions), applying filter: '{self.searchQuery}'")
                self._UpdateFilteredProducts()
                self._suggestionIndex = 0
                imgui.set_keyboard_focus_here()

        # ---- Suggestions window ----
        input_rect_min = imgui.get_item_rect_min()
        input_rect_max = imgui.get_item_rect_max()

        if self.showSuggestions:
            pos = ImVec2(input_rect_min.x, input_rect_max.y)
            imgui.set_next_window_pos(pos)
            imgui.set_next_window_size(ImVec2(input_rect_max.x - input_rect_min.x, 200))
            window_flags = (
                imgui.WindowFlags_.no_title_bar |
                imgui.WindowFlags_.no_resize |
                imgui.WindowFlags_.no_move |
                imgui.WindowFlags_.no_focus_on_appearing |
                imgui.WindowFlags_.no_scrollbar
            )
            imgui.begin("##suggestions_window", None, window_flags)
            debug_print(f"Drawing suggestions window with {len(self.searchSuggestions)} items")

            win_pos = imgui.get_window_pos()
            win_size = imgui.get_window_size()
            win_rect_min = win_pos
            win_rect_max = win_pos + win_size

            for idx, sugg in enumerate(self.searchSuggestions):
                is_selected = (idx == self._suggestionIndex)
                imgui.selectable(sugg, is_selected)
                if imgui.is_item_clicked():
                    debug_print(f"Clicked suggestion: '{sugg}'")
                    self._apply_suggestion(sugg)
                if imgui.is_item_hovered():
                    self._suggestionIndex = idx

            # Close window if mouse clicked outside input and window
            if imgui.is_mouse_clicked(0):
                mouse_pos = imgui.get_mouse_pos()
                in_input = (input_rect_min.x <= mouse_pos.x <= input_rect_max.x and
                            input_rect_min.y <= mouse_pos.y <= input_rect_max.y)
                in_window = (win_rect_min.x <= mouse_pos.x <= win_rect_max.x and
                             win_rect_min.y <= mouse_pos.y <= win_rect_max.y)
                if not in_input and not in_window:
                    debug_print("Mouse clicked outside, closing suggestions")
                    self.showSuggestions = False
                    self._suggestionIndex = 0

            imgui.end()

        # ---- Keyboard navigation ----
        if is_active and self.showSuggestions and len(self.searchSuggestions) > 0:
            if self._suggestionIndex >= len(self.searchSuggestions):
                self._suggestionIndex = len(self.searchSuggestions) - 1
            if self._suggestionIndex < 0:
                self._suggestionIndex = 0

            if imgui.is_key_pressed(imgui.Key.up_arrow):
                self._suggestionIndex = (self._suggestionIndex - 1) % len(self.searchSuggestions)
                debug_print(f"Selection up: {self._suggestionIndex}")
            if imgui.is_key_pressed(imgui.Key.down_arrow):
                self._suggestionIndex = (self._suggestionIndex + 1) % len(self.searchSuggestions)
                debug_print(f"Selection down: {self._suggestionIndex}")

        # ---- Escape to close suggestions ----
        if self.showSuggestions and imgui.is_key_pressed(imgui.Key.escape):
            debug_print("Escape pressed, closing suggestions")
            self.showSuggestions = False
            self._suggestionIndex = 0
            imgui.set_keyboard_focus_here()

        # ---- Lost focus (deactivation) ----
        if imgui.is_item_deactivated_after_edit() and not self.showSuggestions:
            if self._justSelected:
                debug_print("Deactivation after selection, ignoring")
                self._justSelected = False
                self._enterConsumed = False
            else:
                debug_print(f"Lost focus, applying filter: '{self.searchQuery}'")
                self._UpdateFilteredProducts()
                self._suggestionIndex = 0

        # ---- Results ----
        if not self.filteredProducts:
            if self.searchQuery.strip():
                imgui.text("No products match your search.")
            else:
                imgui.text("No products stored.")
            return

        sorted_products = sorted(self.filteredProducts, key=lambda p: p.Name.Value)
        if imgui.begin_child("RealProductsChild", size=ImVec2(0, 0), child_flags=imgui.ChildFlags_.borders):
            clipper = imgui.ListClipper()
            clipper.begin(len(sorted_products))
            while clipper.step():
                for idx in range(clipper.display_start, clipper.display_end):
                    self._DrawRealProduct(sorted_products[idx])
            clipper.end()
        imgui.end_child()

    def _apply_suggestion(self, sugg):
        tokens = self.searchQuery.split()
        if not tokens:
            self.searchQuery = sugg
        else:
            tokens[-1] = sugg
            self.searchQuery = " ".join(tokens)

        self._UpdateFilteredProducts()
        self.showSuggestions = False
        self._suggestionIndex = 0
        self._justSelected = True
        self._enterConsumed = True
        self._prevSearchQuery = self.searchQuery
        self._refocus = True

    # ---------- Autocomplete ----------
    def _UpdateSuggestions(self):
        """Update autocomplete suggestions for the last token only."""
        if not self.searchQuery.strip():
            self.searchSuggestions = []
            self.showSuggestions = False
            debug_print("Empty query, clearing suggestions")
            return

        tokens = self.searchQuery.split()
        if not tokens:
            self.searchSuggestions = []
            self.showSuggestions = False
            return

        last_token = tokens[-1]
        debug_print(f"Last token: '{last_token}'")

        suggestions = []
        if ":" in last_token:
            raw_suggestions = self.searchEngine.Autocomplete(last_token)
            suggestions = [s for s in raw_suggestions if s != last_token][:10]
        else:
            field = None
            if len(tokens) >= 2:
                prev_token = tokens[-2]
                if prev_token.endswith(":") and prev_token[:-1] in self.searchEngine._fieldTries:
                    field = prev_token[:-1]
                    debug_print(f"Previous token is field prefix: '{field}'")
            if field:
                field_trie = self.searchEngine._fieldTries.get(field)
                if field_trie:
                    raw_suggestions = field_trie.Find(last_token)
                    suggestions = [f"{field}:{v}" for v in raw_suggestions if v and v != last_token][:10]
            else:
                raw_suggestions = self.searchEngine.GetSuggestions(last_token)
                for sugg in raw_suggestions:
                    if sugg != last_token:
                        suggestions.append(sugg)
                    if len(suggestions) >= 10:
                        break

        self.searchSuggestions = suggestions[:10]
        self.showSuggestions = bool(self.searchSuggestions)
        debug_print(f"Suggestions: {self.searchSuggestions} (show={self.showSuggestions})")

    # ---------- Main Draw ----------
    def Draw(self):
        imgui.push_id("ProductEditor")

        imgui.text("PRODUCTS: ")
        imgui.same_line()
        if imgui.button("+"):
            self.ToBeProducts.append(copy.deepcopy(self._productTemplate))
            debug_print("Added new product template")

        imgui.same_line()
        if imgui.button("Save / Submit"):
            self._SaveProducts()

        if imgui.begin_popup("SaveErrorsPopup"):
            imgui.text("Validation errors occurred. Please fix them.")
            for idx, err_dict in self.ProductErrors.items():
                imgui.text(f"Product {idx}:")
                for err in err_dict.get("__general__", []):
                    imgui.bullet_text(err)
            if imgui.button("OK"):
                imgui.close_current_popup()
            imgui.end_popup()

        # --- Delete confirmation popup ---
        if self._productToDelete is not None:
            imgui.open_popup("DeleteConfirmPopup")
            self._deletePopupOpen = True

        opened = imgui.begin_popup_modal("DeleteConfirmPopup", None, imgui.WindowFlags_.always_auto_resize)[0]
        if opened:
            debug_print("Delete confirmation popup opened")
            if self._productToDelete:
                if self._productToDelete[0] == "pending":
                    idx = self._productToDelete[1]
                    imgui.text(f"Delete pending product #{idx}?")
                else:
                    upc = self._productToDelete[1]
                    imgui.text(f"Delete real product '{upc}'?")
                if imgui.button("Yes"):
                    debug_print("Delete confirmed")
                    if self._productToDelete[0] == "pending":
                        del self.ToBeProducts[self._productToDelete[1]]
                        debug_print(f"Deleted pending product at index {self._productToDelete[1]}")
                    else:
                        upc = self._productToDelete[1]
                        if upc in self.StorageManager.Products:
                            product = self.StorageManager.Products[upc]
                            self.StorageManager.RemoveProduct(product)
                            debug_print(f"Deleted real product '{upc}'")
                    self._productToDelete = None
                    self._deletePopupOpen = False
                    self.searchEngine.Rebuild()
                    self._UpdateFilteredProducts()
                    imgui.close_current_popup()
                imgui.same_line()
                if imgui.button("No"):
                    debug_print("Delete cancelled")
                    self._productToDelete = None
                    self._deletePopupOpen = False
                    imgui.close_current_popup()
            else:
                imgui.close_current_popup()
            imgui.end_popup()
        else:
            if self._productToDelete is not None and self._deletePopupOpen:
                debug_print("Popup was closed without confirmation, clearing delete request")
                self._productToDelete = None
                self._deletePopupOpen = False

        imgui.separator()

        imgui.columns(2, "ProductEditorColumns", True)
        imgui.set_column_width(0, imgui.get_window_width() * 0.45)

        if imgui.begin_child("ToBeProductsChild", size=ImVec2(0, 0), child_flags=imgui.ChildFlags_.borders):
            if not self.ToBeProducts:
                imgui.text("No pending products.")
            else:
                self.ShowToBeProducts()
        imgui.end_child()

        imgui.next_column()

        if imgui.begin_child("RealProductsChildMain", size=ImVec2(0, 0), child_flags=imgui.ChildFlags_.borders):
            self.ShowProducts()
        imgui.end_child()

        imgui.columns(1)
        imgui.pop_id()


# ---------- BatchEditor ----------
class BatchEditor:
    def __init__(self, storageManager, prefill_demo: bool = True):
        self.StorageManager = storageManager
        self.searchEngine = SearchEngine(storageManager, index_type='batch')
        self.ToBeBatches = []
        self.BatchErrors = {}
        self.searchQuery = ""
        self.searchSuggestions = []
        self.showSuggestions = False
        self.filteredBatchIDs = []
        self._searching = False
        self._searchTime = 0.0
        self._searchResultsCount = 0
        self._suggestionIndex = 0
        self._justSelected = False
        self._refocus = False
        self._prevSearchQuery = ""

        self._batchTemplate = {
            "ProductUPC": "",
            "Amount": 1,
            "State": "Good",
            "HasExpiration": False,
            "ExpirationDate": "",
        }
        self._batchToDelete = None
        self._productFilter = ""
        self._generateBatchCount = 5

        if prefill_demo:
            self._prefillDemoBatches()

    # ---------- Index maintenance ----------
    def _reindexBatch(self, batch):
        self.StorageManager._removeBatch(batch)
        self.StorageManager._indexBatch(batch)
        self.searchEngine.Rebuild()

    # ---------- Demo ----------
    def _prefillDemoBatches(self):
        if self.StorageManager.BatchByID:
            return
        debug_print("Prefilling demo batches...")
        demo = [
            {"UPC": "12345", "Amount": 10, "State": "Good", "Expiration": "2025-12-31"},
            {"UPC": "67890", "Amount": 5, "State": "ToBeReviewed", "Expiration": ""},
            {"UPC": "11111", "Amount": 20, "State": "Good", "Expiration": "2025-06-15"},
            {"UPC": "22222", "Amount": 3, "State": "Good", "Expiration": ""},
        ]
        for data in demo:
            batch = Batch(data["UPC"], data["Amount"], data["State"])
            if data["Expiration"]:
                try:
                    batch.SetExpirationDate(dt.datetime.strptime(data["Expiration"], "%Y-%m-%d"))
                except ValueError:
                    pass
            self.StorageManager.AddBatch(batch)
        self.searchEngine.Rebuild()
        self._updateFilteredBatches()
        debug_print("Demo batches added.")

    # ---------- Generation ----------
    def _GenerateRandomBatches(self, count: int):
        import random
        debug_print(f"Generating {count} random batches...")
        if not self.StorageManager.Products:
            debug_print("No products available to generate batches for.")
            return
        upc_list = list(self.StorageManager.Products.keys())
        states = ["Good", "ToBeReviewed"]
        for i in range(count):
            upc = random.choice(upc_list)
            amount = random.randint(1, 100)
            state = random.choice(states)
            batch = Batch(upc, amount, state)
            if random.random() > 0.5:
                delta = dt.timedelta(days=random.randint(1, 365))
                batch.SetExpirationDate(dt.datetime.now() + delta)
            self.StorageManager.AddBatch(batch)
        self.searchEngine.Rebuild()
        self._updateFilteredBatches()
        debug_print(f"Generated {count} batches.")

    # ---------- Validation (pending batches) ----------
    def _validateBatch(self, tbBatch: dict) -> List[str]:
        errors = []
        upc = tbBatch["ProductUPC"].strip()
        if not upc:
            errors.append("Product UPC is required")
        elif upc not in self.StorageManager.Products:
            errors.append(f"Product UPC '{upc}' does not exist")
        if tbBatch["Amount"] < 1:
            errors.append("Amount must be at least 1")
        if tbBatch["State"] not in ("Good", "ToBeReviewed"):
            errors.append("State must be Good or ToBeReviewed")
        if tbBatch["HasExpiration"]:
            if not tbBatch["ExpirationDate"].strip():
                errors.append("Expiration date is required")
            else:
                try:
                    exp_date = dt.datetime.strptime(tbBatch["ExpirationDate"], "%Y-%m-%d")
                    if exp_date < dt.datetime.now():
                        errors.append("Expiration date cannot be in the past")
                except ValueError:
                    errors.append("Expiration date must be in YYYY-MM-DD format")
        return errors

    def _validateAll(self) -> bool:
        self.BatchErrors = {}
        all_valid = True
        for idx, tbBatch in enumerate(self.ToBeBatches):
            errs = self._validateBatch(tbBatch)
            if errs:
                all_valid = False
                self.BatchErrors[idx] = errs
        return all_valid

    def _buildBatch(self, tbBatch):
        debug_print(f"_buildBatch: Creating batch for UPC={tbBatch['ProductUPC']}")
        batch = Batch(tbBatch["ProductUPC"], tbBatch["Amount"], tbBatch["State"])
        if tbBatch["HasExpiration"] and tbBatch["ExpirationDate"].strip():
            try:
                exp_date = dt.datetime.strptime(tbBatch["ExpirationDate"], "%Y-%m-%d")
                batch.ExpirationDate = exp_date
                debug_print(f"  -> Set expiration to {exp_date}")
            except ValueError as e:
                debug_print(f"  -> Failed to parse expiration date: {e}")
        else:
            debug_print("  -> No expiration set")
        return batch

    # ---------- Save pending batches ----------
    def _saveBatches(self):
        if not self.ToBeBatches:
            debug_print("No batches to save.")
            return
        debug_print("Validating batches...")
        if not self._validateAll():
            debug_print("Validation failed. Errors:", self.BatchErrors)
            imgui.open_popup("BatchSaveErrorsPopup")
            return
        debug_print("All batches valid. Saving...")
        for tbBatch in self.ToBeBatches:
            batch = self._buildBatch(tbBatch)
            debug_print(f"About to add batch: ID={batch.BatchID}, ExpirationDate={batch.ExpirationDate}")
            self.StorageManager.AddBatch(batch)
            debug_print(f"Saved batch {batch.BatchID} for product {batch.ProductUPC}")
        self.ToBeBatches.clear()
        self.BatchErrors.clear()
        self.searchEngine.Rebuild()
        self._updateFilteredBatches()
        debug_print("All batches saved.")

    # ---------- Search ----------
    def _updateFilteredBatches(self):
        self._searching = True
        start = time.perf_counter()
        self.filteredBatchIDs = self._filterBatches(self.searchQuery)
        self._searchTime = time.perf_counter() - start
        self._searchResultsCount = len(self.filteredBatchIDs)
        self._searching = False

    def _filterBatches(self, query: str) -> List[int]:
        if not query.strip():
            return list(self.StorageManager.BatchByID.keys())

        include = []
        exclude = []
        for token in query.split():
            token = token.strip()
            if not token:
                continue
            if token.startswith('-'):
                exclude.append(token[1:].strip().lower())
            else:
                include.append(token.strip().lower())

        include_sets = []
        for kw in include:
            s = self._getBatchIDsForKeyword(kw)
            include_sets.append(s)

        if include_sets:
            if any(len(s) == 0 for s in include_sets):
                return []
            result = min(include_sets, key=len)
            for s in include_sets:
                if s is not result:
                    result = result.intersection(s)
        else:
            result = set(self.StorageManager.BatchByID.keys())

        for kw in exclude:
            s = self._getBatchIDsForKeyword(kw)
            if s:
                result = result.difference(s)

        return sorted(result)

    def _getBatchIDsForKeyword(self, keyword: str) -> Set[int]:
        keyword = keyword.lower().strip()
        batch_ids = set()

        # Numeric comparisons like amount>20 or amount<=10
        numeric_match = re.match(r"^([a-zA-Z_][\w]*)\s*(<=|>=|<|>|==|=)\s*(.+)$", keyword)
        if numeric_match:
            field, op, raw_value = numeric_match.groups()
            field = field.lower()
            raw_value = raw_value.strip()
            try:
                if field == "amount":
                    value = int(raw_value)
                elif field in ("importeddate", "expirationdate"):
                    # Support ISO date comparisons for batch date fields.
                    value = dt.datetime.fromisoformat(raw_value).timestamp()
                else:
                    value = float(raw_value)
            except (ValueError, TypeError):
                return set()
            return self.StorageManager.GetBatchIDsByNumericComparison(field, op, value)

        # Exact numeric field match using colon syntax
        field_exact_match = re.match(r"^([a-zA-Z_][\w]*):(.*)$", keyword)
        if field_exact_match:
            field, raw_value = field_exact_match.groups()
            field = field.lower()
            raw_value = raw_value.strip()
            if field == "amount":
                try:
                    value = int(raw_value)
                    return self.StorageManager.GetBatchIDsByNumericComparison(field, "=", value)
                except ValueError:
                    pass
            if field in ("importeddate", "expirationdate"):
                try:
                    value = dt.datetime.fromisoformat(raw_value).timestamp()
                    return self.StorageManager.GetBatchIDsByNumericComparison(field, "=", value)
                except ValueError:
                    pass

        if keyword in self.StorageManager.BatchKeywordIndex:
            batch_ids.update(self.StorageManager.BatchKeywordIndex[keyword])

        upcs = self.StorageManager.GetProductsByKeyword(keyword)
        for upc in upcs:
            if upc in self.StorageManager.ProductToBatchIndex:
                batch_ids.update(self.StorageManager.ProductToBatchIndex[upc])

        return batch_ids

    def _applySuggestion(self, sugg):
        tokens = self.searchQuery.split()
        if not tokens:
            self.searchQuery = sugg
        else:
            tokens[-1] = sugg
            self.searchQuery = " ".join(tokens)

        self._updateFilteredBatches()
        self.showSuggestions = False
        self._suggestionIndex = 0
        self._justSelected = True
        self._refocus = True

    # ---------- UI: Real Batches (editable) ----------
    def _drawBatch(self, batch):
        batch_id = batch.BatchID
        expired = batch.ExpirationDate is not None and batch.ExpirationDate < dt.datetime.now()
        low_amount = batch.Amount < 10

        if expired or low_amount:
            imgui.push_style_color(imgui.Col_.text, ImVec4(1.0, 0.1, 0.1, 1.0))

        imgui.push_id(f"batch_{batch_id}")

        imgui.text(f"ID: {batch_id}")
        imgui.same_line()

        product = self.StorageManager.Products.get(batch.ProductUPC)
        product_name = product.Name.Value if product else "Unknown"
        imgui.text(f"UPC: {batch.ProductUPC} ({product_name})")
        imgui.same_line()

        # Amount – em_size(8)
        imgui.set_next_item_width(em_size(8))
        changed, amount = imgui.input_int("Amount", batch.Amount)
        if changed:
            batch.Amount = max(1, amount)
            self._reindexBatch(batch)
            self._updateFilteredBatches()

        imgui.same_line()
        imgui.text(f"Imported: {batch.ImportedDate.strftime('%Y-%m-%d')}")

        if batch.ExpirationDate:
            imgui.same_line()
            imgui.text(f"Expiration: {batch.ExpirationDate.strftime('%Y-%m-%d')}")
        else:
            imgui.same_line()
            imgui.text("Expiration: None")

        if expired or low_amount:
            imgui.pop_style_color()

        imgui.same_line()

        # State – width 150px
        imgui.set_next_item_width(150.0)
        states = ["Good", "ToBeReviewed"]
        current_idx = states.index(batch.State) if batch.State in states else 0
        if imgui.begin_combo("State", states[current_idx]):
            for idx, state in enumerate(states):
                if imgui.selectable(state, idx == current_idx)[0]:
                    batch.State = state
                    self._reindexBatch(batch)
                    self._updateFilteredBatches()
            imgui.end_combo()

        imgui.same_line()

        # Expiration checkbox – directly modify batch.ExpirationDate
        has_exp = batch.ExpirationDate is not None
        changed, has_exp = imgui.checkbox("Has Expiration", has_exp)
        if changed:
            debug_print(f"Toggled expiration for batch {batch_id}: {has_exp}")
            if has_exp:
                batch.ExpirationDate = dt.datetime.now() + dt.timedelta(days=30)
                debug_print(f"  Set expiration to {batch.ExpirationDate}")
            else:
                batch.ExpirationDate = None
            self._reindexBatch(batch)
            self._updateFilteredBatches()

        if batch.ExpirationDate:
            current_date = batch.ExpirationDate.strftime("%Y-%m-%d")
            imgui.same_line()
            imgui.set_next_item_width(100.0)
            changed, new_date_str = imgui.input_text("Expiration", current_date)
            if changed and imgui.is_item_deactivated_after_edit():
                try:
                    new_date = dt.datetime.strptime(new_date_str, "%Y-%m-%d")
                    batch.ExpirationDate = new_date
                    self._reindexBatch(batch)
                    self._updateFilteredBatches()
                except ValueError:
                    pass

        imgui.same_line()
        if imgui.button(f"Delete##{batch_id}"):
            debug_print(f"Delete button clicked for batch {batch_id}")
            self._batchToDelete = ("real", batch_id)
            imgui.open_popup("DeleteBatchConfirmPopup")

        imgui.pop_id()

    def ShowBatches(self):
        # ---- Search bar with autocomplete ----
        imgui.text("Search Batches:")
        imgui.same_line()

        if self._refocus:
            imgui.set_keyboard_focus_here()
        flags = imgui.InputTextFlags_.enter_returns_true
        if self._refocus:
            flags |= imgui.InputTextFlags_.auto_select_all

        imgui.set_next_item_width(em_size(15))
        changed, self.searchQuery = imgui.input_text("##batch_search", self.searchQuery, flags=flags)
        self._refocus = False

        is_active = imgui.is_item_active()
        if is_active and self.searchQuery != self._prevSearchQuery:
            self._prevSearchQuery = self.searchQuery
            debug_print(f"Live batch search: '{self.searchQuery}'")
            self._updateSuggestions()

        if changed:
            if self.showSuggestions and len(self.searchSuggestions) > 0:
                selected_suggestion = self.searchSuggestions[self._suggestionIndex]
                debug_print(f"Selected suggestion via Enter: '{selected_suggestion}'")
                self._applySuggestion(selected_suggestion)
            else:
                debug_print(f"Enter pressed (no suggestions), applying filter: '{self.searchQuery}'")
                self._updateFilteredBatches()
                self._suggestionIndex = 0
                imgui.set_keyboard_focus_here()

        # ---- Suggestions popup ----
        input_rect_min = imgui.get_item_rect_min()
        input_rect_max = imgui.get_item_rect_max()

        if self.showSuggestions:
            pos = ImVec2(input_rect_min.x, input_rect_max.y)
            imgui.set_next_window_pos(pos)
            imgui.set_next_window_size(ImVec2(input_rect_max.x - input_rect_min.x, 200))
            window_flags = (
                imgui.WindowFlags_.no_title_bar |
                imgui.WindowFlags_.no_resize |
                imgui.WindowFlags_.no_move |
                imgui.WindowFlags_.no_focus_on_appearing |
                imgui.WindowFlags_.no_scrollbar
            )
            imgui.begin("##batch_suggestions_window", None, window_flags)
            debug_print(f"Drawing suggestions with {len(self.searchSuggestions)} items")
            for idx, sugg in enumerate(self.searchSuggestions):
                is_selected = (idx == self._suggestionIndex)
                imgui.selectable(sugg, is_selected)
                if imgui.is_item_clicked():
                    debug_print(f"Clicked suggestion: '{sugg}'")
                    self._applySuggestion(sugg)
                if imgui.is_item_hovered():
                    self._suggestionIndex = idx

            win_pos = imgui.get_window_pos()
            win_size = imgui.get_window_size()
            win_rect_min = win_pos
            win_rect_max = win_pos + win_size

            if imgui.is_mouse_clicked(0):
                mouse_pos = imgui.get_mouse_pos()
                in_input = (
                    input_rect_min.x <= mouse_pos.x <= input_rect_max.x and
                    input_rect_min.y <= mouse_pos.y <= input_rect_max.y
                )
                in_window = (
                    win_rect_min.x <= mouse_pos.x <= win_rect_max.x and
                    win_rect_min.y <= mouse_pos.y <= win_rect_max.y
                )
                if not in_input and not in_window:
                    debug_print("Mouse clicked outside batch suggestions, closing suggestions")
                    self.showSuggestions = False
                    self._suggestionIndex = 0

            imgui.end()

        # ---- Keyboard navigation ----
        if is_active and self.showSuggestions and len(self.searchSuggestions) > 0:
            if self._suggestionIndex >= len(self.searchSuggestions):
                self._suggestionIndex = len(self.searchSuggestions) - 1
            if self._suggestionIndex < 0:
                self._suggestionIndex = 0

            if imgui.is_key_pressed(imgui.Key.up_arrow):
                self._suggestionIndex = (self._suggestionIndex - 1) % len(self.searchSuggestions)
                debug_print(f"Selection up: {self._suggestionIndex}")
            if imgui.is_key_pressed(imgui.Key.down_arrow):
                self._suggestionIndex = (self._suggestionIndex + 1) % len(self.searchSuggestions)
                debug_print(f"Selection down: {self._suggestionIndex}")

        # ---- Escape to close ----
        if self.showSuggestions and imgui.is_key_pressed(imgui.Key.escape):
            debug_print("Escape pressed, closing suggestions")
            self.showSuggestions = False
            self._suggestionIndex = 0
            imgui.set_keyboard_focus_here()

        # ---- Lost focus ----
        if imgui.is_item_deactivated_after_edit() and not self.showSuggestions:
            if self._justSelected:
                debug_print("Deactivation after selection, ignoring")
                self._justSelected = False
            else:
                debug_print(f"Lost focus, applying filter: '{self.searchQuery}'")
                self._updateFilteredBatches()
                self._suggestionIndex = 0

        imgui.same_line()
        if self._searching:
            imgui.text("Searching...")
        else:
            if self.searchQuery.strip():
                imgui.text(f"{self._searchResultsCount} results in {self._searchTime:.4f}s")
            else:
                imgui.text(f"{len(self.filteredBatchIDs)} batches")
        imgui.same_line()
        if imgui.button("Optimize Database"):
            self.StorageManager.OptimizeDatabase()
            self.searchEngine.Rebuild()
            self._updateFilteredBatches()
            debug_print("Database optimized.")
        imgui.same_line()
        if imgui.button("Save Database"):
            saved = self.StorageManager.SaveDatabase("data.txt")
            debug_print(f"Save Database: {'success' if saved else 'failed'}")
        imgui.separator()

        if not self.filteredBatchIDs:
            if self.searchQuery.strip():
                imgui.text("No batches match your search.")
            else:
                imgui.text("No batches stored.")
            return

        if imgui.begin_child("BatchList", size=ImVec2(0, 0), child_flags=imgui.ChildFlags_.borders):
            clipper = imgui.ListClipper()
            clipper.begin(len(self.filteredBatchIDs))
            while clipper.step():
                for idx in range(clipper.display_start, clipper.display_end):
                    batch_id = self.filteredBatchIDs[idx]
                    batch = self.StorageManager.GetBatch(batch_id)
                    if batch:
                        self._drawBatch(batch)
            clipper.end()
            imgui.end_child()

        self._showDeletePopup()

    def _updateSuggestions(self):
        if not self.searchQuery.strip():
            self.searchSuggestions = []
            self.showSuggestions = False
            debug_print("Empty query, clearing suggestions")
            return

        tokens = self.searchQuery.split()
        last_token = tokens[-1] if tokens else ""
        suggestions = []
        if last_token:
            raw = self.searchEngine.Autocomplete(last_token)
            for sugg in raw:
                if sugg != last_token:
                    suggestions.append(sugg)
            self.searchSuggestions = suggestions[:10]
        self.showSuggestions = bool(self.searchSuggestions)

    # ---------- UI: Pending Batches ----------
    def ShowToBeBatches(self):
        if imgui.button("+ Add Batch"):
            self.ToBeBatches.append(copy.deepcopy(self._batchTemplate))

        imgui.same_line()
        if imgui.button("Save Batches"):
            self._saveBatches()

        imgui.separator()

        if not self.ToBeBatches:
            imgui.text("No pending batches.")
            return

        if imgui.begin_child("PendingBatchesChild", size=ImVec2(0, 300), child_flags=imgui.ChildFlags_.borders):
            i = 0
            while i < len(self.ToBeBatches):
                tbBatch = self.ToBeBatches[i]
                header = f"Batch {i+1} (UPC: {tbBatch['ProductUPC'] if tbBatch['ProductUPC'] else '??? '})"
                if i in self.BatchErrors:
                    imgui.push_style_color(imgui.Col_.header, ImVec4(1.0, 0.3, 0.3, 1.0))
                opened = imgui.collapsing_header(header)
                if i in self.BatchErrors:
                    imgui.pop_style_color()

                if opened:
                    imgui.push_id(f"tbBatch{i}")

                    if i in self.BatchErrors and imgui.is_item_hovered():
                        imgui.begin_tooltip()
                        for err in self.BatchErrors[i]:
                            imgui.text(err)
                        imgui.end_tooltip()

                    all_upcs = list(self.StorageManager.Products.keys())
                    product_options = []
                    for upc in all_upcs:
                        product = self.StorageManager.Products[upc]
                        product_options.append(f"{upc} - {product.Name.Value}")

                    current_upc = tbBatch["ProductUPC"]
                    current_display = ""
                    for opt in product_options:
                        if opt.startswith(current_upc):
                            current_display = opt
                            break

                    if imgui.begin_combo("Product UPC", current_display):
                        changed, self._productFilter = imgui.input_text("Filter", self._productFilter)
                        for idx, opt in enumerate(product_options):
                            if self._productFilter.lower() not in opt.lower():
                                continue
                            if imgui.selectable(opt, opt == current_display)[0]:
                                upc = opt.split(" - ")[0]
                                tbBatch["ProductUPC"] = upc
                                if i in self.BatchErrors:
                                    self.BatchErrors[i] = []
                        imgui.end_combo()

                    imgui.set_next_item_width(em_size(8))
                    changed, amount = imgui.input_int("Amount", tbBatch["Amount"])
                    if changed:
                        tbBatch["Amount"] = max(1, amount)

                    imgui.set_next_item_width(150.0)
                    states = ["Good", "ToBeReviewed"]
                    current_idx2 = states.index(tbBatch["State"]) if tbBatch["State"] in states else 0
                    if imgui.begin_combo("State", states[current_idx2]):
                        for idx, state in enumerate(states):
                            if imgui.selectable(state, idx == current_idx2)[0]:
                                tbBatch["State"] = state
                        imgui.end_combo()

                    changed, has_exp = imgui.checkbox("Has Expiration", tbBatch["HasExpiration"])
                    if changed:
                        tbBatch["HasExpiration"] = has_exp
                    if tbBatch["HasExpiration"]:
                        imgui.set_next_item_width(100.0)
                        changed, exp_str = imgui.input_text("Expiration Date (YYYY-MM-DD)", tbBatch["ExpirationDate"])
                        if changed:
                            tbBatch["ExpirationDate"] = exp_str

                    if imgui.button("Delete"):
                        debug_print(f"Delete pending batch at index {i}")
                        del self.ToBeBatches[i]
                        self.BatchErrors.pop(i, None)
                        imgui.pop_id()
                        continue

                    imgui.pop_id()
                i += 1

            imgui.end_child()

        if imgui.begin_popup("BatchSaveErrorsPopup"):
            imgui.text("Validation errors occurred. Please fix them:")
            for idx, errs in self.BatchErrors.items():
                imgui.text(f"Batch {idx+1}:")
                for err in errs:
                    imgui.bullet_text(err)
            if imgui.button("OK"):
                imgui.close_current_popup()
            imgui.end_popup()

        self._showDeletePopup()

    # ---------- Shared delete confirmation popup ----------
    def _showDeletePopup(self):
        if self._batchToDelete is not None:
            imgui.open_popup("DeleteBatchConfirmPopup")
        if imgui.begin_popup_modal("DeleteBatchConfirmPopup", None, imgui.WindowFlags_.always_auto_resize)[0]:
            if self._batchToDelete:
                if self._batchToDelete[0] == "real":
                    batch_id = self._batchToDelete[1]
                    imgui.text(f"Delete batch #{batch_id}?")
                    if imgui.button("Yes"):
                        debug_print(f"Confirmed deletion of real batch {batch_id}")
                        self.StorageManager.RemoveBatch(batch_id)
                        self.searchEngine.Rebuild()
                        self._updateFilteredBatches()
                        self._batchToDelete = None
                        imgui.close_current_popup()
                    imgui.same_line()
                    if imgui.button("No"):
                        self._batchToDelete = None
                        imgui.close_current_popup()
                else:
                    self._batchToDelete = None
                    imgui.close_current_popup()
            else:
                imgui.close_current_popup()
            imgui.end_popup()

    # ---------- Main Draw ----------
    def Draw(self):
        imgui.text("Real Batches")
        imgui.separator()
        self.ShowBatches()

        imgui.text("Pending Batches")
        imgui.separator()
        self.ShowToBeBatches()

        imgui.separator()
        imgui.text("Generate Batches:")
        imgui.same_line()
        changed, self._generateBatchCount = imgui.input_int("##batch_gen_count", self._generateBatchCount)
        if changed:
            self._generateBatchCount = max(1, self._generateBatchCount)
        imgui.same_line()
        imgui.set_next_item_width(em_size(2))
        if imgui.button("Generate Batches"):
            self._GenerateRandomBatches(self._generateBatchCount)


# ---------- MainApp ----------
class MainApp:
    def __init__(self, storageManager, productEnum):
        self.Filter = imgui.TextFilter()
        self.StorageManager = storageManager
        self.StorageManager.SetProductEnum(productEnum)
        self.StorageManager.LoadDatabase("data.txt", productEnum)
        self.ProductEditor = ProductEditor(storageManager, productEnum)
        self.EnumEditor = EnumEditor(productEnum)
        self.BatchEditor = BatchEditor(storageManager)
        self.ProductEditor.searchEngine.Rebuild()
        self.BatchEditor.searchEngine.Rebuild()
        self.StorageManager.OptimizeDatabase()
        self.ProductEditor._UpdateFilteredProducts()
        self.BatchEditor._updateFilteredBatches()

    def Draw(self):
        if imgui.begin_tab_bar("MainTab"):
            # Product Editor tab
            opened, visible = imgui.begin_tab_item("Product Editor")
            if opened:
                self.ProductEditor.Draw()
                self.EnumEditor.Draw()
                imgui.end_tab_item()

            # Database Editor tab (Batches)
            opened, visible = imgui.begin_tab_item("Database Editor")
            if opened:
                self.BatchEditor.Draw()
                imgui.end_tab_item()

            imgui.end_tab_bar()

        # self.Filter.draw('Search ("incl,-excl") ("error")', em_size(25))

        # if imgui.button("Add Product"):
        #     self.ToBeItems.append({
        #         "Name": "",
        #         "TypeIndex": 0,
        #     })

        # for toBeItem in self.ToBeItems:
        #     imgui.push_id("Enter name")

        #     imgui.set_next_item_width(em_size(5))
        #     changed, toBeItem["Name"] = imgui.input_text("Enter name", toBeItem["Name"])

        #     imgui.same_line()
        #     _, toBeItem["TypeIndex"] = imgui.combo("Type", toBeItem["TypeIndex"], ItemTypes)
            
        #     imgui.pop_id()

        # imgui.button("Remove Product")
    
        

class Init:
    def __init__(self, storageManager, productEnum):
        self.MainApp = MainApp(storageManager, productEnum)
        # self.StorageManager = storageManager
        # self.ProductEnum = productEnum

        def gui():
            self.MainApp.Draw()

        hello_imgui.run(gui, window_title="Warehouse Management System")