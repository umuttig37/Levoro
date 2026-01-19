# marketing.py
from flask import redirect, url_for, request
from services.auth_service import auth_service

# Import wrap function and app from app - will be available after app initialization
def get_wrap():
    from app import wrap
    return wrap

def get_app():
    from app import app
    return app

app = get_app()

@app.get("/terms")
def terms():
    """Legacy terms route - redirect to new customer terms"""
    from flask import redirect
    return redirect('/kayttoehdot', code=301)

@app.get("/kayttoehdot")
def customer_terms():
    """Customer terms of service page"""
    from flask import render_template
    return render_template('terms_customer.html')

@app.get("/kuljettajan-ehdot")
def driver_terms():
    """Driver terms of service page"""
    from flask import render_template
    return render_template('terms_driver.html')

@app.get("/yhteystiedot")
def contact():
    # Redirect to home page hash anchor since user requested no separate page
    return redirect(url_for('main.index', _anchor='contact'))

@app.post("/yhteystiedot")
def contact_submit():
    """Handle contact form submission - send email to admin"""
    from flask import request, flash
    from services.email_service import email_service
    import os
    
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    message = request.form.get('message', '').strip()
    
    # Validate required fields
    if not name or not email or not message:
        flash('Täytä kaikki kentät.', 'error')
        return redirect(url_for('main.index', _anchor='contact'))
    
    # Get admin email from environment or use default
    admin_email = os.getenv('ADMIN_EMAIL', 'support@levoro.fi')
    
    # Create email HTML
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1f2937; border-bottom: 2px solid #3b82f6; padding-bottom: 10px;">
            Uusi yhteydenotto Levoro-sivustolta
        </h2>
        
        <div style="background: #f3f4f6; border-radius: 8px; padding: 20px; margin: 20px 0;">
            <p style="margin: 0 0 10px 0;"><strong>Lähettäjä:</strong> {name}</p>
            <p style="margin: 0 0 10px 0;"><strong>Sähköposti:</strong> <a href="mailto:{email}">{email}</a></p>
        </div>
        
        <div style="margin: 20px 0;">
            <h3 style="color: #374151; margin-bottom: 10px;">Viesti:</h3>
            <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 15px; white-space: pre-wrap;">
{message}
            </div>
        </div>
        
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
        
        <p style="color: #6b7280; font-size: 0.875rem;">
            Voit vastata suoraan tähän sähköpostiin.
        </p>
    </div>
    """
    
    try:
        # Send email to admin with reply-to set to the visitor's email
        success = email_service.send_email(
            subject=f"Yhteydenotto: {name}",
            recipients=[admin_email],
            html_body=html_body,
            sender=f"Levoro Yhteydenotto <noreply@levoro.fi>"
        )
        
        if success:
            flash('Viestisi on lähetetty! Vastaamme mahdollisimman pian.', 'success')
        else:
            flash('Viestin lähetys epäonnistui. Yritä myöhemmin uudelleen.', 'error')
    except Exception as e:
        print(f"Contact form error: {e}")
        flash('Viestin lähetys epäonnistui. Yritä myöhemmin uudelleen.', 'error')
    
    return redirect(url_for('main.index', _anchor='contact'))


@app.get("/calculator")
def calculator():
    u = auth_service.get_current_user()
    if not u:
        # Preserve query params (pickup, destination) when redirecting to login
        next_url = "/calculator"
        if request.query_string:
            next_url = f"/calculator?{request.query_string.decode('utf-8')}"
        return redirect(url_for("auth.login", next=next_url))

    # Drivers cannot access calculator - redirect to their dashboard
    if u.get('role') == 'driver':
        return redirect(url_for("driver.dashboard"))


    # Render the new template
    from flask import render_template
    import os
    
    # Get saved addresses properly if available (placeholder for now)
    saved_addresses = u.get('saved_addresses', [])
    
    return render_template(
        'calculator_new.html', 
        current_user=u,
        saved_addresses=saved_addresses,
        google_places_api_key=os.environ.get("GOOGLE_PLACES_API_KEY", "")
    )
