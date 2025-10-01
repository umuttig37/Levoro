"""
Database Connection and Utilities
Centralized MongoDB connection management and database operations
"""

import os
from pymongo import MongoClient, ReturnDocument
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
DB_NAME = os.getenv("DB_NAME", "carrental")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI puuttuu (aseta ympäristömuuttuja).")


class DatabaseManager:
    """Singleton database manager for MongoDB connections"""

    _instance = None
    _client = None
    _db = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._client = MongoClient(MONGODB_URI)
            self._db = self._client[DB_NAME]

    @property
    def client(self):
        """Get MongoDB client"""
        return self._client

    @property
    def db(self):
        """Get database instance"""
        return self._db

    def get_collection(self, name):
        """Get a collection by name"""
        return self._db[name]

    def sync_counter(self, sequence_name, collection_name, id_field="id"):
        """Sync counter with existing maximum ID in collection"""
        try:
            # Get the maximum existing ID from the collection
            collection = self.get_collection(collection_name)
            max_doc = collection.find_one(sort=[(id_field, -1)])

            if max_doc and id_field in max_doc:
                max_id = max_doc[id_field]
                print(f"Found max {id_field} in {collection_name}: {max_id}")
            else:
                max_id = 0
                print(f"No existing records in {collection_name}, starting counter at 0")

            # Set the counter to max_id (next increment will be max_id + 1)
            counters_col = self.get_collection("counters")
            counters_col.update_one(
                {"_id": sequence_name},
                {"$set": {"value": max_id}},
                upsert=True
            )
            print(f"Synced {sequence_name} counter to {max_id}")
            return max_id

        except Exception as e:
            print(f"Error syncing counter {sequence_name}: {e}")
            return 0

    def close(self):
        """Close database connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None


class BaseModel:
    """Base model class with common database operations"""

    collection_name = None

    def __init__(self):
        self.db_manager = DatabaseManager()
        if not self.collection_name:
            raise NotImplementedError("collection_name must be defined")

    @property
    def collection(self):
        """Get the MongoDB collection for this model"""
        return self.db_manager.get_collection(self.collection_name)

    def find_one(self, filter_dict, projection=None):
        """Find a single document"""
        projection = projection or {"_id": 0}
        return self.collection.find_one(filter_dict, projection)

    def find(self, filter_dict=None, projection=None, sort=None, limit=None):
        """Find multiple documents"""
        filter_dict = filter_dict or {}
        projection = projection or {"_id": 0}

        cursor = self.collection.find(filter_dict, projection)

        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)

        return list(cursor)

    def insert_one(self, document):
        """Insert a single document"""
        result = self.collection.insert_one(document)
        return result.inserted_id

    def update_one(self, filter_dict, update_dict, upsert=False):
        """Update a single document"""
        result = self.collection.update_one(filter_dict, update_dict, upsert=upsert)
        return result.modified_count > 0

    def delete_one(self, filter_dict):
        """Delete a single document"""
        result = self.collection.delete_one(filter_dict)
        return result.deleted_count > 0

    def aggregate(self, pipeline):
        """Run aggregation pipeline"""
        return list(self.collection.aggregate(pipeline))

    def count_documents(self, filter_dict=None):
        """Count documents matching filter"""
        filter_dict = filter_dict or {}
        return self.collection.count_documents(filter_dict)


class CounterManager:
    """Manages auto-incrementing counters for IDs"""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.collection = self.db_manager.get_collection("counters")

    def get_next_id(self, sequence_name):
        """Get the next ID for a sequence"""
        # Check if counter exists, if not sync it first to prevent starting from 1
        counter_doc = self.collection.find_one({"_id": sequence_name})
        if not counter_doc:
            print(f"Counter {sequence_name} doesn't exist, syncing with existing data...")
            # Map sequence names to collection names
            collection_mapping = {
                "users": "users",
                "orders": "orders",
                "driver_applications": "driver_applications"
            }
            collection_name = collection_mapping.get(sequence_name, sequence_name)
            self.db_manager.sync_counter(sequence_name, collection_name, "id")

        # Atomically increment and get the new value
        result = self.collection.find_one_and_update(
            {"_id": sequence_name},
            {"$inc": {"value": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )
        return result["value"]

    def reset_counter(self, sequence_name, start_value=0):
        """Reset a counter to a specific value"""
        self.collection.update_one(
            {"_id": sequence_name},
            {"$set": {"value": start_value}},
            upsert=True
        )


# Global instances for backward compatibility
db_manager = DatabaseManager()
counter_manager = CounterManager()

# Legacy functions for backward compatibility
def mongo_db():
    return db_manager.db

def users_col():
    return db_manager.get_collection("users")

def orders_col():
    return db_manager.get_collection("orders")

def counters_col():
    return db_manager.get_collection("counters")

def next_id(seq_name: str) -> int:
    return counter_manager.get_next_id(seq_name)