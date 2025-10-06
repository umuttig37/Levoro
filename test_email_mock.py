"""
Test Development Email Mock System
Run this script to verify the email mock system is working correctly
"""

import os
import sys

# Set development mode
os.environ['FLASK_ENV'] = 'development'

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_email_mock():
    """Test the email mock system"""
    from flask import Flask
    from services.email_service import email_service
    
    print("=" * 60)
    print("Testing Development Email Mock System")
    print("=" * 60)
    print()
    
    # Create minimal Flask app
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-key'
    
    # Configure email service
    email_service.configure_mail(app)
    
    with app.app_context():
        print("📧 Test 1: Customer Order Confirmation Email")
        print("-" * 60)
        success1 = email_service.send_order_created_email(
            user_email="customer@example.com",
            user_name="Testi Asiakas",
            order_data={
                'id': 999,
                'pickup_address': 'Helsinki, Mannerheimintie 1',
                'dropoff_address': 'Tampere, Hämeenkatu 10',
                'pickup_date': '2025-10-15',
                'pickup_time': '10:00',
                'vehicle_make': 'Toyota',
                'vehicle_model': 'Corolla',
                'price_gross': 150.0,
                'distance_km': 175
            }
        )
        print(f"Result: {'✅ Success' if success1 else '❌ Failed'}")
        print()
        
        print("📧 Test 2: Admin Order Notification Email")
        print("-" * 60)
        success2 = email_service.send_admin_new_order_notification(
            order_data={
                'id': 999,
                'status': 'NEW',
                'pickup_address': 'Helsinki, Mannerheimintie 1',
                'dropoff_address': 'Tampere, Hämeenkatu 10',
                'distance_km': 175,
                'price_gross': 150.0
            },
            customer_data={
                'name': 'Testi Asiakas',
                'email': 'customer@example.com',
                'phone': '+358 40 1234567'
            }
        )
        print(f"Result: {'✅ Success' if success2 else '❌ Failed'}")
        print()
        
        print("📧 Test 3: Admin Driver Action Notification")
        print("-" * 60)
        success3 = email_service.send_admin_driver_action_notification(
            order_id=999,
            driver_name="Testi Kuljettaja",
            action="ASSIGNED_TO_DRIVER",
            order_data={
                'id': 999,
                'pickup_address': 'Helsinki, Mannerheimintie 1',
                'dropoff_address': 'Tampere, Hämeenkatu 10',
                'distance_km': 175,
                'reg_number': 'ABC-123'
            }
        )
        print(f"Result: {'✅ Success' if success3 else '❌ Failed'}")
        print()
    
    print("=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print()
    print("📋 View emails at:")
    print("   http://localhost:8000/static/dev_emails/index.html")
    print()
    print("📁 Or check the folder:")
    print("   static/dev_emails/")
    print()
    
    # Count emails
    emails_dir = 'static/dev_emails'
    if os.path.exists(emails_dir):
        email_files = [f for f in os.listdir(emails_dir) if f.endswith('.html') and f != 'index.html']
        print(f"✅ Generated {len(email_files)} email files")
    else:
        print("⚠️ Email directory not found")

if __name__ == '__main__':
    test_email_mock()
