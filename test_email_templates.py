"""
Email Template Visual Test
Tests the new responsive email templates in development mode
"""

from services.email_service import EmailService
from flask_mail import Mail

def test_email_templates():
    """Test all redesigned email templates"""
    
    # Initialize email service in dev mode
    import os
    os.environ['FLASK_ENV'] = 'development'
    
    from app import app
    with app.app_context():
        email_service = EmailService()
        
        print("\n" + "="*60)
        print("EMAIL TEMPLATE VISUAL TEST")
        print("="*60)
        
        # Test data
        test_order = {
            'order_id': 15,
            'id': 15,
            'status': 'NEW',
            'pickup_address': 'Mannerheimintie 1, Helsinki',
            'dropoff_address': 'Hämeenkatu 10, Tampere',
            'pickup_date': '2025-10-15',
            'pickup_time': '10:00',
            'vehicle_make': 'Toyota',
            'vehicle_model': 'Corolla',
            'distance_km': 178.5,
            'price_gross': 295.50,
            'reg_number': 'ABC-123',
            'winter_tires': True,
            'extras': 'Auton avaimet jätetään oveen',
            'created_at': '2025-10-06 14:30:00'
        }
        
        test_customer = {
            'name': 'Matti Meikäläinen',
            'email': 'matti.meikalainen@example.com'
        }
        
        print("\n1. Testing ORDER CREATED email...")
        print("   Template: order_created.html")
        print("   Theme: Success (Green)")
        print("   Features: Price highlight, order details, no emojis")
        
        from flask import render_template
        html_body = render_template('emails/order_created.html',
                                   order=test_order,
                                   user_name=test_customer['name'])
        
        email_service.send_email(
            subject="Tilausvahvistus - Levoro",
            recipients=[test_customer['email']],
            html_body=html_body
        )
        print("   ✅ Email saved to dev_emails folder")
        
        print("\n2. Testing STATUS UPDATE email (CONFIRMED)...")
        print("   Template: status_update.html")
        print("   Theme: Success (Green)")
        print("   Features: Status badge, dynamic colors, responsive")
        
        test_order['status'] = 'VAHVISTETTU'
        test_order['status_description'] = 'Tilauksesi on vahvistettu ja odottaa noutopäivää'
        html_body = render_template('emails/status_update.html',
                                   order=test_order,
                                   user_name=test_customer['name'],
                                   new_status='CONFIRMED')
        
        email_service.send_email(
            subject="Tilaus vahvistettu - Levoro",
            recipients=[test_customer['email']],
            html_body=html_body
        )
        print("   ✅ Email saved to dev_emails folder")
        
        print("\n3. Testing STATUS UPDATE email (IN_TRANSIT)...")
        print("   Template: status_update.html")
        print("   Theme: Warning (Orange)")
        print("   Features: In-transit notification, route display")
        
        test_order['status'] = 'KULJETUKSESSA'
        test_order['status_description'] = 'Autosi on matkalla määränpäähän'
        html_body = render_template('emails/status_update.html',
                                   order=test_order,
                                   user_name=test_customer['name'],
                                   new_status='IN_TRANSIT')
        
        email_service.send_email(
            subject="Auto kuljetuksessa - Levoro",
            recipients=[test_customer['email']],
            html_body=html_body
        )
        print("   ✅ Email saved to dev_emails folder")
        
        print("\n4. Testing STATUS UPDATE email (DELIVERED)...")
        print("   Template: status_update.html")
        print("   Theme: Success (Green)")
        print("   Features: Completion message, thank you note")
        
        test_order['status'] = 'TOIMITETTU'
        test_order['status_description'] = 'Autosi on toimitettu perille'
        html_body = render_template('emails/status_update.html',
                                   order=test_order,
                                   user_name=test_customer['name'],
                                   new_status='DELIVERED')
        
        email_service.send_email(
            subject="Auto toimitettu - Levoro",
            recipients=[test_customer['email']],
            html_body=html_body
        )
        print("   ✅ Email saved to dev_emails folder")
        
        print("\n5. Testing ADMIN NEW ORDER email...")
        print("   Template: admin_new_order.html")
        print("   Theme: Warning (Orange)")
        print("   Features: Action buttons, complete details, route visualization")
        
        test_order['status'] = 'NEW'
        html_body = render_template('emails/admin_new_order.html',
                                   order=test_order,
                                   customer=test_customer,
                                   admin_url='http://localhost:8000/admin',
                                   order_detail_url=f'http://localhost:8000/admin/order/{test_order["id"]}')
        
        email_service.send_email(
            subject="Uusi tilaus #15 - Levoro Admin",
            recipients=['support@levoro.fi'],
            html_body=html_body
        )
        print("   ✅ Email saved to dev_emails folder")
        
        print("\n" + "="*60)
        print("EMAIL TEMPLATE TEST COMPLETE!")
        print("="*60)
        print("\n📧 All emails saved to: static/dev_emails/")
        print("🌐 View inbox at: http://localhost:8000/static/dev_emails/index.html")
        print("\n✅ Features Tested:")
        print("   • Responsive table-based layout")
        print("   • Blue theme system (#3b82f6)")
        print("   • NO EMOJIS - professional text labels")
        print("   • Status badges with colors")
        print("   • Price highlighting")
        print("   • Mobile-friendly buttons")
        print("   • Proper typography hierarchy")
        print("\n🎨 Templates Updated:")
        print("   1. order_created.html (Customer order confirmation)")
        print("   2. status_update.html (Customer status updates)")
        print("   3. admin_new_order.html (Admin notifications)")
        print("\n📱 Test on Mobile:")
        print("   Open the inbox on your phone to see responsive design!")
        print("\n" + "="*60 + "\n")

if __name__ == '__main__':
    test_email_templates()
