import json
import os
import datetime as dt
from typing import Set
from .Product import Product, Attribute
from .Batch import Batch
from . import Batch as BatchModule


class   StorageManager:
    def __init__(self):
        self.Products = dict()
        self.BatchByID = dict()

        self.ProductAttributeNameCounts = {}
        self.ProductEnum = None

        # Keyword indexes
        self.ProductKeywordIndex = dict()    # key -> set of UPCs
        self.BatchKeywordIndex = dict()      # key -> set of BatchIDs
        self.ProductToBatchIndex = dict()    # ProductUPC -> set of BatchIDs

        # Numeric indexes for products (user‑defined numeric attributes)
        self.ProductNumericIndexes = dict()      # field -> list of (value, UPC)
        self.ProductDeltaNumericIndexes = dict() # field -> list of (value, UPC) for recent additions

        # Numeric indexes for batches
        self.BatchNumericIndexes = dict()        # field -> list of (value, batchID)
        self.BatchDeltaNumericIndexes = dict()   # field -> list of (value, batchID) for recent additions

    # ---------- Attribute name tracking ----------
    def _addProductAttributeName(self, field: str):
        field = field.lower()
        if field not in self.ProductAttributeNameCounts:
            self.ProductAttributeNameCounts[field] = 0
        self.ProductAttributeNameCounts[field] += 1

    def _removeProductAttributeName(self, field: str):
        field = field.lower()
        if field in self.ProductAttributeNameCounts:
            self.ProductAttributeNameCounts[field] -= 1
            if self.ProductAttributeNameCounts[field] <= 0:
                del self.ProductAttributeNameCounts[field]

    def GetProductAttributeNames(self) -> set:
        return set(self.ProductAttributeNameCounts.keys())

    def GetProductsByKeyword(self, keyword: str) -> Set[str]:
        keyword = keyword.lower()
        return self.ProductKeywordIndex.get(keyword, set())

    def GetBatchIDsByNumericComparison(self, field: str, operator: str, value: float) -> Set[int]:
        field = field.lower()
        batch_ids = set()

        def matches(v: float) -> bool:
            if operator == ">":
                return v > value
            if operator == "<":
                return v < value
            if operator == ">=":
                return v >= value
            if operator == "<=":
                return v <= value
            if operator in ("=", "=="):
                return v == value
            return False

        for index_dict in (self.BatchNumericIndexes, self.BatchDeltaNumericIndexes):
            if field not in index_dict:
                continue
            for v, batch_id in index_dict[field]:
                if matches(v):
                    batch_ids.add(batch_id)

        return batch_ids

    # ---------- Product management ----------
    def AddProduct(self, product):
        """Add a product and index its attributes (both string and numeric)."""
        self.Products[product.UPC.Value] = product
        self._indexProduct(product)

    def RemoveProduct(self, product):
        """Remove a product and delete its entries from all indexes."""
        if product.UPC.Value in self.Products:
            del self.Products[product.UPC.Value]
        self._removeProduct(product)

    def GetProduct(self, upc):
        return self.Products.get(upc)

    # ---------- Batch management ----------
    def AddBatch(self, batch):
        if batch.BatchID in self.BatchByID:
            return
        self.BatchByID[batch.BatchID] = batch

        if batch.ProductUPC not in self.ProductToBatchIndex:
            self.ProductToBatchIndex[batch.ProductUPC] = set()
        self.ProductToBatchIndex[batch.ProductUPC].add(batch.BatchID)

        self._indexBatch(batch)

    def GetBatch(self, batchID: int):
        return self.BatchByID[batchID]

    def RemoveBatch(self, batchID: int):
        if batchID not in self.BatchByID:
            return
        batch = self.BatchByID.pop(batchID)

        self.ProductToBatchIndex[batch.ProductUPC].remove(batchID)
        if not self.ProductToBatchIndex[batch.ProductUPC]:
            del self.ProductToBatchIndex[batch.ProductUPC]

        self._removeBatch(batch)

    def BulkAddBatches(self, batches):
        for batch in batches:
            if self.DoesBatchIDExist(batch):
                continue
            self.AddBatch(batch)

    def RemoveBulkBatches(self, batchIDs):
        for batchID in batchIDs:
            self.RemoveBatch(batchID)

    def DoesBatchIDExist(self, batch):
        return batch.BatchID in self.BatchByID

    # ---------- Rebuilding indexes ----------
    def RebuildProductIndex(self):
        self.ProductKeywordIndex.clear()
        self.ProductNumericIndexes.clear()
        self.ProductDeltaNumericIndexes.clear()
        self.ProductAttributeNameCounts.clear()
        for prod in self.Products.values():
            self._indexProduct(prod)
        # Sort numeric indexes
        for index in self.ProductNumericIndexes.values():
            index.sort(key=lambda x: x[0])

    def RebuildBatchIndex(self):
        self.BatchKeywordIndex.clear()
        self.BatchNumericIndexes.clear()
        self.BatchDeltaNumericIndexes.clear()

    def SetProductEnum(self, productEnum):
        self.ProductEnum = productEnum

    def SaveDatabase(self, file_path: str):
        payload = {
            "products": [],
            "batches": [],
            "enums": {},
            "indexes": {
                "product_keywords": {k: list(v) for k, v in self.ProductKeywordIndex.items()},
                "batch_keywords": {k: list(v) for k, v in self.BatchKeywordIndex.items()},
                "product_to_batch": {k: list(v) for k, v in self.ProductToBatchIndex.items()},
                "product_numeric": {k: v for k, v in self.ProductNumericIndexes.items()},
                "product_delta_numeric": {k: v for k, v in self.ProductDeltaNumericIndexes.items()},
                "batch_numeric": {k: v for k, v in self.BatchNumericIndexes.items()},
                "batch_delta_numeric": {k: v for k, v in self.BatchDeltaNumericIndexes.items()},
            },
        }

        if self.ProductEnum is not None:
            payload["enums"] = {
                enum_name: {
                    "type": self.ProductEnum.GetType(enum_name),
                    "values": self.ProductEnum.GetValues(enum_name),
                }
                for enum_name in self.ProductEnum.EnumNames()
            }

        for product in self.Products.values():
            product_data = {
                "UPC": product.UPC.Value,
                "Name": product.Name.Value,
                "attributes": [
                    {
                        "name": attr_name,
                        "value": attr.Value,
                        "type": attr.Type,
                        "is_enum": attr.IsEnum,
                        "enum_name": attr.EnumName,
                    }
                    for attr_name, attr in product.__dict__.items()
                    if not attr_name.startswith("_") and isinstance(attr, Attribute)
                ],
            }
            payload["products"].append(product_data)

        for batch in self.BatchByID.values():
            payload["batches"].append({
                "BatchID": batch.BatchID,
                "ProductUPC": batch.ProductUPC,
                "Amount": batch.Amount,
                "State": batch.State,
                "ImportedDate": batch.ImportedDate.isoformat(),
                "ExpirationDate": batch.ExpirationDate.isoformat() if batch.ExpirationDate is not None else None,
            })

        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        return True

    def LoadDatabase(self, file_path: str, productEnum=None):
        if not os.path.exists(file_path):
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            return False

        self.Products.clear()
        self.BatchByID.clear()
        self.ProductKeywordIndex.clear()
        self.BatchKeywordIndex.clear()
        self.ProductToBatchIndex.clear()
        self.ProductNumericIndexes.clear()
        self.ProductDeltaNumericIndexes.clear()
        self.BatchNumericIndexes.clear()
        self.BatchDeltaNumericIndexes.clear()
        self.ProductAttributeNameCounts.clear()

        if productEnum is not None:
            self.ProductEnum = productEnum
            self.ProductEnum._enums.clear()
        elif self.ProductEnum is not None:
            self.ProductEnum._enums.clear()

        enums = payload.get("enums", {})
        for enum_name, enum_data in enums.items():
            if self.ProductEnum is not None:
                self.ProductEnum.NewEnum(enum_name, enum_data.get("type", "string"))
                for val in enum_data.get("values", []):
                    self.ProductEnum.AddToEnum(enum_name, val)

        for product_data in payload.get("products", []):
            product = Product(product_data["UPC"], product_data["Name"])
            for attr in product_data.get("attributes", []):
                if attr["name"] in ("UPC", "Name"):
                    continue
                product.AddAttribute(
                    attr["name"],
                    attr["value"],
                    attr["type"],
                    attr["is_enum"],
                    attr.get("enum_name"),
                )
            self.Products[product.UPC.Value] = product
            self._indexProduct(product)

        max_batch_id = -1
        for batch_data in payload.get("batches", []):
            batch = Batch(batch_data["ProductUPC"], batch_data["Amount"], batch_data["State"])
            batch.BatchID = batch_data["BatchID"]
            batch.ImportedDate = dt.datetime.fromisoformat(batch_data["ImportedDate"])
            batch.ExpirationDate = dt.datetime.fromisoformat(batch_data["ExpirationDate"]) if batch_data.get("ExpirationDate") else None
            self.BatchByID[batch.BatchID] = batch
            if batch.ProductUPC not in self.ProductToBatchIndex:
                self.ProductToBatchIndex[batch.ProductUPC] = set()
            self.ProductToBatchIndex[batch.ProductUPC].add(batch.BatchID)
            self._indexBatch(batch)
            max_batch_id = max(max_batch_id, batch.BatchID)

        if max_batch_id >= 0:
            BatchModule.Data["BatchID"] = max_batch_id

        self.OptimizeDatabase()
        return True

    # ---------- Internal product index helpers ----------
    def _addToProductKeyword(self, key: str, upc: str):
        key = key.lower()
        if key not in self.ProductKeywordIndex:
            self.ProductKeywordIndex[key] = set()
        self.ProductKeywordIndex[key].add(upc)

    def _removeFromProductKeyword(self, key: str, upc: str):
        key = key.lower()
        if key in self.ProductKeywordIndex:
            self.ProductKeywordIndex[key].discard(upc)
            if not self.ProductKeywordIndex[key]:
                del self.ProductKeywordIndex[key]

    def _addToProductNumeric(self, field: str, value: int | float, upc: str, delta: bool = False):
        field = field.lower()
        target = self.ProductDeltaNumericIndexes if delta else self.ProductNumericIndexes
        if field not in target:
            target[field] = []
        target[field].append((value, upc))

    def _removeFromProductNumeric(self, field: str, value: int | float, upc: str, delta: bool = False):
        field = field.lower()
        target = self.ProductDeltaNumericIndexes if delta else self.ProductNumericIndexes
        if field in target:
            target[field] = [(v, u) for v, u in target[field] if not (v == value and u == upc)]
            if not target[field]:
                del target[field]

    def _indexProduct(self, prod):
        upc = prod.UPC.Value
        for attr, data in prod.__dict__.items():
            if attr.startswith("_"):
                continue
            if not isinstance(data, Attribute):
                continue
            # Track attribute name
            self._addProductAttributeName(attr)
            # Index the attribute name itself (e.g., "size", "price")
            self._addToProductKeyword(attr.lower(), upc)

            value_str = str(data.Value).lower()
            self._addToProductKeyword(value_str, upc)
            if data.Type == "string" and isinstance(data.Value, str):
                for token in value_str.split():
                    self._addToProductKeyword(token, upc)
            # Field‑specific keyword for exact field search
            self._addToProductKeyword(f"{attr.lower()}:{value_str}", upc)

    def _removeProduct(self, prod):
        upc = prod.UPC.Value
        for attr, data in prod.__dict__.items():
            if attr.startswith("_") or not isinstance(data, Attribute):
                continue
            self._removeProductAttributeName(attr)
            self._removeFromProductKeyword(attr.lower(), upc)
            value_str = str(data.Value).lower()
            self._removeFromProductKeyword(value_str, upc)
            if data.Type == "string" and isinstance(data.Value, str):
                for token in value_str.split():
                    self._removeFromProductKeyword(token, upc)
            self._removeFromProductKeyword(f"{attr.lower()}:{value_str}", upc)

    # ---------- Internal batch index helpers ----------
    def _addToBatchKeyword(self, key: str, batchID: int):
        key = key.lower()
        if key not in self.BatchKeywordIndex:
            self.BatchKeywordIndex[key] = set()
        self.BatchKeywordIndex[key].add(batchID)

    def _removeFromBatchKeyword(self, key: str, batchID: int):
        key = key.lower()
        if key in self.BatchKeywordIndex:
            self.BatchKeywordIndex[key].discard(batchID)
            if not self.BatchKeywordIndex[key]:
                del self.BatchKeywordIndex[key]

    def _indexBatch(self, batch, useDelta=True):
        state = batch.State.lower()
        self._addToBatchKeyword(state, batch.BatchID)
        self._addToBatchKeyword(f"state:{state}", batch.BatchID)

        if batch.ExpirationDate is None:
            self._addToBatchKeyword("noexpiration", batch.BatchID)
        else:
            self._addToBatchKeyword("hasexpiration", batch.BatchID)

        addNumeric = self._addToBatchDeltaNumeric if useDelta else self._addToBatchNumeric

        addNumeric("amount", batch.Amount, batch.BatchID)
        addNumeric("importeddate", batch.ImportedDate.timestamp(), batch.BatchID)
        if batch.ExpirationDate is not None:
            addNumeric("expirationdate", batch.ExpirationDate.timestamp(), batch.BatchID)

    def _removeBatch(self, batch):
        state = batch.State.lower()
        self._removeFromBatchKeyword(state, batch.BatchID)
        self._removeFromBatchKeyword(f"state:{state}", batch.BatchID)
        if batch.ExpirationDate is None:
            self._removeFromBatchKeyword("noexpiration", batch.BatchID)
        else:
            self._removeFromBatchKeyword("hasexpiration", batch.BatchID)

        # Remove from numeric indexes (both main and delta)
        self._removeFromBatchNumeric("amount", batch.Amount, batch.BatchID, delta=True)
        self._removeFromBatchNumeric("amount", batch.Amount, batch.BatchID, delta=False)
        self._removeFromBatchNumeric("importeddate", batch.ImportedDate.timestamp(), batch.BatchID, delta=True)
        self._removeFromBatchNumeric("importeddate", batch.ImportedDate.timestamp(), batch.BatchID, delta=False)
        if batch.ExpirationDate is not None:
            self._removeFromBatchNumeric("expirationdate", batch.ExpirationDate.timestamp(), batch.BatchID, delta=True)
            self._removeFromBatchNumeric("expirationdate", batch.ExpirationDate.timestamp(), batch.BatchID, delta=False)

    def _addToBatchNumeric(self, field: str, value: int | float, batchID: int):
        field = field.lower()
        if field not in self.BatchNumericIndexes:
            self.BatchNumericIndexes[field] = []
        self.BatchNumericIndexes[field].append((value, batchID))

    def _addToBatchDeltaNumeric(self, field: str, value: int | float, batchID: int):
        field = field.lower()
        if field not in self.BatchDeltaNumericIndexes:
            self.BatchDeltaNumericIndexes[field] = []
        self.BatchDeltaNumericIndexes[field].append((value, batchID))

    def _removeFromBatchNumeric(self, field: str, value: int | float, batchID: int, delta: bool):
        field = field.lower()
        target = self.BatchDeltaNumericIndexes if delta else self.BatchNumericIndexes
        if field in target:
            target[field] = [(v, b) for v, b in target[field] if not (v == value and b == batchID)]
            if not target[field]:
                del target[field]

    def OptimizeDatabase(self):
        """Merge delta numeric indexes (both product and batch) into their main sorted indexes."""
        # Merge product delta into product main
        for field, delta in self.ProductDeltaNumericIndexes.items():
            if field not in self.ProductNumericIndexes:
                self.ProductNumericIndexes[field] = []
            self.ProductNumericIndexes[field].extend(delta)
            self.ProductNumericIndexes[field].sort(key=lambda x: x[0])
        self.ProductDeltaNumericIndexes.clear()

        # Merge batch delta into batch main
        for field, delta in self.BatchDeltaNumericIndexes.items():
            if field not in self.BatchNumericIndexes:
                self.BatchNumericIndexes[field] = []
            self.BatchNumericIndexes[field].extend(delta)
            self.BatchNumericIndexes[field].sort(key=lambda x: x[0])
        self.BatchDeltaNumericIndexes.clear()