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
        self.dev_mode = os.getenv('FLASK_ENV', 'production') == 'development'

    def configure_mail(self, app):
        """Configure Flask-Mail with Zoho SMTP settings"""
        # Zoho SMTP configuration
        app.config['MAIL_SERVER'] = os.getenv('ZOHO_SMTP_SERVER', 'smtppro.zoho.com')
        app.config['MAIL_PORT'] = int(os.getenv('ZOHO_SMTP_PORT', '465'))
        app.config['MAIL_USE_SSL'] = os.getenv('ZOHO_USE_SSL', 'true').lower() == 'true'
        app.config['MAIL_USE_TLS'] = os.getenv('ZOHO_USE_TLS', 'false').lower() == 'true'
        app.config['MAIL_USERNAME'] = os.getenv('ZOHO_EMAIL', '')
        app.config['MAIL_PASSWORD'] = os.getenv('ZOHO_PASSWORD', '')
        app.config['MAIL_DEFAULT_SENDER'] = os.getenv('ZOHO_EMAIL', 'support@levoro.fi')

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
        In development mode, saves emails as HTML files instead of sending

        Args:
            subject: Email subject
            recipients: List of recipient email addresses
            html_body: HTML email content
            text_body: Plain text email content (optional)
            sender: Sender email address (optional, uses default if not provided)

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        # Re-check environment on each send for safety (prevents accidental dev mode in production)
        flask_env = os.getenv('FLASK_ENV', 'production').lower()
        is_dev_mode = flask_env == 'development'
        
        # Log email attempt details
        print(f"[EMAIL] Attempting to send email")
        print(f"   Environment: {flask_env.upper()}")
        print(f"   From: {sender or current_app.config.get('MAIL_DEFAULT_SENDER', 'N/A')}")
        print(f"   To: {recipients}")
        print(f"   Subject: {subject}")
        
        # In development mode, save email to file instead of sending
        if is_dev_mode:
            print(f"   [DEV MODE] Saving email to file instead of sending...")
            return self._save_email_to_file(subject, recipients, html_body, sender)
        
        print(f"   SMTP Server: {current_app.config.get('MAIL_SERVER', 'N/A')}")
        print(f"   SMTP Port: {current_app.config.get('MAIL_PORT', 'N/A')}")
        print(f"   Use SSL: {current_app.config.get('MAIL_USE_SSL', 'N/A')}")
        print(f"   Username: {current_app.config.get('MAIL_USERNAME', 'N/A')}")

        try:
            if not self.mail:
                error_msg = "[ERROR] Mail instance not configured"
                current_app.logger.error(error_msg)
                print(f"   {error_msg}")
                return False

            if not recipients:
                error_msg = "[ERROR] No recipients provided"
                current_app.logger.error(error_msg)
                print(f"   {error_msg}")
                return False

            print(f"   [CREATE] Creating email message...")
            msg = Message(
                subject=subject,
                recipients=recipients,
                html=html_body,
                body=text_body or self._html_to_text(html_body),
                sender=sender
            )

            print(f"   [SEND] Attempting to send via Zoho SMTP...")
            self.mail.send(msg)

            success_msg = f"[SUCCESS] Email sent successfully to {recipients}"
            current_app.logger.info(success_msg)
            print(f"   {success_msg}")
            return True

        except Exception as e:
            error_msg = f"[ERROR] Failed to send email: {str(e)}"
            current_app.logger.error(error_msg)
            print(f"   {error_msg}")

            # Log additional SMTP debug info
            if "552" in str(e):
                print(f"   [BLOCKED] SMTP Error 552: IP Address blocked by Zoho")
                print(f"   [INFO] This is common in development environments like Codespaces")
                print(f"   [TIP] Solution: Test from production server or use different SMTP provider for dev")
            elif "authentication" in str(e).lower():
                print(f"   [AUTH] Authentication issue: Check ZOHO_EMAIL and ZOHO_PASSWORD")
            elif "connection" in str(e).lower():
                print(f"   [CONN] Connection issue: Check SMTP server/port settings")

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

    def send_password_reset_email(self, user_email: str, user_name: str, reset_url: str, token: str) -> bool:
        """Send password reset email with reset link"""
        print(f"🔐 PASSWORD RESET EMAIL:")
        print(f"   Recipient: {user_name} <{user_email}>")
        print(f"   Reset URL: {reset_url}")
        
        try:
            html_body = render_template('emails/password_reset.html',
                                      user_name=user_name,
                                      reset_url=reset_url,
                                      token=token)

            return self.send_email(
                subject="Salasanan palautus - Levoro",
                recipients=[user_email],
                html_body=html_body
            )
        except Exception as e:
            error_msg = f"Failed to send password reset email: {str(e)}"
            current_app.logger.error(error_msg)
            print(f"   ❌ {error_msg}")
            return False

    def send_order_created_email(self, user_email: str, user_name: str, order_data: Dict) -> bool:
        """Send email when new order is created"""
        print(f"[ORDER] Creating order confirmation email")
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

            print(f"   [RENDER] Rendering order confirmation template...")
            html_body = render_template('emails/order_created.html',
                                      user_name=user_name,
                                      order=order_info)

            print(f"   [SEND] Sending order confirmation email...")
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

    def send_status_update_email(self, user_email: str, user_name: str, order_id: int,
                               new_status: str, driver_name: str = None) -> bool:
        """Send email when order status changes"""
        from utils.status_translations import translate_status, get_status_description

        status_finnish = translate_status(new_status)
        status_description = get_status_description(new_status)

        print(f"📊 ORDER STATUS UPDATE EMAIL:")
        print(f"   Recipient: {user_name} <{user_email}>")
        print(f"   Order ID: #{order_id}")
        print(f"   Status Change: {new_status} ({status_finnish})")
        print(f"   Description: {status_description}")
        if driver_name:
            print(f"   Driver: {driver_name}")

        try:
            # Get order data from database
            from models.order import order_model
            order_data = order_model.find_by_id(order_id)

            if not order_data:
                print(f"   ❌ Order {order_id} not found")
                return False

            order_info = {
                'order_id': order_id,
                'pickup_address': order_data.get('pickup_address', ''),
                'dropoff_address': order_data.get('dropoff_address', ''),
                'distance_km': order_data.get('distance_km', 0),
                'price_gross': order_data.get('price_gross', 0),
                'status': status_finnish,
                'status_description': status_description,
                'driver_name': driver_name
            }

            print(f"   📝 Rendering status update template...")
            html_body = render_template('emails/status_update.html',
                                      user_name=user_name,
                                      order=order_info,
                                      new_status=new_status,
                                      driver_name=driver_name)

            print(f"   [SEND] Sending status update email...")
            return self.send_email(
                subject=f"Tilaus #{order_id} - {status_finnish}",
                recipients=[user_email],
                html_body=html_body
            )
        except Exception as e:
            error_msg = f"Failed to send status update email: {str(e)}"
            current_app.logger.error(error_msg)
            print(f"   [ERROR] {error_msg}")
            return False

    def send_admin_new_order_notification(self, order_data: Dict, customer_data: Dict = None) -> bool:
        """Send notification to admin when new order is created"""
        admin_email = os.getenv("ADMIN_EMAIL", "support@levoro.fi")

        print(f"📧 ADMIN ORDER NOTIFICATION:")
        print(f"   To: {admin_email}")
        print(f"   Order ID: #{order_data.get('id')}")
        print(f"   Status: {order_data.get('status')}")
        print(f"   Customer: {customer_data.get('name') if customer_data else 'Unknown'}")

        try:
            # Create admin URLs using configured base URL
            base_url = os.getenv("BASE_URL", "http://localhost:3000")
            admin_url = f"{base_url}/admin"
            order_detail_url = f"{base_url}/admin/order/{order_data.get('id')}"

            html_body = render_template('emails/admin_new_order.html',
                                      order=order_data,
                                      customer=customer_data,
                                      admin_url=admin_url,
                                      order_detail_url=order_detail_url)

            return self.send_email(
                subject=f"[Levoro] Uusi tilaus #{order_data.get('id')} - Vahvistus tarvitaan",
                recipients=[admin_email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send admin order notification: {str(e)}")
            print(f"   [ERROR] Failed to send admin order notification: {str(e)}")
            return False

    def send_admin_new_user_notification(self, user_data: Dict, stats: Dict = None) -> bool:
        """Send notification to admin when new user registers"""
        admin_email = os.getenv("ADMIN_EMAIL", "support@levoro.fi")

        print(f"📧 ADMIN USER NOTIFICATION:")
        print(f"   To: {admin_email}")
        print(f"   User ID: #{user_data.get('id')}")
        print(f"   Name: {user_data.get('name')}")
        print(f"   Email: {user_data.get('email')}")
        print(f"   Role: {user_data.get('role', 'customer')}")

        try:
            # Create admin URLs using configured base URL
            base_url = os.getenv("BASE_URL", "http://localhost:3000")
            admin_users_url = f"{base_url}/admin/users"
            user_detail_url = f"{base_url}/admin/user/{user_data.get('id')}"

            # Default stats if not provided
            if not stats:
                stats = {
                    'total_users': 'N/A',
                    'customer_count': 'N/A',
                    'driver_count': 'N/A'
                }

            html_body = render_template('emails/admin_new_user.html',
                                      user=user_data,
                                      admin_users_url=admin_users_url,
                                      user_detail_url=user_detail_url,
                                      total_users=stats.get('total_users'),
                                      customer_count=stats.get('customer_count'),
                                      driver_count=stats.get('driver_count'))

            return self.send_email(
                subject=f"[Levoro] Uusi käyttäjä rekisteröitynyt: {user_data.get('name')}",
                recipients=[admin_email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send admin user notification: {str(e)}")
            print(f"   [ERROR] Failed to send admin user notification: {str(e)}")
            return False

    def send_driver_application_confirmation(self, email: str, name: str) -> bool:
        """Send confirmation email to driver applicant"""
        try:
            print(f"[EMAIL] Sending driver application confirmation to {email}")

            html_body = render_template('emails/driver_application_confirmation.html',
                                      name=name)

            return self.send_email(
                subject="Kuljettajahakemus vastaanotettu - Levoro",
                recipients=[email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send driver application confirmation: {str(e)}")
            print(f"   [ERROR] Failed to send driver application confirmation: {str(e)}")
            return False

    def send_admin_driver_application_notification(self, application: Dict) -> bool:
        """Send notification to admin about new driver application"""
        try:
            admin_email = os.getenv("ADMIN_EMAIL", "support@levoro.fi")
            print(f"[EMAIL] Sending driver application notification to admin: {admin_email}")

            applicant_name = application.get("name") or " ".join(
                filter(None, [application.get("first_name"), application.get("last_name")])
            ).strip()

            base_url = os.getenv('BASE_URL', 'http://localhost:3000')
            application_url = f"{base_url}/admin/driver-applications/{application['id']}"

            html_body = render_template('emails/admin_driver_application.html',
                                      application=application,
                                      applicant_name=applicant_name,
                                      application_url=application_url)

            return self.send_email(
                subject=f"[Levoro] Uusi kuljettajahakemus: {applicant_name}",
                recipients=[admin_email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send admin driver application notification: {str(e)}")
            print(f"   ❌ Failed to send admin driver application notification: {str(e)}")
            return False

    def send_driver_application_approved(self, email: str, name: str) -> bool:
        """Send approval email to driver"""
        try:
            print(f"[EMAIL] Sending driver application approval to {email}")

            html_body = render_template('emails/driver_application_approved.html',
                                      name=name,
                                      email=email)

            return self.send_email(
                subject="Kuljettajahakemus hyväksytty - Tervetuloa Levorolle!",
                recipients=[email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send driver application approval: {str(e)}")
            print(f"   [ERROR] Failed to send driver application approval: {str(e)}")
            return False

    def send_driver_assignment_email(self, driver_email: str, driver_name: str, order_data: Dict) -> bool:
        """Send email to driver when assigned to an order"""
        try:
            print(f"[EMAIL] Sending driver assignment notification to {driver_email}")

            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #3b82f6, #2563eb); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center;">
                    <h1 style="margin: 0; font-size: 28px;">Uusi tehtävä määritetty!</h1>
                    <p style="margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">Kuljetustehtävä</p>
                </div>

                <div style="padding: 0 20px;">
                    <p style="font-size: 16px; color: #374151;">Hei {driver_name},</p>

                    <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                        Sinut on määritetty uuteen kuljetustehtävään. Tässä tehtävän tiedot:
                    </p>

                    <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #1f2937; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px;">Tehtävän tiedot</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr><td style="padding: 8px 0; font-weight: bold; width: 40%;">Tilaus #:</td><td style="padding: 8px 0;">{order_data.get('id')}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Nouto:</td><td style="padding: 8px 0;">{order_data.get('pickup_address', 'N/A')}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Toimitus:</td><td style="padding: 8px 0;">{order_data.get('dropoff_address', 'N/A')}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Matka:</td><td style="padding: 8px 0;">{order_data.get('distance_km', 0)} km</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Rekisterinumero:</td><td style="padding: 8px 0;">{order_data.get('reg_number', 'N/A')}</td></tr>
                        </table>
                    </div>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{os.getenv('BASE_URL', 'http://localhost:3000')}/driver/job/{order_data.get('id')}"
                           style="background: #3b82f6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">
                            Näytä tehtävä
                        </a>
                    </div>

                    <p style="font-size: 16px; color: #374151;">
                        Ystävällisin terveisin,<br>
                        <strong>Levoro tiimi</strong>
                    </p>
                </div>

                <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                    <p style="font-size: 14px; color: #6b7280;">
                        Levoro - Luotettavaa autokuljetusta<br>
                        <a href="https://levoro.fi" style="color: #3b82f6;">levoro.fi</a>
                    </p>
                </div>
            </div>
            """

            return self.send_email(
                subject=f"Uusi tehtävä #{order_data.get('id')} - Levoro",
                recipients=[driver_email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send driver assignment email: {str(e)}")
            print(f"   [ERROR] Failed to send driver assignment email: {str(e)}")
            return False

    def send_customer_driver_assigned_email(self, customer_email: str, customer_name: str, order_data: Dict, driver_data: Dict) -> bool:
        """Send email to customer when driver is assigned to their order"""
        try:
            print(f"[EMAIL] Sending driver assigned notification to customer {customer_email}")

            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center;">
                    <h1 style="margin: 0; font-size: 28px;">&#x2713; Kuljettaja määritetty!</h1>
                </div>

                <div style="padding: 0 20px;">
                    <p style="font-size: 16px; color: #374151;">Hei {customer_name},</p>

                    <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                        Tilauksellesi #{order_data.get('id')} on määritetty kuljettaja. Kuljettaja ottaa sinuun yhteyttä pian.
                    </p>

                    <div style="background: #f0fdf4; border: 2px solid #10b981; padding: 20px; border-radius: 8px; margin: 25px 0;">
                        <h3 style="margin-top: 0; color: #047857; border-bottom: 2px solid #bbf7d0; padding-bottom: 8px;">Kuljettajan tiedot</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr><td style="padding: 8px 0; font-weight: bold; width: 30%;">Nimi:</td><td style="padding: 8px 0;">{driver_data.get('name', 'N/A')}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Puhelin:</td><td style="padding: 8px 0;">{driver_data.get('phone', 'N/A')}</td></tr>
                        </table>
                    </div>

                    <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #1f2937; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px;">Tilauksen tiedot</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr><td style="padding: 8px 0; font-weight: bold; width: 30%;">Tilaus #:</td><td style="padding: 8px 0;">{order_data.get('id')}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Nouto:</td><td style="padding: 8px 0;">{order_data.get('pickup_address', 'N/A')}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Toimitus:</td><td style="padding: 8px 0;">{order_data.get('dropoff_address', 'N/A')}</td></tr>
                        </table>
                    </div>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{os.getenv('BASE_URL', 'http://localhost:3000')}/order/{order_data.get('id')}"
                           style="background: #3b82f6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">
                            Seuraa tilausta
                        </a>
                    </div>

                    <p style="font-size: 16px; color: #374151;">
                        Ystävällisin terveisin,<br>
                        <strong>Levoro tiimi</strong>
                    </p>
                </div>

                <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                    <p style="font-size: 14px; color: #6b7280;">
                        Levoro - Luotettavaa autokuljetusta<br>
                        <a href="https://levoro.fi" style="color: #3b82f6;">levoro.fi</a>
                    </p>
                </div>
            </div>
            """

            return self.send_email(
                subject=f"Kuljettaja määritetty tilaukselle #{order_data.get('id')} - Levoro",
                recipients=[customer_email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send customer driver assigned email: {str(e)}")
            print(f"   [ERROR] Failed to send customer driver assigned email: {str(e)}")
            return False

    def send_driver_application_denied(self, email: str, name: str) -> bool:
        """Send denial email to driver applicant"""
        try:
            print(f"[EMAIL] Sending driver application denial to {email}")

            html_body = render_template('emails/driver_application_denied.html',
                                      name=name)

            return self.send_email(
                subject="Kuljettajahakemus - Levoro",
                recipients=[email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send driver application denial: {str(e)}")
            print(f"   [ERROR] Failed to send driver application denial: {str(e)}")
            return False

    def send_admin_driver_action_notification(self, order_id: int, driver_name: str, action: str, order_data: Dict) -> bool:
        """Send notification to admin when driver performs an action"""
        admin_email = os.getenv("ADMIN_EMAIL", "support@levoro.fi")

        print(f"[ADMIN] DRIVER ACTION NOTIFICATION:")
        print(f"   To: {admin_email}")
        print(f"   Order ID: #{order_id}")
        print(f"   Driver: {driver_name}")
        print(f"   Action: {action}")

        try:
            # Map action to Finnish description
            action_descriptions = {
                "DRIVER_ARRIVED": "Kuljettaja on saapunut noutopaikalle",
                "PICKUP_IMAGES_ADDED": "Kuljettaja on lisännyt noutokuvat",
                "IN_TRANSIT": "Kuljettaja on aloittanut kuljetuksen",
                "DELIVERY_ARRIVED": "Kuljettaja on saapunut toimituspaikalle",
                "DELIVERY_IMAGES_ADDED": "Kuljettaja on lisännyt toimituskuvat",
                "DELIVERED": "Kuljettaja on merkinnyt toimituksen valmiiksi"
            }

            action_finnish = action_descriptions.get(action, action)

            base_url = os.getenv("BASE_URL", "http://localhost:3000")
            order_detail_url = f"{base_url}/admin/order/{order_id}"

            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #f59e0b, #d97706); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center;">
                    <h1 style="margin: 0; font-size: 28px;">Kuljettajan toimenpide</h1>
                    <p style="margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">Tilaus #{order_id}</p>
                </div>

                <div style="padding: 0 20px;">
                    <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #92400e;">Toimenpide:</h3>
                        <p style="font-size: 18px; font-weight: bold; color: #92400e; margin: 5px 0;">{action_finnish}</p>
                        <p style="margin: 10px 0 0 0; color: #92400e;">Kuljettaja: <strong>{driver_name}</strong></p>
                    </div>

                    <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #1f2937; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px;">Tilauksen tiedot</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr><td style="padding: 8px 0; font-weight: bold; width: 40%;">Tilaus #:</td><td style="padding: 8px 0;">{order_id}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Nouto:</td><td style="padding: 8px 0;">{order_data.get('pickup_address', 'N/A')}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Toimitus:</td><td style="padding: 8px 0;">{order_data.get('dropoff_address', 'N/A')}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Matka:</td><td style="padding: 8px 0;">{order_data.get('distance_km', 0)} km</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Rekisterinumero:</td><td style="padding: 8px 0;">{order_data.get('reg_number', 'N/A')}</td></tr>
                        </table>
                    </div>

                    <div style="background: #dbeafe; border: 2px solid #3b82f6; padding: 20px; border-radius: 8px; margin: 25px 0;">
                        <p style="margin: 0; color: #1e40af; font-size: 14px;">
                            <strong>Huomio:</strong> Tämä on automaattinen ilmoitus kuljettajan toimenpiteestä.
                            Voit päivittää tilauksen tilan admin-paneelista tarpeen mukaan.
                        </p>
                    </div>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{order_detail_url}"
                           style="background: #3b82f6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">
                            Näytä tilaus admin-paneelissa
                        </a>
                    </div>

                    <p style="font-size: 16px; color: #374151;">
                        Ystävällisin terveisin,<br>
                        <strong>Levoro järjestelmä</strong>
                    </p>
                </div>

                <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                    <p style="font-size: 14px; color: #6b7280;">
                        Levoro - Luotettavaa autokuljetusta<br>
                        <a href="https://levoro.fi" style="color: #3b82f6;">levoro.fi</a>
                    </p>
                </div>
            </div>
            """

            return self.send_email(
                subject=f"[Levoro] Kuljettajan toimenpide tilaus #{order_id} - {action_finnish}",
                recipients=[admin_email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send admin driver action notification: {str(e)}")
            print(f"   [ERROR] Failed to send admin driver action notification: {str(e)}")
            return False

    def _save_email_to_file(self, subject: str, recipients: List[str], html_body: str, sender: str = None) -> bool:
        """Save email as HTML file for development testing"""
        try:
            from datetime import datetime
            import re
            
            # Create dev_emails directory if it doesn't exist
            emails_dir = os.path.join('static', 'dev_emails')
            os.makedirs(emails_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            # Sanitize subject for filename
            safe_subject = re.sub(r'[^a-zA-Z0-9_-]', '_', subject)[:50]
            filename = f"{timestamp}_{safe_subject}.html"
            filepath = os.path.join(emails_dir, filename)
            
            # Create email wrapper with metadata
            email_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{subject}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .email-metadata {{
            background: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .email-metadata h2 {{ margin-top: 0; color: #3498db; }}
        .email-metadata p {{ margin: 5px 0; }}
        .email-metadata strong {{ color: #ecf0f1; }}
        .email-content {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .timestamp {{ color: #95a5a6; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="email-metadata">
        <h2>📧 Development Email Mock</h2>
        <p><strong>From:</strong> {sender or 'support@levoro.fi'}</p>
        <p><strong>To:</strong> {', '.join(recipients)}</p>
        <p><strong>Subject:</strong> {subject}</p>
        <p class="timestamp"><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    <div class="email-content">
        {html_body}
    </div>
</body>
</html>
"""
            
            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(email_html)
            
            # Create index.html for easy browsing
            self._update_email_index(emails_dir)
            
            print(f"   ✅ [DEV] Email saved to: {filepath}")
            print(f"   🌐 [DEV] View at: http://localhost:8000/static/dev_emails/{filename}")
            print(f"   📋 [DEV] Email index: http://localhost:8000/static/dev_emails/index.html")
            return True
            
        except Exception as e:
            print(f"   ❌ [DEV] Failed to save email to file: {str(e)}")
            return False
    
    def _update_email_index(self, emails_dir: str):
        """Update index.html with list of all saved emails"""
        try:
            from datetime import datetime
            import glob
            
            # Get all email files
            email_files = sorted(
                glob.glob(os.path.join(emails_dir, '*.html')),
                key=os.path.getmtime,
                reverse=True
            )
            
            # Remove index.html from list
            email_files = [f for f in email_files if not f.endswith('index.html')]
            
            # Generate index HTML
            index_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Development Emails - Levoro</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            color: white;
            text-align: center;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .subtitle {{
            text-align: center;
            color: rgba(255,255,255,0.9);
            margin-bottom: 30px;
        }}
        .stats {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            padding: 15px;
            border-radius: 8px;
            color: white;
            text-align: center;
            margin-bottom: 20px;
        }}
        .email-list {{
            display: grid;
            gap: 15px;
        }}
        .email-card {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .email-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        }}
        .email-info {{
            flex: 1;
        }}
        .email-filename {{
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
            font-size: 1.1em;
        }}
        .email-time {{
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        .email-actions {{
            display: flex;
            gap: 10px;
        }}
        .btn {{
            padding: 10px 20px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            transition: all 0.2s;
            display: inline-block;
        }}
        .btn-primary {{
            background: #3498db;
            color: white;
        }}
        .btn-primary:hover {{
            background: #2980b9;
        }}
        .btn-danger {{
            background: #e74c3c;
            color: white;
        }}
        .btn-danger:hover {{
            background: #c0392b;
        }}
        .no-emails {{
            background: white;
            padding: 40px;
            border-radius: 12px;
            text-align: center;
            color: #7f8c8d;
        }}
        .clear-all {{
            text-align: center;
            margin-top: 20px;
        }}
        .icon {{ font-size: 1.2em; margin-right: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📧 Development Email Inbox</h1>
        <p class="subtitle">All emails are saved here instead of being sent in development mode</p>
        
        <div class="stats">
            <strong>Total Emails:</strong> {len(email_files)} | 
            <strong>Last Updated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        
        <div class="email-list">
"""
            
            if email_files:
                for email_file in email_files:
                    filename = os.path.basename(email_file)
                    file_time = datetime.fromtimestamp(os.path.getmtime(email_file))
                    time_str = file_time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Extract readable subject from filename
                    parts = filename.split('_', 3)
                    display_name = parts[3].replace('.html', '').replace('_', ' ') if len(parts) > 3 else filename
                    
                    index_html += f"""
            <div class="email-card">
                <div class="email-info">
                    <div class="email-filename"><span class="icon">📨</span>{display_name}</div>
                    <div class="email-time">🕐 {time_str}</div>
                </div>
                <div class="email-actions">
                    <a href="{filename}" class="btn btn-primary" target="_blank">View Email</a>
                </div>
            </div>
"""
            else:
                index_html += """
            <div class="no-emails">
                <div style="font-size: 4em; margin-bottom: 20px;">📭</div>
                <h2>No Emails Yet</h2>
                <p>Emails will appear here as they are generated in development mode.</p>
            </div>
"""
            
            index_html += f"""
        </div>
        
        {f'<div class="clear-all"><button class="btn btn-danger" onclick="if(confirm(\'Clear all emails?\')) {{ alert(\'Please delete files manually from static/dev_emails folder\'); }}">🗑️ Clear All Emails</button></div>' if email_files else ''}
    </div>
    <script>
        // Auto-refresh every 5 seconds
        setTimeout(() => location.reload(), 5000);
    </script>
</body>
</html>
"""
            
            # Write index file
            index_path = os.path.join(emails_dir, 'index.html')
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(index_html)
                
        except Exception as e:
            print(f"   ⚠️ [DEV] Failed to update email index: {str(e)}")

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