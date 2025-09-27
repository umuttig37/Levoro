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

    def send_status_update_email(self, user_email: str, user_name: str, order_id: int,
                               new_status: str, driver_name: str = None) -> bool:
        """Send email when order status changes"""
        # Status translations for email subject
        status_translations = {
            'NEW': 'Uusi tilaus',
            'CONFIRMED': 'Tehtävä vahvistettu',
            'ASSIGNED_TO_DRIVER': 'Kuljettaja määritetty',
            'DRIVER_ARRIVED': 'Kuljettaja saapunut',
            'PICKUP_IMAGES_ADDED': 'Noutokuvat lisätty',
            'IN_TRANSIT': 'Kuljetus aloitettu',
            'DELIVERY_ARRIVED': 'Kuljetus saapunut',
            'DELIVERY_IMAGES_ADDED': 'Toimituskuvat lisätty',
            'DELIVERED': 'Toimitettu',
            'CANCELLED': 'Peruutettu'
        }

        status_descriptions = {
            'NEW': 'Tilaus vastaanotettu ja odottaa vahvistusta',
            'CONFIRMED': 'Tilaus vahvistettu! Kuljettaja määritetään pian',
            'ASSIGNED_TO_DRIVER': 'Kuljettaja määritetty ja matkalla noutopaikalle',
            'DRIVER_ARRIVED': 'Kuljettaja saapunut noutopaikalle ja aloittaa ajoneuvon tarkastuksen',
            'PICKUP_IMAGES_ADDED': 'Ajoneuvon tila dokumentoitu - kuljetus alkaa pian',
            'IN_TRANSIT': 'Ajoneuvonne on nyt matkalla määränpäähän',
            'DELIVERY_ARRIVED': 'Ajoneuvonne on saapunut toimituspaikalle',
            'DELIVERY_IMAGES_ADDED': 'Toimitus dokumentoitu - ajoneuvonne on valmis luovutettavaksi',
            'DELIVERED': 'Kuljetus suoritettu onnistuneesti! Kiitos Levoro-palvelun käytöstä',
            'CANCELLED': 'Tilaus on peruutettu'
        }

        status_finnish = status_translations.get(new_status, new_status)
        status_description = status_descriptions.get(new_status, new_status)

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

            print(f"   📧 Sending status update email...")
            return self.send_email(
                subject=f"Tilaus #{order_id} - {status_finnish}",
                recipients=[user_email],
                html_body=html_body
            )
        except Exception as e:
            error_msg = f"Failed to send status update email: {str(e)}"
            current_app.logger.error(error_msg)
            print(f"   ❌ {error_msg}")
            return False

    def send_admin_new_order_notification(self, order_data: Dict, customer_data: Dict = None) -> bool:
        """Send notification to admin when new order is created"""
        admin_email = "support@levoro.fi"

        print(f"📧 ADMIN ORDER NOTIFICATION:")
        print(f"   To: {admin_email}")
        print(f"   Order ID: #{order_data.get('id')}")
        print(f"   Status: {order_data.get('status')}")
        print(f"   Customer: {customer_data.get('name') if customer_data else 'Unknown'}")

        try:
            # Create admin URLs (assuming local development)
            base_url = "http://localhost:8000"  # Should be configurable in production
            admin_url = f"{base_url}/admin"
            order_detail_url = f"{base_url}/admin/order/{order_data.get('id')}"

            html_body = render_template('emails/admin_new_order.html',
                                      order=order_data,
                                      customer=customer_data,
                                      admin_url=admin_url,
                                      order_detail_url=order_detail_url)

            return self.send_email(
                subject=f"🆕 Uusi tilaus #{order_data.get('id')} - Vahvistus tarvitaan",
                recipients=[admin_email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send admin order notification: {str(e)}")
            print(f"   ❌ Failed to send admin order notification: {str(e)}")
            return False

    def send_admin_new_user_notification(self, user_data: Dict, stats: Dict = None) -> bool:
        """Send notification to admin when new user registers"""
        admin_email = "support@levoro.fi"

        print(f"📧 ADMIN USER NOTIFICATION:")
        print(f"   To: {admin_email}")
        print(f"   User ID: #{user_data.get('id')}")
        print(f"   Name: {user_data.get('name')}")
        print(f"   Email: {user_data.get('email')}")
        print(f"   Role: {user_data.get('role', 'customer')}")

        try:
            # Create admin URLs (assuming local development)
            base_url = "http://localhost:8000"  # Should be configurable in production
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
                subject=f"👤 Uusi käyttäjä rekisteröitynyt: {user_data.get('name')}",
                recipients=[admin_email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send admin user notification: {str(e)}")
            print(f"   ❌ Failed to send admin user notification: {str(e)}")
            return False

    def send_driver_application_confirmation(self, email: str, name: str) -> bool:
        """Send confirmation email to driver applicant"""
        try:
            print(f"📧 Sending driver application confirmation to {email}")

            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #3b82f6, #2563eb); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center;">
                    <h1 style="margin: 0; font-size: 28px;">🚗 Kiitos hakemuksestasi!</h1>
                </div>

                <div style="padding: 0 20px;">
                    <p style="font-size: 16px; color: #374151;">Hei {name},</p>

                    <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                        Kiitos kuljettajahakemuksestasi Levorolle! Olemme vastaanottaneet hakemuksesi ja käsittelemme sen mahdollisimman pian.
                    </p>

                    <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #1f2937;">📋 Seuraavat vaiheet:</h3>
                        <ul style="color: #374151; line-height: 1.6;">
                            <li>Käymme hakemuksesi läpi huolellisesti</li>
                            <li>Otamme sinuun yhteyttä 1-3 arkipäivän sisällä</li>
                            <li>Jos hakemus hyväksytään, lähetämme kirjautumistiedot</li>
                        </ul>
                    </div>

                    <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                        Jos sinulla on kysyttävää, vastaa tähän sähköpostiin tai ota yhteyttä asiakaspalveluumme.
                    </p>

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
                subject="🚗 Kuljettajahakemus vastaanotettu - Levoro",
                recipients=[email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send driver application confirmation: {str(e)}")
            print(f"   ❌ Failed to send driver application confirmation: {str(e)}")
            return False

    def send_admin_driver_application_notification(self, application: Dict) -> bool:
        """Send notification to admin about new driver application"""
        try:
            admin_email = os.getenv("ADMIN_EMAIL", "admin@levoro.fi")
            print(f"📧 Sending driver application notification to admin: {admin_email}")

            applicant_name = application.get("name") or " ".join(
                filter(None, [application.get("first_name"), application.get("last_name")])
            ).strip()

            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
                <div style="background: #dc2626; color: white; padding: 25px; border-radius: 12px; margin-bottom: 30px; text-align: center;">
                    <h1 style="margin: 0; font-size: 24px;">🚗 Uusi kuljettajahakemus</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Hakemus #{application['id']} odottaa käsittelyä</p>
                </div>

                <div style="padding: 0 20px;">
                    <!-- Personal Information -->
                    <div style="background: #f9fafb; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                        <h3 style="margin-top: 0; color: #1f2937;">👤 Hakijan tiedot</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr><td style="padding: 8px 0; font-weight: bold; width: 30%;">Nimi:</td><td style="padding: 8px 0;">{applicant_name}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Sähköposti:</td><td style="padding: 8px 0;">{application['email']}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Puhelin:</td><td style="padding: 8px 0;">{application['phone']}</td></tr>
                            <tr><td style="padding: 8px 0; font-weight: bold;">Salasana:</td><td style="padding: 8px 0;">Asetettu (käyttäjä loi oman)</td></tr>
                        </table>
                    </div>

                    <div style="background: #f0fdf4; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                        <h3 style="margin-top: 0; color: #1f2937;">ℹ️ Huomio</h3>
                        <p style="margin: 0; color: #065f46;">
                            Hakija on luonut oman salasanan rekisteröityessään. Hyväksymisen yhteydessä käyttäjätili luodaan automaattisesti.
                        </p>
                    </div>

                    <div style="text-align: center; margin-top: 30px;">
                        <a href="http://levoro.fi/admin/driver-applications/{application['id']}"
                           style="background: #3b82f6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">
                            Käsittele hakemus
                        </a>
                    </div>
                </div>
            </div>
            """

            return self.send_email(
                subject=f"🚗 Uusi kuljettajahakemus: {applicant_name}",
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
            print(f"📧 Sending driver application approval to {email}")

            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center;">
                    <h1 style="margin: 0; font-size: 28px;">🎉 Hakemus hyväksytty!</h1>
                    <p style="margin: 10px 0 0 0; font-size: 18px; opacity: 0.9;">Tervetuloa Levoro-tiimiin</p>
                </div>

                <div style="padding: 0 20px;">
                    <p style="font-size: 16px; color: #374151;">Hei {name},</p>

                    <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                        Onneksi olkoon! Kuljettajahakemuksesi on hyväksytty ja kuljettajatilisi on aktivoitu Levoro-järjestelmään.
                    </p>

                    <div style="background: #f0fdf4; border: 2px solid #10b981; padding: 20px; border-radius: 8px; margin: 25px 0;">
                        <h3 style="margin-top: 0; color: #047857;">🔑 Kirjautuminen</h3>
                        <p style="margin: 10px 0; font-size: 14px; color: #065f46;">
                            Voit nyt kirjautua sisään käyttämällä sähköpostiosoitettasi <strong>{email}</strong> ja rekisteröityessäsi luomaasi salasanaa.
                        </p>
                    </div>

                    <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #1f2937;">📋 Seuraavat vaiheet:</h3>
                        <ol style="color: #374151; line-height: 1.6; margin: 0; padding-left: 20px;">
                            <li>Kirjaudu sisään osoitteessa <a href="https://levoro.fi" style="color: #3b82f6;">levoro.fi</a></li>
                            <li>Tutustu kuljettajan työkaluihin</li>
                            <li>Aloita tehtävien vastaanottaminen</li>
                        </ol>
                    </div>

                    <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                        Olemme innoissamme saadessemme sinut mukaan tiimiimme! Jos sinulla on kysyttävää, ota rohkeasti yhteyttä.
                    </p>

                    <p style="font-size: 16px; color: #374151;">
                        Tervetuloa mukaan!<br>
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
                subject="🎉 Kuljettajahakemus hyväksytty - Tervetuloa Levorolle!",
                recipients=[email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send driver application approval: {str(e)}")
            print(f"   ❌ Failed to send driver application approval: {str(e)}")
            return False

    def send_driver_application_denied(self, email: str, name: str) -> bool:
        """Send denial email to driver applicant"""
        try:
            print(f"📧 Sending driver application denial to {email}")

            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: #ef4444; color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center;">
                    <h1 style="margin: 0; font-size: 28px;">Kiitos hakemuksestasi</h1>
                </div>

                <div style="padding: 0 20px;">
                    <p style="font-size: 16px; color: #374151;">Hei {name},</p>

                    <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                        Kiitos mielenkiinnostasi Levoro kuljettajatehtäviä kohtaan. Valitettavasti emme voi tällä hetkellä hyväksyä hakemustasi.
                    </p>

                    <div style="background: #fef2f2; border: 1px solid #fca5a5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0; color: #7f1d1d; line-height: 1.6;">
                            Hakemusten arviointi on tiukkaa ja tilanne voi muuttua tulevaisuudessa.
                            Kannustamme sinua hakemaan uudelleen myöhemmin.
                        </p>
                    </div>

                    <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                        Kiitos ymmärryksestäsi ja toivomme sinulle menestystä tulevaisuudessa.
                    </p>

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
                subject="Kuljettajahakemus - Levoro",
                recipients=[email],
                html_body=html_body
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send driver application denial: {str(e)}")
            print(f"   ❌ Failed to send driver application denial: {str(e)}")
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