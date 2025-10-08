#!/usr/bin/env python3
"""
Password Reset System Test Script
Tests the password reset functionality without running the full Flask app
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.user import user_model
from datetime import datetime, timezone, timedelta
import secrets


def test_password_reset_flow():
    """Test the complete password reset flow"""
    
    print("🔐 Password Reset System Test")
    print("=" * 60)
    
    # Test 1: Generate Reset Token
    print("\n1️⃣  Testing token generation...")
    test_email = "test@example.com"
    
    # First, check if test user exists
    existing_user = user_model.find_by_email(test_email)
    if not existing_user:
        print(f"   ⚠️  Test user {test_email} does not exist")
        print(f"   💡 Create a test user first or use an existing email")
        return False
    
    print(f"   ✅ Found user: {existing_user.get('name')} ({existing_user.get('email')})")
    
    token, error = user_model.generate_reset_token(test_email)
    
    if error:
        print(f"   ❌ Token generation failed: {error}")
        return False
    
    print(f"   ✅ Token generated successfully")
    print(f"   📝 Token: {token[:20]}... (truncated for security)")
    
    # Test 2: Validate Token
    print("\n2️⃣  Testing token validation...")
    user, error = user_model.validate_reset_token(token)
    
    if error:
        print(f"   ❌ Token validation failed: {error}")
        return False
    
    print(f"   ✅ Token is valid")
    print(f"   👤 User: {user.get('email')}")
    print(f"   ⏰ Expires: {user.get('reset_token_expires')}")
    
    # Test 3: Test Expired Token
    print("\n3️⃣  Testing expired token detection...")
    
    # Manually set token to expired
    expired_date = datetime.now(timezone.utc) - timedelta(hours=3)
    user_model.update_one(
        {"id": user["id"]},
        {"$set": {"reset_token_expires": expired_date}}
    )
    
    _, error = user_model.validate_reset_token(token)
    
    if error and "vanhentunut" in error.lower():
        print(f"   ✅ Expired token correctly rejected")
        print(f"   📝 Error: {error}")
    else:
        print(f"   ❌ Expired token not detected properly")
        return False
    
    # Restore valid expiration
    valid_date = datetime.now(timezone.utc) + timedelta(hours=2)
    user_model.update_one(
        {"id": user["id"]},
        {"$set": {"reset_token_expires": valid_date}}
    )
    
    # Test 4: Reset Password
    print("\n4️⃣  Testing password reset...")
    new_password = "new_test_password_123"
    
    success, error = user_model.reset_password_with_token(token, new_password)
    
    if not success:
        print(f"   ❌ Password reset failed: {error}")
        return False
    
    print(f"   ✅ Password reset successful")
    
    # Test 5: Verify Token Cleared
    print("\n5️⃣  Testing token cleanup...")
    updated_user = user_model.find_by_id(user["id"])
    
    if "reset_token" not in updated_user or updated_user.get("reset_token") is None:
        print(f"   ✅ Reset token cleared successfully")
    else:
        print(f"   ❌ Reset token not cleared")
        return False
    
    # Test 6: Verify New Password Works
    print("\n6️⃣  Testing new password authentication...")
    auth_user, error = user_model.authenticate(test_email, new_password)
    
    if error:
        print(f"   ❌ Authentication with new password failed: {error}")
        return False
    
    print(f"   ✅ New password works correctly")
    
    # Test 7: Verify Token Cannot Be Reused
    print("\n7️⃣  Testing one-time use (token reuse prevention)...")
    _, error = user_model.validate_reset_token(token)
    
    if error:
        print(f"   ✅ Used token correctly rejected")
        print(f"   📝 Error: {error}")
    else:
        print(f"   ❌ Used token was not rejected (security issue!)")
        return False
    
    # Test 8: Invalid Token
    print("\n8️⃣  Testing invalid token rejection...")
    fake_token = secrets.token_urlsafe(32)
    _, error = user_model.validate_reset_token(fake_token)
    
    if error:
        print(f"   ✅ Invalid token correctly rejected")
        print(f"   📝 Error: {error}")
    else:
        print(f"   ❌ Invalid token was not rejected")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All password reset tests passed!")
    print("=" * 60)
    
    return True


def cleanup_test_tokens():
    """Clean up any test reset tokens"""
    print("\n🧹 Cleaning up test tokens...")
    
    result = user_model.update_many(
        {"reset_token": {"$exists": True}},
        {"$unset": {"reset_token": "", "reset_token_expires": ""}}
    )
    
    print(f"   Cleaned {result} reset tokens")


if __name__ == "__main__":
    print("\n⚠️  WARNING: This test will modify database records!")
    print("   Make sure you're running this on a development database.")
    
    response = input("\nContinue? (yes/no): ").strip().lower()
    
    if response == "yes":
        try:
            success = test_password_reset_flow()
            
            if success:
                print("\n✅ Password reset system is working correctly!")
                
                # Ask about cleanup
                cleanup_response = input("\nClean up all reset tokens? (yes/no): ").strip().lower()
                if cleanup_response == "yes":
                    cleanup_test_tokens()
            else:
                print("\n❌ Password reset system has issues!")
                sys.exit(1)
                
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        print("Test cancelled.")
        sys.exit(0)
