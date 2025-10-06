"""
Data Integrity Check Script
============================
Detects inconsistencies in the database between users, driver applications, and driver accounts.

Run this script periodically to identify data integrity issues.

Usage:
    python check_data_integrity.py
"""

import os
from dotenv import load_dotenv
from collections import defaultdict

# Load environment variables
load_dotenv()

# Import database models
from models.database import db_manager
from models.user import user_model
from models.driver_application import driver_application_model


def check_duplicate_emails():
    """Check for duplicate emails across users and driver applications"""
    print("\n" + "=" * 70)
    print("CHECKING FOR DUPLICATE EMAILS")
    print("=" * 70)

    # Get all users
    all_users = list(user_model.find())

    # Get all driver applications
    all_applications = list(driver_application_model.find())

    # Create email mapping
    email_map = defaultdict(list)

    # Add users to email map
    for user in all_users:
        email = user.get('email', '').lower()
        if email:
            email_map[email].append({
                'type': 'user',
                'id': user.get('id'),
                'name': user.get('name'),
                'role': user.get('role'),
                'status': user.get('status')
            })

    # Add driver applications to email map
    for app in all_applications:
        email = app.get('email', '').lower()
        if email:
            email_map[email].append({
                'type': 'driver_application',
                'id': app.get('id'),
                'name': app.get('name'),
                'status': app.get('status')
            })

    # Find duplicates
    duplicates = {email: entries for email, entries in email_map.items() if len(entries) > 1}

    if duplicates:
        print(f"\n✗ DUPLICATE EMAILS FOUND: {len(duplicates)}")
        print("-" * 70)
        for email, entries in duplicates.items():
            print(f"\n📧 {email}")
            for entry in entries:
                if entry['type'] == 'user':
                    print(f"   • User #{entry['id']} - {entry['name']} ({entry['role']}) - {entry['status']}")
                else:
                    print(f"   • Driver Application #{entry['id']} - {entry['name']} - {entry['status']}")
        print()
    else:
        print("\n✓ No duplicate emails found")

    return duplicates


def check_orphaned_approved_applications():
    """Check for approved driver applications without corresponding driver accounts"""
    print("\n" + "=" * 70)
    print("CHECKING FOR ORPHANED APPROVED APPLICATIONS")
    print("=" * 70)

    # Get all approved applications
    approved_apps = list(driver_application_model.find({"status": "approved"}))

    orphaned = []

    for app in approved_apps:
        email = app.get('email')

        # Check if corresponding driver user exists
        user = user_model.find_by_email(email)

        if not user or user.get('role') != 'driver':
            orphaned.append(app)

    if orphaned:
        print(f"\n✗ ORPHANED APPROVED APPLICATIONS FOUND: {len(orphaned)}")
        print("-" * 70)
        for app in orphaned:
            print(f"\n   Application #{app.get('id')}")
            print(f"   Name: {app.get('name')}")
            print(f"   Email: {app.get('email')}")
            print(f"   Status: {app.get('status')}")
            print(f"   Approved: {app.get('processed_at')}")
            print(f"   → No corresponding driver account found!")
        print()
    else:
        print("\n✓ All approved applications have corresponding driver accounts")

    return orphaned


def check_drivers_without_applications():
    """Check for driver accounts without driver applications (informational - not an error)"""
    print("\n" + "=" * 70)
    print("CHECKING FOR DRIVERS WITHOUT APPLICATIONS (informational)")
    print("=" * 70)

    # Get all driver users
    drivers = list(user_model.find({"role": "driver"}))

    without_apps = []

    for driver in drivers:
        email = driver.get('email')

        # Check if driver application exists
        app = driver_application_model.find_by_email(email)

        if not app:
            without_apps.append(driver)

    if without_apps:
        print(f"\nℹ️  DRIVERS WITHOUT APPLICATIONS: {len(without_apps)}")
        print("-" * 70)
        print("(This is normal for legacy drivers created before the application system)")
        for driver in without_apps:
            print(f"   • Driver #{driver.get('id')} - {driver.get('name')} ({driver.get('email')})")
        print()
    else:
        print("\n✓ All drivers have corresponding applications")

    return without_apps


def check_pending_applications_with_accounts():
    """Check for pending driver applications that already have user accounts"""
    print("\n" + "=" * 70)
    print("CHECKING FOR PENDING APPLICATIONS WITH EXISTING ACCOUNTS")
    print("=" * 70)

    # Get all pending applications
    pending_apps = list(driver_application_model.find({"status": "pending"}))

    conflicts = []

    for app in pending_apps:
        email = app.get('email')

        # Check if user account exists
        user = user_model.find_by_email(email)

        if user:
            conflicts.append({
                'application': app,
                'user': user
            })

    if conflicts:
        print(f"\n✗ PENDING APPLICATIONS WITH EXISTING ACCOUNTS: {len(conflicts)}")
        print("-" * 70)
        print("(These should be resolved - either approve or deny the application)")
        for conflict in conflicts:
            app = conflict['application']
            user = conflict['user']
            print(f"\n   Application #{app.get('id')} - {app.get('name')}")
            print(f"   Email: {app.get('email')}")
            print(f"   Existing User: #{user.get('id')} ({user.get('role')}) - {user.get('status')}")
        print()
    else:
        print("\n✓ No pending applications with existing accounts")

    return conflicts


def generate_summary(duplicates, orphaned_apps, drivers_without_apps, conflicts):
    """Generate summary report"""
    print("\n" + "=" * 70)
    print("DATA INTEGRITY SUMMARY")
    print("=" * 70)

    total_issues = len(duplicates) + len(orphaned_apps) + len(conflicts)

    print(f"\n🔍 Duplicate Emails: {len(duplicates)}")
    print(f"🔍 Orphaned Approved Applications: {len(orphaned_apps)}")
    print(f"🔍 Pending Apps with Existing Accounts: {len(conflicts)}")
    print(f"ℹ️  Drivers without Applications: {len(drivers_without_apps)} (informational)")

    print("\n" + "=" * 70)

    if total_issues == 0:
        print("✅ NO CRITICAL ISSUES FOUND - Database integrity is good!")
    else:
        print(f"⚠️  {total_issues} CRITICAL ISSUES FOUND - Please review and fix")

    print("=" * 70)
    print()


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "DATA INTEGRITY CHECK" + " " * 28 + "║")
    print("╚" + "=" * 68 + "╝")

    # Run all checks
    duplicates = check_duplicate_emails()
    orphaned_apps = check_orphaned_approved_applications()
    drivers_without_apps = check_drivers_without_applications()
    conflicts = check_pending_applications_with_accounts()

    # Generate summary
    generate_summary(duplicates, orphaned_apps, drivers_without_apps, conflicts)

    print("Check complete!")
    print()
