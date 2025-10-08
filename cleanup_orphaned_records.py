"""
Cleanup Script: Remove Orphaned Driver Applications
----------------------------------------------------
This script finds and removes driver applications where the corresponding
user account no longer exists in the database.

Run this script once to clean up orphaned records.

Usage:
    python cleanup_orphaned_records.py [--dry-run]

Options:
    --dry-run    Show what would be deleted without actually deleting
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import database connection
from models.database import db_manager
from models.user import user_model
from models.driver_application import driver_application_model


def cleanup_orphaned_applications(dry_run=True):
    """
    Find and remove driver applications that don't have corresponding users.

    Args:
        dry_run: If True, only report what would be deleted without deleting

    Returns:
        dict: Statistics about the cleanup operation
    """
    print("=" * 60)
    print("ORPHANED DRIVER APPLICATIONS CLEANUP")
    print("=" * 60)
    print(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'LIVE (will delete orphaned records)'}")
    print()

    # Get all driver applications
    all_applications = list(driver_application_model.find())

    orphaned_applications = []
    valid_applications = []

    # Check each application
    for app in all_applications:
        email = app.get('email')
        app_id = app.get('id')
        status = app.get('status', 'unknown')

        # Find if corresponding user exists
        user = user_model.find_by_email(email)

        if not user:
            # No user exists - this is orphaned
            orphaned_applications.append(app)
        else:
            valid_applications.append(app)

    # Report findings
    print(f"Total driver applications: {len(all_applications)}")
    print(f"Valid applications (with users): {len(valid_applications)}")
    print(f"Orphaned applications (without users): {len(orphaned_applications)}")
    print()

    if orphaned_applications:
        print("ORPHANED APPLICATIONS FOUND:")
        print("-" * 60)
        for app in orphaned_applications:
            print(f"  ID: {app.get('id')}")
            print(f"  Email: {app.get('email')}")
            print(f"  Name: {app.get('name')}")
            print(f"  Status: {app.get('status')}")
            print(f"  Created: {app.get('created_at')}")
            print()

        if not dry_run:
            # Delete orphaned applications
            print("Deleting orphaned applications...")
            deleted_count = 0
            failed_count = 0

            for app in orphaned_applications:
                try:
                    result = driver_application_model.delete_one({"id": app['id']})
                    if result:
                        deleted_count += 1
                        print(f"  ✓ Deleted application ID {app['id']} ({app['email']})")
                    else:
                        failed_count += 1
                        print(f"  ✗ Failed to delete application ID {app['id']} ({app['email']})")
                except Exception as e:
                    failed_count += 1
                    print(f"  ✗ Error deleting application ID {app['id']}: {str(e)}")

            print()
            print(f"Successfully deleted: {deleted_count}")
            print(f"Failed to delete: {failed_count}")
        else:
            print("DRY RUN: No deletions performed.")
            print("Run with --live flag to actually delete these records.")
    else:
        print("✓ No orphaned applications found. Database is clean!")

    print()
    print("=" * 60)

    return {
        "total": len(all_applications),
        "valid": len(valid_applications),
        "orphaned": len(orphaned_applications),
        "deleted": 0 if dry_run else deleted_count if orphaned_applications else 0
    }


def check_orphaned_users():
    """
    Check for users without driver applications (for informational purposes).
    This is usually fine - it means they're regular customers or admins.
    """
    print("\nCHECKING FOR USERS WITHOUT DRIVER APPLICATIONS (informational)")
    print("-" * 60)

    # Get all users with role='driver'
    all_users = list(user_model.find({"role": "driver"}))

    users_without_apps = []

    for user in all_users:
        email = user.get('email')
        app = driver_application_model.find_by_email(email)

        if not app:
            users_without_apps.append(user)

    if users_without_apps:
        print(f"Found {len(users_without_apps)} driver users without applications:")
        print("(This is normal for drivers created before the application system)")
        for user in users_without_apps:
            print(f"  - {user.get('name')} ({user.get('email')}) - Status: {user.get('status')}")
    else:
        print("All driver users have corresponding applications.")

    print()


if __name__ == "__main__":
    # Check command line arguments
    dry_run = True

    if len(sys.argv) > 1:
        if sys.argv[1] == "--live":
            dry_run = False
            print("\n⚠️  WARNING: LIVE MODE - Records will be permanently deleted!")
            response = input("Are you sure you want to continue? (yes/no): ")
            if response.lower() != "yes":
                print("Aborted.")
                sys.exit(0)
        elif sys.argv[1] == "--dry-run":
            dry_run = True
        else:
            print("Usage: python cleanup_orphaned_records.py [--dry-run|--live]")
            sys.exit(1)

    # Run cleanup
    stats = cleanup_orphaned_applications(dry_run=dry_run)

    # Check for users without applications (informational)
    check_orphaned_users()

    print("\nCLEANUP COMPLETE")
    print(f"Total applications checked: {stats['total']}")
    print(f"Orphaned applications found: {stats['orphaned']}")
    if not dry_run and stats['orphaned'] > 0:
        print(f"Records deleted: {stats['deleted']}")
