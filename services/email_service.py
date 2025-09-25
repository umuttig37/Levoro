"""
Email Service
Handles email sending functionality using Zoho SMTP
"""

import os
from typing import Dict, Optional, List
from flask import render_template, current_app
from flask_mail import Mail, Message


class EmailService:
    """Service for handling email operations with Zoho SMTP"""

    def __init__(self, mail_instance: Mail = None):
        self.mail = mail_instance

    def configure_mail(self, app):
        """Configure Flask-Mail with Zoho SMTP settings"""
        # Zoho SMTP configuration
        app.config['MAIL_SERVER'] = os.getenv('ZOHO_SMTP_SERVER', 'smtppro.zoho.com')
        app.config['MAIL_PORT'] = int(os.getenv('ZOHO_SMTP_PORT', '465'))
        app.config['MAIL_USE_SSL'] = os.getenv('ZOHO_USE_SSL', 'true').lower() == 'true'
        app.config['MAIL_USE_TLS'] = os.getenv('ZOHO_USE_TLS', 'false').lower() == 'true'
        app.config['MAIL_USERNAME'] = os.getenv('ZOHO_EMAIL', '')
        app.config['MAIL_PASSWORD'] = os.getenv('ZOHO_PASSWORD', '')
        app.config['MAIL_DEFAULT_SENDER'] = os.getenv('ZOHO_EMAIL', '')

        # Initialize Flask-Mail
        if self.mail is None:
            self.mail = Mail(app)
        else:
            self.mail.init_app(app)

        return self.mail

    def send_email(self, subject: str, recipients: List[str], html_body: str,
                   text_body: str = None, sender: str = None) -> bool:
        """
        Send an email using Flask-Mail and Zoho SMTP

        Args:
            subject: Email subject
            recipients: List of recipient email addresses
            html_body: HTML email content
            text_body: Plain text email content (optional)
            sender: Sender email address (optional, uses default if not provided)

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        # Log email attempt details
        print(f"📧 EMAIL ATTEMPT:")
        print(f"   From: {sender or current_app.config.get('MAIL_DEFAULT_SENDER', 'N/A')}")
        print(f"   To: {recipients}")
        print(f"   Subject: {subject}")
        print(f"   SMTP Server: {current_app.config.get('MAIL_SERVER', 'N/A')}")
        print(f"   SMTP Port: {current_app.config.get('MAIL_PORT', 'N/A')}")
        print(f"   Use SSL: {current_app.config.get('MAIL_USE_SSL', 'N/A')}")
        print(f"   Username: {current_app.config.get('MAIL_USERNAME', 'N/A')}")

        try:
            if not self.mail:
                error_msg = "❌ Mail instance not configured"
                current_app.logger.error(error_msg)
                print(f"   {error_msg}")
                return False

            if not recipients:
                error_msg = "❌ No recipients provided"
                current_app.logger.error(error_msg)
                print(f"   {error_msg}")
                return False

            print(f"   📝 Creating email message...")
            msg = Message(
                subject=subject,
                recipients=recipients,
                html=html_body,
                body=text_body or self._html_to_text(html_body),
                sender=sender
            )

            print(f"   🚀 Attempting to send via Zoho SMTP...")
            self.mail.send(msg)

            success_msg = f"✅ Email sent successfully to {recipients}"
            current_app.logger.info(success_msg)
            print(f"   {success_msg}")
            return True

        except Exception as e:
            error_msg = f"❌ Failed to send email: {str(e)}"
            current_app.logger.error(error_msg)
            print(f"   {error_msg}")

            # Log additional SMTP debug info
            if "552" in str(e):
                print(f"   🚫 SMTP Error 552: IP Address blocked by Zoho")
                print(f"   💡 This is common in development environments like Codespaces")
                print(f"   📍 Solution: Test from production server or use different SMTP provider for dev")
            elif "authentication" in str(e).lower():
                print(f"   🔐 Authentication issue: Check ZOHO_EMAIL and ZOHO_PASSWORD")
            elif "connection" in str(e).lower():
                print(f"   🔌 Connection issue: Check SMTP server/port settings")

            return False

    def send_registration_email(self, user_email: str, user_name: str) -> bool:
        """Send welcome email after user registration"""
        try:
            html_body = render_template('emails/registration.html',
                                      user_name=user_name)

            return self.send_email(
                subject="Tervetuloa Levoroon - Rekisteröinti vastaanotettu",
                recipients=[user_email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send registration email: {str(e)}")
            return False

    def send_account_approved_email(self, user_email: str, user_name: str) -> bool:
        """Send email when user account is approved"""
        try:
            html_body = render_template('emails/account_approved.html',
                                      user_name=user_name)

            return self.send_email(
                subject="Tilisi on hyväksytty - Tervetuloa Levoroon!",
                recipients=[user_email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send account approved email: {str(e)}")
            return False

    def send_order_created_email(self, user_email: str, user_name: str, order_data: Dict) -> bool:
        """Send email when new order is created"""
        print(f"📦 ORDER CREATED EMAIL:")
        print(f"   Recipient: {user_name} <{user_email}>")
        print(f"   Order ID: #{order_data.get('id')}")
        print(f"   Route: {order_data.get('pickup_address')} → {order_data.get('dropoff_address')}")
        print(f"   Price: {order_data.get('price_gross', 0)} €")

        try:
            # Format order data for template
            order_info = {
                'order_id': order_data.get('id'),
                'pickup_address': order_data.get('pickup_address', ''),
                'dropoff_address': order_data.get('dropoff_address', ''),
                'pickup_date': order_data.get('pickup_date', ''),
                'pickup_time': order_data.get('pickup_time', ''),
                'vehicle_make': order_data.get('vehicle_make', ''),
                'vehicle_model': order_data.get('vehicle_model', ''),
                'price_gross': order_data.get('price_gross', 0),
                'distance_km': order_data.get('distance_km', 0)
            }

            print(f"   📝 Rendering order confirmation template...")
            html_body = render_template('emails/order_created.html',
                                      user_name=user_name,
                                      order=order_info)

            print(f"   📧 Sending order confirmation email...")
            return self.send_email(
                subject=f"Tilausvahvistus #{order_data.get('id')} - Levoro",
                recipients=[user_email],
                html_body=html_body
            )
        except Exception as e:
            error_msg = f"Failed to send order created email: {str(e)}"
            current_app.logger.error(error_msg)
            print(f"   ❌ {error_msg}")
            return False

    def send_status_update_email(self, user_email: str, user_name: str, order_data: Dict,
                               new_status: str, status_description: str) -> bool:
        """Send email when order status changes"""
        # Status translations for email subject
        status_translations = {
            'NEW': 'Uusi tilaus',
            'CONFIRMED': 'Tilaus vahvistettu',
            'IN_TRANSIT': 'Kuljetus aloitettu',
            'DELIVERED': 'Toimitettu',
            'CANCELLED': 'Peruutettu'
        }

        status_finnish = status_translations.get(new_status, new_status)

        print(f"📊 ORDER STATUS UPDATE EMAIL:")
        print(f"   Recipient: {user_name} <{user_email}>")
        print(f"   Order ID: #{order_data.get('id')}")
        print(f"   Status Change: {new_status} ({status_finnish})")
        print(f"   Description: {status_description}")
        print(f"   Route: {order_data.get('pickup_address')} → {order_data.get('dropoff_address')}")

        try:
            order_info = {
                'order_id': order_data.get('id'),
                'pickup_address': order_data.get('pickup_address', ''),
                'dropoff_address': order_data.get('dropoff_address', ''),
                'vehicle_make': order_data.get('vehicle_make', ''),
                'vehicle_model': order_data.get('vehicle_model', ''),
                'status': status_finnish,
                'status_description': status_description
            }

            print(f"   📝 Rendering status update template...")
            html_body = render_template('emails/status_update.html',
                                      user_name=user_name,
                                      order=order_info,
                                      new_status=new_status)

            print(f"   📧 Sending status update email...")
            return self.send_email(
                subject=f"Tilaus #{order_data.get('id')} - {status_finnish}",
                recipients=[user_email],
                html_body=html_body
            )
        except Exception as e:
            error_msg = f"Failed to send status update email: {str(e)}"
            current_app.logger.error(error_msg)
            print(f"   ❌ {error_msg}")
            return False

    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML content to plain text (simple implementation)"""
        try:
            # Simple HTML to text conversion
            import re
            # Remove HTML tags
            text = re.sub('<[^<]+?>', '', html_content)
            # Replace HTML entities
            text = text.replace('&nbsp;', ' ')
            text = text.replace('&lt;', '<')
            text = text.replace('&gt;', '>')
            text = text.replace('&amp;', '&')
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
        except Exception:
            return html_content


# Global instance
email_service = EmailService()