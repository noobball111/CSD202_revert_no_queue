from .Trie import Trie
from typing import List, Set

def debug_print(*args, **kwargs):
    print("[DEBUG SEARCH]", *args, **kwargs)

class SearchEngine:
    def __init__(self, storageManager, index_type='product'):
        self.storageManager = storageManager
        self.index_type = index_type
        self._mainTrie = Trie()
        self._fieldTries = {}
        self.Rebuild()

    def Rebuild(self):
        debug_print(f"Rebuild() started for {self.index_type}")
        self._mainTrie = Trie()
        self._fieldTries = {}

        if self.index_type == 'product':
            keys = list(self.storageManager.ProductKeywordIndex.keys())
            debug_print(f"Product keys: {keys}")
            for key in keys:
                self._mainTrie.Add(key)

            attr_names = self.storageManager.GetProductAttributeNames()
            for field in attr_names:
                field = field.lower()
                field_prefix = f"{field}:"
                field_trie = Trie()
                for key in keys:
                    if key.startswith(field_prefix):
                        value_part = key[len(field_prefix):]
                        field_trie.Add(value_part)
                self._fieldTries[field] = field_trie

            for field in attr_names:
                self._mainTrie.Add(f"{field.lower()}:")
        else:  # batch
            # Batch keywords from BatchKeywordIndex
            batch_keys = list(self.storageManager.BatchKeywordIndex.keys())
            debug_print(f"Batch keys: {batch_keys}")
            for key in batch_keys:
                self._mainTrie.Add(key)
                debug_print(f"Added to batch trie: {key}")

            # Numeric batch fields should be discoverable for autocomplete.
            numeric_fields = ["amount", "importeddate", "expirationdate"]
            for field in numeric_fields:
                self._mainTrie.Add(field)
                self._mainTrie.Add(f"{field}:")
                self._mainTrie.Add(f"{field}>")
                self._mainTrie.Add(f"{field}>=")
                self._mainTrie.Add(f"{field}<")
                self._mainTrie.Add(f"{field}<=")
                self._mainTrie.Add(f"{field}=")

            # Also add ALL product keywords so we can search batches by product attributes
            product_keys = list(self.storageManager.ProductKeywordIndex.keys())
            debug_print(f"Product keys added to batch trie: {product_keys}")
            for key in product_keys:
                self._mainTrie.Add(key)
                debug_print(f"Added to batch trie: {key}")

        debug_print("Rebuild() finished")

    def Autocomplete(self, query: str) -> List[str]:
        query = query.strip().lower()
        if not query:
            return []

        if self.index_type == 'product' and ":" in query:
            field, sub = query.split(":", 1)
            field = field.strip()
            sub = sub.lstrip()
            if field in self._fieldTries:
                results = self._fieldTries[field].Find(sub)
                return [f"{field}:{r}" for r in results]
            return []
        return self._mainTrie.Find(query)

    def GetSuggestions(self, query: str, limit: int = 10) -> List[str]:
        suggestions = self.Autocomplete(query)
        debug_print(f"GetSuggestions('{query}') -> {suggestions[:limit]}")
        return suggestions[:limit]