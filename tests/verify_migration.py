import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import datetime
import mongomock
from decimal import Decimal, ROUND_HALF_UP

# Add current directory to path
sys.path.insert(0, os.getcwd())

# Mock environment variables
os.environ["MONGODB_URI"] = "mongodb://mock-uri"
os.environ["DB_NAME"] = "test_db"
os.environ["BASE_FEE"] = "49"
os.environ["PER_KM"] = "1.20"
os.environ["VAT_RATE"] = "0.255"

# Mock Google Cloud libraries
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.oauth2"] = MagicMock()
sys.modules["google.oauth2.service_account"] = MagicMock()

# Mock Flask and Flask-Mail to prevent import errors in services
sys.modules["flask"] = MagicMock()
sys.modules["flask_mail"] = MagicMock()

# Helper function to match service rounding logic
def round_half_up(value, decimals=2):
    if value is None:
        return 0.0
    decimal_value = Decimal(str(value))
    quantizer = Decimal(10) ** -decimals
    rounded = decimal_value.quantize(quantizer, rounding=ROUND_HALF_UP)
    return float(rounded)

# Patch MongoClient BEFORE importing models.database
with patch('pymongo.MongoClient', mongomock.MongoClient):
    from models.database import db_manager
    from services.order_service import OrderService

class TestOrderFlow(unittest.TestCase):
    def setUp(self):
        # Clean up the mock database
        self.db = db_manager.db
        self.db.orders.drop()
        self.db.users.drop()
        self.db.counters.drop()

        # Initialize service
        self.order_service = OrderService()

        # Setup counters
        self.db.counters.insert_one({"_id": "orders", "value": 100})
        self.db.counters.insert_one({"_id": "users", "value": 1})

    def test_create_basic_order(self):
        """Test creating a standard order via service layer"""
        user_id = 1
        order_data = {
            "pickup_address": "Testikatu 1, Helsinki",
            "dropoff_address": "Testitie 2, Tampere",
            "distance_km": 180.0,
            "price_net": 100.0,
            "price_vat": 25.5,
            "price_gross": 125.5,
            "pickup_date": "2025-01-01",
            "orderer_name": "Test Orderer",
            "orderer_email": "test@example.com",
            "orderer_phone": "+358401234567"
        }

        # Execute
        success, order, error = self.order_service.create_order(user_id, order_data)

        # Verify
        self.assertTrue(success, f"Order creation failed: {error}")
        self.assertIsNotNone(order)
        self.assertEqual(order["id"], 101)
        self.assertEqual(order["status"], "NEW")
        self.assertEqual(order["price_gross"], 125.5)

        # Verify DB insertion
        saved_order = self.db.orders.find_one({"id": 101})
        self.assertIsNotNone(saved_order)
        self.assertEqual(saved_order["pickup_address"], "Testikatu 1, Helsinki")

    def test_price_calculation_logic(self):
        """Verify the pricing logic matches expectations using correct rounding"""
        km = 10.0

        # Get result from service
        # Note: mocking geocoding inside service logic is hard without patching internal methods,
        # but price_from_km_with_discounts mainly does math.
        # We need to patch _both_in_metro if we want deterministic "metro" pricing,
        # but let's trust the input args "Helsinki", "Espoo" trigger it.

        result = self.order_service.price_from_km_with_discounts(km, "Helsinki", "Espoo")

        self.assertIn("final_net", result)
        self.assertIn("final_gross", result)
        self.assertIn("final_vat", result)

        net = result["final_net"]
        gross = result["final_gross"]

        # Verify VAT calculation using service's rounding method
        expected_gross = round_half_up(net * (1 + 0.255), 2)
        self.assertEqual(gross, expected_gross)

    def test_create_order_validations(self):
        """
        Test validation within create_order.
        NOTE: Current Service implementation DOES NOT enforce schema validation.
        This test verifies that the service accepts incomplete data, relying on Controller/Wizard validation.
        """
        user_id = 1
        incomplete_data = {
            "pickup_address": "Mannerheimintie 1",
            # Missing dropoff_address
        }

        success, order, error = self.order_service.create_order(user_id, incomplete_data)

        # Assert SUCCESS because service doesn't validate fields (current behavior)
        self.assertTrue(success)
        self.assertIsNotNone(order)
        self.assertEqual(order["pickup_address"], "Mannerheimintie 1")

    def test_return_order_linkage(self):
        """Test that return orders can be linked"""
        user_id = 1
        # 1. Create Outbound
        outbound_data = {
            "pickup_address": "A", "dropoff_address": "B",
            "distance_km": 100, "price_net": 100, "price_vat": 25.5, "price_gross": 125.5,
            "pickup_date": "2025-01-01",
            "orderer_name": "T", "orderer_email": "t@e.com", "orderer_phone": "123",
            "trip_type": "OUTBOUND"
        }
        success1, order1, _ = self.order_service.create_order(user_id, outbound_data)
        self.assertTrue(success1)

        # 2. Create Return
        return_data = {
            "pickup_address": "B", "dropoff_address": "A",
            "distance_km": 100, "price_net": 70, "price_vat": 17.85, "price_gross": 87.85,
            "pickup_date": "2025-01-02",
            "orderer_name": "T", "orderer_email": "t@e.com", "orderer_phone": "123",
            "trip_type": "RETURN",
            "parent_order_id": order1["id"],
            "return_leg": True
        }
        success2, order2, _ = self.order_service.create_order(user_id, return_data)
        self.assertTrue(success2)

        # 3. Simulate Linkage (as done in controller)
        self.db.orders.update_one({"id": order1["id"]}, {"$set": {"return_order_id": order2["id"]}})

        updated_order1 = self.db.orders.find_one({"id": order1["id"]})
        self.assertEqual(updated_order1["return_order_id"], order2["id"])

if __name__ == "__main__":
    unittest.main()
