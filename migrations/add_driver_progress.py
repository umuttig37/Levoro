"""
Database Migration: Add driver_progress field to all orders

This migration adds the driver_progress field to all existing orders
and infers progress state from current order status and images.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path so we can import models
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from models.order import order_model


def migrate_driver_progress():
    """Add driver_progress field to all orders"""
    print("[MIGRATION] Starting driver_progress field migration...")

    # Get all orders (use find from collection directly to avoid projection)
    orders = list(order_model.collection.find({}))

    migrated_count = 0
    skipped_count = 0

    for order in orders:
        order_id = order['id']

        # Skip if driver_progress already exists
        if 'driver_progress' in order and order['driver_progress']:
            print(f"  [SKIP] Order #{order_id} already has driver_progress")
            skipped_count += 1
            continue

        driver_progress = {}

        # Infer progress from current status and images
        status = order.get('status')
        images = order.get('images', {})
        pickup_images = images.get('pickup', [])
        delivery_images = images.get('delivery', [])

        # Handle old single-image format
        if not isinstance(pickup_images, list):
            pickup_images = [pickup_images] if pickup_images else []
        if not isinstance(delivery_images, list):
            delivery_images = [delivery_images] if delivery_images else []

        pickup_count = len(pickup_images)
        delivery_count = len(delivery_images)

        # Set notified=True to avoid duplicate emails for existing progress
        if status in ['DRIVER_ARRIVED', 'PICKUP_IMAGES_ADDED', 'IN_TRANSIT',
                      'DELIVERY_ARRIVED', 'DELIVERY_IMAGES_ADDED', 'DELIVERED']:
            driver_progress['arrived_at_pickup'] = {
                'timestamp': order.get('arrival_time') or order.get('updated_at') or datetime.now(timezone.utc),
                'notified': True
            }

        if status in ['PICKUP_IMAGES_ADDED', 'IN_TRANSIT', 'DELIVERY_ARRIVED',
                      'DELIVERY_IMAGES_ADDED', 'DELIVERED']:
            if pickup_count > 0:
                driver_progress['pickup_images_complete'] = {
                    'timestamp': order.get('pickup_started') or order.get('updated_at') or datetime.now(timezone.utc),
                    'count': pickup_count,
                    'notified': True
                }

        if status in ['IN_TRANSIT', 'DELIVERY_ARRIVED', 'DELIVERY_IMAGES_ADDED', 'DELIVERED']:
            driver_progress['started_transit'] = {
                'timestamp': order.get('pickup_started') or order.get('updated_at') or datetime.now(timezone.utc),
                'notified': True
            }

        if status in ['DELIVERY_ARRIVED', 'DELIVERY_IMAGES_ADDED', 'DELIVERED']:
            driver_progress['arrived_at_delivery'] = {
                'timestamp': order.get('delivery_arrival_time') or order.get('updated_at') or datetime.now(timezone.utc),
                'notified': True
            }

        if status in ['DELIVERY_IMAGES_ADDED', 'DELIVERED']:
            if delivery_count > 0:
                driver_progress['delivery_images_complete'] = {
                    'timestamp': order.get('delivery_completed') or order.get('updated_at') or datetime.now(timezone.utc),
                    'count': delivery_count,
                    'notified': True
                }

        if status == 'DELIVERED':
            driver_progress['marked_complete'] = {
                'timestamp': order.get('delivery_completed') or order.get('updated_at') or datetime.now(timezone.utc),
                'notified': True
            }

        # Update order with driver_progress
        try:
            order_model.update_one(
                {'id': order_id},
                {'$set': {'driver_progress': driver_progress}}
            )
            print(f"  [OK] Order #{order_id}: Added driver_progress with {len(driver_progress)} progress points")
            migrated_count += 1
        except Exception as e:
            print(f"  [ERROR] Order #{order_id}: Failed to migrate - {str(e)}")

    print(f"\n[MIGRATION COMPLETE]")
    print(f"  - Migrated: {migrated_count} orders")
    print(f"  - Skipped: {skipped_count} orders (already had driver_progress)")
    print(f"  - Total processed: {len(orders)} orders")


if __name__ == "__main__":
    print("=" * 60)
    print("Driver Progress Field Migration")
    print("=" * 60)

    # Confirm before running
    response = input("\nThis will add driver_progress field to all orders.\nContinue? (yes/no): ")

    if response.lower() in ['yes', 'y']:
        migrate_driver_progress()
    else:
        print("[CANCELLED] Migration cancelled by user")
