
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import json

load_dotenv()

# Setup explicit DB logic to avoid full app context
MONGO_URI = os.getenv("MONGO_URI") or "mongodb+srv://doadmin:db_password@db-mongodb-fra1-40589-c196ca74.mongo.ondigitalocean.com/admin?tls=true&authSource=admin"
DB_NAME = os.getenv("DB_NAME") or "levoro"

try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    users_col = db["users"]
    
    # Try to find a user with saved addresses
    # We'll look for any user first, then specifically one with the IDs from the screenshot if possible
    # Screenshot IDs: 1fa7e5da-5ed5-4623-9a9d-25100e94b426
    
    target_id = "1fa7e5da-5ed5-4623-9a9d-25100e94b426"
    
    print("Searching for user with specific saved address ID...")
    user = users_col.find_one({"saved_addresses.id": target_id})
    
    if user:
        print(f"Found user: {user.get('email')} (ID: {user.get('id')})")
        print("Saved Addresses:")
        for a in user.get('saved_addresses', []):
            print(f" - {a.get('displayName')}: {a.get('id')} (Type: {type(a.get('id'))})")
    else:
        print("No user found with that specific address ID.")
        print("Listing all users with saved addresses:")
        for u in users_col.find({"saved_addresses": {"$exists": True, "$not": {"$size": 0}}}):
            print(f"User: {u.get('email')}")
            for a in u.get('saved_addresses', []):
                print(f"   - {a.get('displayName')}: {a.get('id')}")

except Exception as e:
    print(f"Error: {e}")
