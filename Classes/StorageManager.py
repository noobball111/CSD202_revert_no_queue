from typing import Set
from .Product import Product, Attribute
from .Batch import Batch


class StorageManager:
    def __init__(self):
        self.Products = dict()
        self.BatchByID = dict()

        self.ProductAttributeNameCounts = {}

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

    def BulkRemoveBatches(self, batchIDs) -> int:
        ids_to_remove = set()
        for bid in batchIDs:
            if bid in self.BatchByID:
                ids_to_remove.add(bid)

        if not ids_to_remove:
            return 0

        for bid in ids_to_remove:
            batch = self.BatchByID.pop(bid)

            # ProductToBatchIndex
            upc_set = self.ProductToBatchIndex.get(batch.ProductUPC)
            if upc_set is not None:
                upc_set.discard(bid)
                if not upc_set:
                    del self.ProductToBatchIndex[batch.ProductUPC]

            # BatchKeywordIndex
            state = batch.State.lower()
            for key in (state, f"state:{state}"):
                s = self.BatchKeywordIndex.get(key)
                if s is not None:
                    s.discard(bid)
            exp_key = "noexpiration" if batch.ExpirationDate is None else "hasexpiration"
            s = self.BatchKeywordIndex.get(exp_key)
            if s is not None:
                s.discard(bid)

        # Clean up empty keyword sets in one sweep
        empty = [k for k, v in self.BatchKeywordIndex.items() if not v]
        for k in empty:
            del self.BatchKeywordIndex[k]

        for store in (self.BatchNumericIndexes, self.BatchDeltaNumericIndexes):
            empty_fields = []
            for field, entries in store.items():
                store[field] = [(v, b) for v, b in entries if b not in ids_to_remove]
                if not store[field]:
                    empty_fields.append(field)
            for f in empty_fields:
                del store[f]

        return len(ids_to_remove)

    def RebuildProductIndex(self):
        self.ProductKeywordIndex.clear()
        self.ProductNumericIndexes.clear()
        self.ProductDeltaNumericIndexes.clear()
        for prod in Product.ProductCache:   # Assumes Product.ProductCache exists
            self._indexProduct(prod)
        # Sort numeric indexes
        for index in self.ProductNumericIndexes.values():
            index.sort(key=lambda x: x[0])

    def RebuildBatchIndex(self):
        self.BatchKeywordIndex.clear()
        self.BatchNumericIndexes.clear()
        self.BatchDeltaNumericIndexes.clear()

        for batch in self.BatchByID.values():
            self._indexBatch(batch, useDelta=False)

        for index in self.BatchNumericIndexes.values():
            index.sort(key=lambda x: x[0])

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

            # Index string values
            if data.Type == "string" and isinstance(data.Value, str):
                value = data.Value.lower()
                self._addToProductKeyword(value, upc)
                for token in value.split():
                    self._addToProductKeyword(token, upc)
                # Field‑specific keyword for exact field search
                self._addToProductKeyword(f"{attr.lower()}:{value}", upc)

    def _removeProduct(self, prod):
        upc = prod.UPC.Value
        for attr, data in prod.__dict__.items():
            if attr.startswith("_") or not isinstance(data, Attribute):
                continue
            self._removeProductAttributeName(attr)
            self._removeFromProductKeyword(attr.lower(), upc)
            if data.Type == "string" and isinstance(data.Value, str):
                value = data.Value.lower()
                self._removeFromProductKeyword(value, upc)
                for token in value.split():
                    self._removeFromProductKeyword(token, upc)
                self._removeFromProductKeyword(f"{attr.lower()}:{value}", upc)

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