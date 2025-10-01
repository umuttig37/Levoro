#!/usr/bin/env python3
"""
Script to fix user status issue in MongoDB
Fixes user ID 13 (Zhinar Jihad) status from missing -> pending
"""

import os
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
DB_NAME = os.getenv("DB_NAME", "Levoro")

if not MONGODB_URI:
    print("❌ ERROR: MONGODB_URI not found in environment")
    exit(1)

def main():
    print("🔧 MongoDB User Status Fix Tool")
    print("=" * 50)
    
    try:
        # Connect to MongoDB
        print(f"🔗 Connecting to MongoDB...")
        client = MongoClient(MONGODB_URI)
        db = client[DB_NAME]
        users_col = db["users"]
        
        # Test connection
        client.admin.command('ping')
        print("✅ Connected successfully!")
        
        # 1. Check current state of user ID 13
        print("\n📋 BEFORE FIX - User ID 13:")
        user_before = users_col.find_one(
            {"id": 13}, 
            {"name": 1, "email": 1, "status": 1, "approved": 1, "role": 1}
        )
        
        if not user_before:
            print("❌ User ID 13 not found!")
            return
            
        print(f"   Name: {user_before.get('name')}")
        print(f"   Email: {user_before.get('email')}")
        print(f"   Role: {user_before.get('role')}")
        print(f"   Status: {user_before.get('status', 'MISSING!')}")
        print(f"   Approved (old field): {user_before.get('approved', 'MISSING!')}")
        
        # 2. Apply the fix
        print(f"\n🔧 APPLYING FIX...")
        
        update_operations = {
            "$set": {
                "status": "pending",
                "updated_at": datetime.now(timezone.utc)
            }
        }
        
        # Remove old approved field if it exists
        if "approved" in user_before:
            update_operations["$unset"] = {"approved": ""}
        
        result = users_col.update_one(
            {"id": 13},
            update_operations
        )
        
        print(f"   Modified count: {result.modified_count}")
        print(f"   Matched count: {result.matched_count}")
        
        if result.modified_count > 0:
            print("✅ Fix applied successfully!")
        else:
            print("⚠️  No changes made (user might already be correct)")
        
        # 3. Verify the fix
        print(f"\n📋 AFTER FIX - User ID 13:")
        user_after = users_col.find_one(
            {"id": 13}, 
            {"name": 1, "email": 1, "status": 1, "approved": 1, "role": 1}
        )
        
        print(f"   Name: {user_after.get('name')}")
        print(f"   Email: {user_after.get('email')}")
        print(f"   Role: {user_after.get('role')}")
        print(f"   Status: {user_after.get('status', 'MISSING!')}")
        print(f"   Approved (old field): {user_after.get('approved', 'REMOVED')}")
        
        # 4. Check for other users with missing status
        print(f"\n🔍 CHECKING FOR OTHER USERS WITH MISSING STATUS:")
        users_without_status = list(users_col.find(
            {
                "status": {"$exists": False},
                "role": {"$ne": "admin"}
            },
            {"id": 1, "name": 1, "email": 1, "role": 1, "approved": 1}
        ))
        
        print(f"   Found {len(users_without_status)} users without status field:")
        for user in users_without_status:
            print(f"   - ID: {user.get('id')}, Name: {user.get('name')}, Email: {user.get('email')}")
        
        if users_without_status:
            print(f"\n⚠️  WARNING: {len(users_without_status)} other users also need fixing!")
            fix_all = input("Do you want to fix all users? (y/n): ").lower().strip()
            
            if fix_all == 'y':
                print("🔧 Fixing all users...")
                bulk_result = users_col.update_many(
                    {
                        "status": {"$exists": False},
                        "role": {"$ne": "admin"}
                    },
                    {
                        "$set": {
                            "status": "pending",
                            "updated_at": datetime.now(timezone.utc)
                        },
                        "$unset": {
                            "approved": ""
                        }
                    }
                )
                print(f"✅ Fixed {bulk_result.modified_count} additional users")
        
        print(f"\n🎉 SCRIPT COMPLETE!")
        print(f"✅ User ID 13 should now show as 'pending' in the admin UI")
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
    finally:
        if 'client' in locals():
            client.close()
            print("🔒 Database connection closed")

if __name__ == "__main__":
    main()