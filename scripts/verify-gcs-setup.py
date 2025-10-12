#!/usr/bin/env python3
"""
GCS Setup Verification Script

Checks if GCS is properly configured and accessible.
Run this after setting up buckets to verify everything works.

Usage:
    python verify-gcs-setup.py
"""

import os
import sys
import base64
import json
from pathlib import Path

# Add parent directory to path to import services
sys.path.insert(0, str(Path(__file__).parent.parent))

def check_env_vars():
    """Check if all required environment variables are set"""
    print("\n" + "="*50)
    print("Checking Environment Variables")
    print("="*50)
    
    required_vars = [
        'GCS_PROJECT_ID',
        'GCS_BUCKET_NAME',
        'GCS_PRIVATE_BUCKET_NAME',
        'GCS_CREDENTIALS_JSON'
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if var == 'GCS_CREDENTIALS_JSON':
                print(f"✓ {var}: Present (length: {len(value)} chars)")
            else:
                print(f"✓ {var}: {value}")
        else:
            print(f"✗ {var}: Missing")
            missing.append(var)
    
    if missing:
        print(f"\n❌ Missing variables: {', '.join(missing)}")
        return False
    
    print("\n✅ All environment variables are set")
    return True


def verify_credentials():
    """Verify that credentials are valid JSON"""
    print("\n" + "="*50)
    print("Verifying Credentials Format")
    print("="*50)
    
    creds_b64 = os.getenv('GCS_CREDENTIALS_JSON')
    if not creds_b64:
        print("❌ GCS_CREDENTIALS_JSON not set")
        return False
    
    try:
        # Decode base64
        creds_json = base64.b64decode(creds_b64).decode('utf-8')
        print("✓ Base64 decoding successful")
    except Exception as e:
        print(f"❌ Base64 decoding failed: {e}")
        return False
    
    try:
        # Parse JSON
        creds_dict = json.loads(creds_json)
        print("✓ JSON parsing successful")
    except Exception as e:
        print(f"❌ JSON parsing failed: {e}")
        return False
    
    # Check required fields
    required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 
                      'client_email', 'client_id']
    missing_fields = [f for f in required_fields if f not in creds_dict]
    
    if missing_fields:
        print(f"❌ Missing fields in credentials: {', '.join(missing_fields)}")
        return False
    
    print("\n✅ Credentials format is valid")
    print(f"   Project ID: {creds_dict.get('project_id')}")
    print(f"   Client Email: {creds_dict.get('client_email')}")
    
    return True


def test_gcs_initialization():
    """Test if GCS service initializes correctly"""
    print("\n" + "="*50)
    print("Testing GCS Service Initialization")
    print("="*50)
    
    try:
        from services.gcs_service import gcs_service
        
        if not gcs_service.enabled:
            print("❌ GCS service is not enabled")
            return False
        
        print("✓ GCS service initialized successfully")
        print(f"   Public Bucket: {gcs_service.bucket_name}")
        print(f"   Private Bucket: {gcs_service.private_bucket_name}")
        print(f"   Project ID: {gcs_service.project_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ GCS initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bucket_access():
    """Test if buckets are accessible"""
    print("\n" + "="*50)
    print("Testing Bucket Access")
    print("="*50)
    
    try:
        from services.gcs_service import gcs_service
        
        if not gcs_service.enabled:
            print("❌ GCS not enabled, skipping bucket access test")
            return False
        
        # Test public bucket
        print("\nTesting public bucket access...")
        try:
            blobs = list(gcs_service.bucket.list_blobs(max_results=1))
            print(f"✓ Public bucket accessible")
        except Exception as e:
            print(f"❌ Public bucket not accessible: {e}")
            return False
        
        # Test private bucket
        print("\nTesting private bucket access...")
        try:
            blobs = list(gcs_service.private_bucket.list_blobs(max_results=1))
            print(f"✓ Private bucket accessible")
        except Exception as e:
            print(f"❌ Private bucket not accessible: {e}")
            return False
        
        print("\n✅ Both buckets are accessible")
        return True
        
    except Exception as e:
        print(f"❌ Bucket access test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification checks"""
    print("\n" + "="*50)
    print("GCS Setup Verification")
    print("="*50)
    
    # Load environment variables from .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✓ .env file loaded")
    except ImportError:
        print("! python-dotenv not installed, using system environment only")
    except Exception as e:
        print(f"! Could not load .env file: {e}")
    
    # Run checks
    checks = [
        ("Environment Variables", check_env_vars),
        ("Credentials Format", verify_credentials),
        ("GCS Initialization", test_gcs_initialization),
        ("Bucket Access", test_bucket_access),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Unexpected error in {name}: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*50)
    print("Verification Summary")
    print("="*50)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "="*50)
    if all_passed:
        print("✅ All checks passed! GCS is ready to use.")
        print("="*50)
        return 0
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print("="*50)
        return 1


if __name__ == "__main__":
    sys.exit(main())
