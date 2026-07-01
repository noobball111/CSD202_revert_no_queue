import os
import json
import tempfile
import unittest
import datetime as dt

from Classes.StorageManager import StorageManager
from Classes.ProductEnum import ProductEnum
from Classes.Product import Product
from Classes.Batch import Batch
from Services.UIService import BatchEditor


class StorageManagerTests(unittest.TestCase):
    def setUp(self):
        self.product_enum = ProductEnum()
        self.product_enum.NewEnum("Color", "string")
        self.product_enum.AddToEnum("Color", "Red")
        self.product_enum.AddToEnum("Color", "Blue")
        self.storage = StorageManager()
        self.storage.SetProductEnum(self.product_enum)

    def test_save_and_load_database(self):
        product = Product("00001", "Test Product")
        product.AddAttribute("Color", "Red", "string", True, "Color")
        self.storage.AddProduct(product)

        batch = Batch("00001", 15, "Good")
        batch.ImportedDate = dt.datetime(2024, 1, 1)
        batch.ExpirationDate = dt.datetime(2024, 12, 31)
        self.storage.AddBatch(batch)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as temp_file:
            temp_name = temp_file.name

        try:
            saved = self.storage.SaveDatabase(temp_name)
            self.assertTrue(saved)
            self.assertTrue(os.path.exists(temp_name))

            new_enum = ProductEnum()
            loaded = StorageManager()
            loaded.SetProductEnum(new_enum)
            result = loaded.LoadDatabase(temp_name, new_enum)
            self.assertTrue(result)

            loaded_product = loaded.GetProduct("00001")
            self.assertIsNotNone(loaded_product)
            self.assertEqual(loaded_product.Name.Value, "Test Product")
            self.assertEqual(loaded_product.Color.Value, "Red")
            self.assertEqual(loaded_product.Color.EnumName, "Color")
            self.assertTrue(new_enum.EnumExists("Color"))
            self.assertIn("Red", new_enum.GetValues("Color"))

            loaded_batch_ids = list(loaded.BatchByID.keys())
            self.assertEqual(len(loaded_batch_ids), 1)
            loaded_batch = loaded.BatchByID[loaded_batch_ids[0]]
            self.assertEqual(loaded_batch.ProductUPC, "00001")
            self.assertEqual(loaded_batch.Amount, 15)
            self.assertEqual(loaded_batch.ExpirationDate, dt.datetime(2024, 12, 31))
        finally:
            os.remove(temp_name)

    def test_optimize_database_merges_delta_indexes(self):
        self.storage.ProductDeltaNumericIndexes["amount"] = [(10, "00001")]
        self.storage.BatchDeltaNumericIndexes["amount"] = [(5, 1)]
        self.storage.OptimizeDatabase()

        self.assertFalse(self.storage.ProductDeltaNumericIndexes)
        self.assertFalse(self.storage.BatchDeltaNumericIndexes)
        self.assertIn("amount", self.storage.ProductNumericIndexes)
        self.assertIn("amount", self.storage.BatchNumericIndexes)
        self.assertEqual(self.storage.ProductNumericIndexes["amount"], [(10, "00001")])
        self.assertEqual(self.storage.BatchNumericIndexes["amount"], [(5, 1)])

    def test_get_products_by_keyword_returns_upc(self):
        product = Product("00002", "Another Product")
        product.AddAttribute("Brand", "ACME", "string", False)
        self.storage.AddProduct(product)
        self.assertIn("00002", self.storage.GetProductsByKeyword("acme"))
        self.assertIn("00002", self.storage.GetProductsByKeyword("brand"))
        self.assertIn("00002", self.storage.GetProductsByKeyword("brand:acme"))

    def test_batch_editor_amount_comparison_filter(self):
        batch_editor = BatchEditor(self.storage, prefill_demo=False)
        batch1 = Batch("00001", 5, "Good")
        batch2 = Batch("00002", 25, "Good")
        self.storage.AddBatch(batch1)
        self.storage.AddBatch(batch2)

        filtered_ids = batch_editor._filterBatches("amount>20")
        self.assertEqual(filtered_ids, [batch2.BatchID])

        filtered_ids = batch_editor._filterBatches("amount<10")
        self.assertEqual(filtered_ids, [batch1.BatchID])

    def test_batch_search_autocomplete_includes_amount(self):
        batch_editor = BatchEditor(self.storage, prefill_demo=False)
        suggestions = batch_editor.searchEngine.Autocomplete("am")
        self.assertIn("amount", suggestions)
        self.assertIn("amount:", suggestions)
        self.assertIn("amount>", suggestions)


if __name__ == "__main__":
    unittest.main()
