"""
Complete Driver Cleanup Script
===============================
Removes ALL driver-related records from the database with backup.

This script:
1. Creates database backup (optional, but highly recommended)
2. Finds all driver applications (all statuses)
3. Finds all user accounts with role="driver"
4. Finds duplicate customer accounts with emails matching driver applications
5. Deletes all found records (in --live mode)

IMPORTANT: Creates backup before any changes!

Usage:
    # Dry-run (see what would be deleted, creates backup)
    python cleanup_all_drivers.py

    # Actually delete everything (with backup and confirmation)
    python cleanup_all_drivers.py --live

    # Create backup only
    python cleanup_all_drivers.py --backup-only

    # Delete without backup (NOT RECOMMENDED)
    python cleanup_all_drivers.py --live --no-backup
"""

import os
import sys
import subprocess
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import database models
from models.database import db_manager
from models.user import user_model
from models.driver_application import driver_application_model


def create_backup():
    """Create MongoDB backup using mongodump"""
    print("\n[1/5] Creating database backup...")
    print("─" * 70)

    # Get MongoDB URI from environment
    mongodb_uri = os.getenv('MONGODB_URI')
    if not mongodb_uri:
        print("✗ ERROR: MONGODB_URI not found in environment variables")
        return None

    # Create backup directory with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f"backups/mongodb_backup_{timestamp}"

    # Create backups directory if it doesn't exist
    os.makedirs("backups", exist_ok=True)

    # Run mongodump
    try:
        print(f"Creating backup to: {backup_dir}/")

        # Use mongodump command
        result = subprocess.run(
            ['mongodump', f'--uri={mongodb_uri}', f'--out={backup_dir}'],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            # Check backup size
            backup_size = get_directory_size(backup_dir)
            print(f"✓ Backup created: {backup_dir}/")
            print(f"✓ Backup size: {backup_size:.1f} MB")
            return backup_dir
        else:
            print(f"✗ Backup failed: {result.stderr}")
            return None

    except FileNotFoundError:
        print("✗ ERROR: mongodump not found. Install MongoDB Database Tools:")
        print("  https://www.mongodb.com/docs/database-tools/installation/installation/")
        return None
    except subprocess.TimeoutExpired:
        print("✗ ERROR: Backup timed out after 60 seconds")
        return None
    except Exception as e:
        print(f"✗ ERROR creating backup: {str(e)}")
        return None


def get_directory_size(path):
    """Get directory size in MB"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
    return total_size / (1024 * 1024)  # Convert to MB


def find_driver_applications():
    """Find all driver applications"""
    print("\n[2/5] Finding driver applications...")
    print("─" * 70)

    applications = list(driver_application_model.find())

    if applications:
        print(f"Found {len(applications)} driver applications:")
        for app in applications:
            print(f"  #{app.get('id')} - {app.get('name')} ({app.get('email')}) - {app.get('status')}")
    else:
        print("No driver applications found")

    return applications


def find_driver_users():
    """Find all user accounts with role='driver'"""
    print("\n[3/5] Finding driver user accounts...")
    print("─" * 70)

    drivers = list(user_model.find({"role": "driver"}))

    if drivers:
        print(f"Found {len(drivers)} driver users:")
        for driver in drivers:
            print(f"  #{driver.get('id')} - {driver.get('name')} ({driver.get('email')}) - {driver.get('status')}")
    else:
        print("No driver users found")

    return drivers


def find_duplicate_users(applications):
    """Find customer accounts with emails matching driver applications"""
    print("\n[4/5] Finding duplicate accounts...")
    print("─" * 70)

    duplicates = []

    # Get all application emails
    app_emails = {app.get('email').lower() for app in applications if app.get('email')}

    # Find users (non-drivers) with matching emails
    for email in app_emails:
        user = user_model.find_by_email(email)
        if user and user.get('role') != 'driver':
            duplicates.append(user)

    if duplicates:
        print(f"Found {len(duplicates)} duplicate(s):")
        for dup in duplicates:
            print(f"  #{dup.get('id')} - {dup.get('name')} ({dup.get('email')}) - {dup.get('role')} - {dup.get('status')}")
            # Find matching application
            matching_app = next((app for app in applications if app.get('email').lower() == dup.get('email').lower()), None)
            if matching_app:
                print(f"    (matches driver application #{matching_app.get('id')})")
    else:
        print("No duplicate accounts found")

    return duplicates


def show_summary(applications, drivers, duplicates):
    """Show summary of what will be deleted"""
    print("\n[5/5] Summary")
    print("─" * 70)
    print("Total records to delete:")
    print(f"  • Driver applications: {len(applications)}")
    print(f"  • Driver user accounts: {len(drivers)}")
    print(f"  • Duplicate customer accounts: {len(duplicates)}")
    print(f"  • Total: {len(applications) + len(drivers) + len(duplicates)} records")


def delete_all_records(applications, drivers, duplicates):
    """Delete all driver-related records"""
    from app import users_col

    stats = {
        'applications_deleted': 0,
        'drivers_deleted': 0,
        'duplicates_deleted': 0,
        'errors': 0
    }

    # Delete driver applications
    if applications:
        print("\nDeleting driver applications...")
        for app in applications:
            try:
                driver_application_model.delete_one({"id": app['id']})
                stats['applications_deleted'] += 1
                print(f"  ✓ Deleted application #{app['id']} ({app['name']})")
            except Exception as e:
                stats['errors'] += 1
                print(f"  ✗ Failed to delete application #{app['id']}: {str(e)}")

    # Delete driver users
    if drivers:
        print("\nDeleting driver user accounts...")
        for driver in drivers:
            try:
                users_col().delete_one({"id": driver['id']})
                stats['drivers_deleted'] += 1
                print(f"  ✓ Deleted user #{driver['id']} ({driver['name']} - driver)")
            except Exception as e:
                stats['errors'] += 1
                print(f"  ✗ Failed to delete user #{driver['id']}: {str(e)}")

    # Delete duplicate customers
    if duplicates:
        print("\nDeleting duplicate customer accounts...")
        for dup in duplicates:
            try:
                users_col().delete_one({"id": dup['id']})
                stats['duplicates_deleted'] += 1
                print(f"  ✓ Deleted user #{dup['id']} ({dup['name']} - {dup['role']})")
            except Exception as e:
                stats['errors'] += 1
                print(f"  ✗ Failed to delete user #{dup['id']}: {str(e)}")

    return stats


def main():
    """Main execution"""
    # Parse command line arguments
    dry_run = True
    create_backup_flag = True

    if len(sys.argv) > 1:
        if '--live' in sys.argv:
            dry_run = False
        if '--no-backup' in sys.argv:
            create_backup_flag = False
        if '--backup-only' in sys.argv:
            print("\n" + "═" * 70)
            print("BACKUP ONLY MODE")
            print("═" * 70)
            backup_dir = create_backup()
            if backup_dir:
                print(f"\n✓ Backup completed: {backup_dir}/")
            else:
                print("\n✗ Backup failed")
            return

    # Print header
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 18 + "COMPLETE DRIVER CLEANUP SCRIPT" + " " * 20 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    print("═" * 70)
    print("COMPLETE DRIVER CLEANUP SCRIPT")
    print("═" * 70)

    if dry_run:
        print("Mode: DRY RUN (no changes will be made)")
    else:
        print("Mode: LIVE (records will be PERMANENTLY deleted)")

    # Create backup
    backup_dir = None
    if create_backup_flag:
        backup_dir = create_backup()
        if not backup_dir and not dry_run:
            print("\n✗ ERROR: Backup failed. Cannot proceed without backup.")
            print("  Use --no-backup flag to skip backup (NOT RECOMMENDED)")
            return
    else:
        print("\n⚠️  WARNING: Backup skipped (--no-backup flag used)")

    # Find all records
    applications = find_driver_applications()
    drivers = find_driver_users()
    duplicates = find_duplicate_users(applications)

    # Show summary
    show_summary(applications, drivers, duplicates)

    total_records = len(applications) + len(drivers) + len(duplicates)

    if total_records == 0:
        print("\n✓ No driver-related records found. Nothing to delete.")
        return

    # Dry run completion
    if dry_run:
        print("\n" + "═" * 70)
        print("DRY RUN COMPLETE")
        print("═" * 70)
        print("\nNo changes were made.", end="")
        if backup_dir:
            print(f" Database backup created at:")
            print(f"  {backup_dir}/")
        else:
            print()
        print("\nTo actually delete these records, run:")
        print("  python cleanup_all_drivers.py --live")
        return

    # Live mode - get confirmation
    print("\n" + "═" * 70)
    print("⚠️  FINAL CONFIRMATION REQUIRED")
    print("═" * 70)
    print(f"\nYou are about to PERMANENTLY DELETE:")
    print(f"  • {len(applications)} driver applications")
    print(f"  • {len(drivers)} driver user accounts")
    print(f"  • {len(duplicates)} duplicate customer account(s)")
    print(f"\nTotal: {total_records} records will be deleted")

    if backup_dir:
        print(f"\nDatabase backup created: {backup_dir}/")

    print("\nType 'DELETE ALL DRIVERS' to confirm: ", end="")
    confirmation = input().strip()

    if confirmation != "DELETE ALL DRIVERS":
        print("\n✗ Aborted. No changes made.")
        return

    print("\nProceeding with deletion...")

    # Delete everything
    stats = delete_all_records(applications, drivers, duplicates)

    # Final summary
    print("\n" + "═" * 70)
    print("CLEANUP COMPLETE")
    print("═" * 70)
    print("\nSuccessfully deleted:")
    print(f"  ✓ {stats['applications_deleted']} driver applications")
    print(f"  ✓ {stats['drivers_deleted']} driver users")
    print(f"  ✓ {stats['duplicates_deleted']} duplicate customer(s)")
    print(f"  ✓ Total: {stats['applications_deleted'] + stats['drivers_deleted'] + stats['duplicates_deleted']} records")

    if stats['errors'] > 0:
        print(f"\n  ✗ {stats['errors']} errors occurred")

    if backup_dir:
        print(f"\nBackup location: {backup_dir}/")
        print("\nTo restore from backup if needed:")
        print(f'  mongorestore --uri="<MONGODB_URI>" {backup_dir}/')

    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user. No changes made.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
