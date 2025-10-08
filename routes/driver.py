"""
Driver Routes
Handles driver-specific routes and functionality
"""

from flask import Blueprint, request, redirect, url_for, flash, jsonify, render_template, abort
from services.driver_service import driver_service
from services.auth_service import auth_service
from services.image_service import image_service
from utils.helpers import login_required
from utils.formatters import format_helsinki_time

driver_bp = Blueprint('driver', __name__, url_prefix='/driver')


def driver_required(f):
    """Decorator to require driver authentication"""
    def decorated_function(*args, **kwargs):
        user = auth_service.get_current_user()
        if not user or user.get('role') != 'driver':
            flash('Kirjaudu sisään kuljettajana', 'error')
            return redirect(url_for('auth.login'))

        # Check if driver has accepted terms (except for terms page itself)
        if f.__name__ != 'terms' and not user.get('terms_accepted', False):
            flash('Sinun tulee hyväksyä kuljettajan säännöt ensin', 'warning')
            return redirect(url_for('driver.terms'))

        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


@driver_bp.route('/dashboard')
@driver_required
def dashboard():
    """Driver main dashboard"""
    driver = auth_service.get_current_user()  # Use the same user that was validated

    # Get driver statistics
    stats = driver_service.get_driver_statistics(driver['id'])

    # Get active jobs
    active_jobs = driver_service.get_active_driver_jobs(driver['id'])

    # Get available jobs
    available_jobs = driver_service.get_available_jobs(limit=50)

    # Get all driver's jobs
    all_jobs = driver_service.get_driver_jobs(driver['id'])

    return render_template('driver/dashboard.html',
                         driver=driver,
                         stats=stats,
                         active_jobs=active_jobs,
                         available_jobs=available_jobs,
                         all_jobs=all_jobs,
                         current_user=driver)


@driver_bp.route('/jobs')
@driver_required
def jobs():
    """List available jobs"""
    available_jobs = driver_service.get_available_jobs()
    driver = auth_service.get_current_user()
    return render_template('driver/jobs_list.html', available_jobs=available_jobs, current_user=driver)


@driver_bp.route('/job/<int:order_id>')
@driver_required
def job_detail(order_id):
    """Job detail page"""
    driver = auth_service.get_current_user()

    # Check if this job belongs to the driver or is available
    from models.order import order_model
    order = order_model.find_by_id(order_id, projection=order_model.DRIVER_PROJECTION)

    if not order:
        flash('Tilaus ei löytynyt', 'error')
        return redirect(url_for('driver.dashboard'))

    # Auto-fix status if images exist but status not updated (race condition recovery)
    images = order.get('images', {})
    pickup_images = images.get('pickup', [])
    delivery_images = images.get('delivery', [])
    current_status = order.get('status')

    # Fix pickup status if images exist but status is still DRIVER_ARRIVED
    if len(pickup_images) > 0 and current_status == order_model.STATUS_DRIVER_ARRIVED:
        driver_service.update_pickup_images_status(order_id, driver['id'])
        order = order_model.find_by_id(order_id, projection=order_model.DRIVER_PROJECTION)  # Refresh order
        current_status = order.get('status')

    # Fix delivery status if images exist but status is still DELIVERY_ARRIVED
    if len(delivery_images) > 0 and current_status == order_model.STATUS_DELIVERY_ARRIVED:
        driver_service.update_delivery_images_status(order_id, driver['id'])
        order = order_model.find_by_id(order_id, projection=order_model.DRIVER_PROJECTION)  # Refresh order

    # Check if driver can access this job
    driver_id = order.get('driver_id')
    status = order.get('status')

    # Allow access if:
    # 1. Job is available for assignment (CONFIRMED status with no driver assigned)
    # 2. Job is assigned to current driver
    if driver_id and driver_id != driver['id']:
        flash('Tämä tilaus on määritetty toiselle kuljettajalle', 'error')
        return redirect(url_for('driver.dashboard'))
    elif not driver_id and status != 'CONFIRMED':
        flash('Tämä tilaus ei ole saatavilla', 'error')
        return redirect(url_for('driver.dashboard'))

    return render_template('driver/job_detail.html', order=order, driver=driver, current_user=driver)


@driver_bp.route('/job/<int:order_id>/accept', methods=['POST'])
@driver_required
def accept_job(order_id):
    """Accept a job assignment"""
    driver = auth_service.get_current_user()

    success, error = driver_service.accept_job(order_id, driver['id'])

    if success:
        flash('Tilaus otettu onnistuneesti!', 'success')
        return redirect(url_for('driver.job_detail', order_id=order_id))
    else:
        flash(f'Virhe: {error}', 'error')
        return redirect(url_for('driver.jobs'))


@driver_bp.route('/job/<int:order_id>/arrive', methods=['POST'])
@driver_required
def mark_arrival(order_id):
    """Mark arrival at pickup location"""
    driver = auth_service.get_current_user()

    success, error = driver_service.mark_arrival(order_id, driver['id'])

    if success:
        flash('Saapuminen merkitty!', 'success')
    else:
        flash(f'Virhe: {error}', 'error')

    return redirect(url_for('driver.job_detail', order_id=order_id))


@driver_bp.route('/job/<int:order_id>/start', methods=['POST'])
@driver_required
def start_transport(order_id):
    """Start transport after pickup images"""
    driver = auth_service.get_current_user()

    success, error = driver_service.start_transport(order_id, driver['id'])

    if success:
        flash('Kuljetus aloitettu!', 'success')
    else:
        flash(f'Virhe: {error}', 'error')

    return redirect(url_for('driver.job_detail', order_id=order_id))


@driver_bp.route('/job/<int:order_id>/arrive_delivery', methods=['POST'])
@driver_required
def arrive_delivery(order_id):
    """Mark arrival at delivery location"""
    driver = auth_service.get_current_user()

    success, error = driver_service.arrive_at_delivery(order_id, driver['id'])

    if success:
        flash('Saapuminen toimitusosoitteeseen merkitty!', 'success')
    else:
        flash(f'Virhe: {error}', 'error')

    return redirect(url_for('driver.job_detail', order_id=order_id))


@driver_bp.route('/job/<int:order_id>/complete', methods=['POST'])
@driver_required
def complete_delivery(order_id):
    """Complete delivery after delivery images"""
    driver = auth_service.get_current_user()

    success, error = driver_service.complete_delivery(order_id, driver['id'])

    if success:
        flash('Toimitus suoritettu onnistuneesti!', 'success')
    else:
        flash(f'Virhe: {error}', 'error')

    return redirect(url_for('driver.job_detail', order_id=order_id))


@driver_bp.route('/job/<int:order_id>/upload', methods=['POST'])
@driver_required
def upload_image(order_id):
    """Upload image for pickup or delivery"""
    driver = auth_service.get_current_user()
    image_type = request.form.get('image_type')

    if image_type not in ['pickup', 'delivery']:
        flash('Virheellinen kuvatyyppi', 'error')
        return redirect(url_for('driver.job_detail', order_id=order_id))

    # Verify driver can add images for this stage
    if image_type == 'pickup' and not driver_service.can_add_pickup_images(order_id, driver['id']):
        flash('Et voi lisätä noutokuvia tässä vaiheessa', 'error')
        return redirect(url_for('driver.job_detail', order_id=order_id))

    if image_type == 'delivery' and not driver_service.can_add_delivery_images(order_id, driver['id']):
        flash('Et voi lisätä toimituskuvia tässä vaiheessa', 'error')
        return redirect(url_for('driver.job_detail', order_id=order_id))

    if 'image' not in request.files:
        flash('Kuvaa ei valittu', 'error')
        return redirect(url_for('driver.job_detail', order_id=order_id))

    file = request.files['image']
    if file.filename == '':
        flash('Kuvaa ei valittu', 'error')
        return redirect(url_for('driver.job_detail', order_id=order_id))

    # Save and process image using ImageService
    image_info, error = image_service.save_order_image(file, order_id, image_type, driver.get('email', 'driver'))

    if error:
        flash(error, 'error')
        return redirect(url_for('driver.job_detail', order_id=order_id))

    # Add image to order using ImageService (atomic MongoDB $push operation)
    success, add_error = image_service.add_image_to_order(order_id, image_type, image_info)

    if not success:
        flash(add_error, 'error')
        return redirect(url_for('driver.job_detail', order_id=order_id))

    # Get updated image count AFTER adding (check if this was the first image)
    # This prevents race conditions - only the upload that results in count=1 will trigger status update
    from models.order import order_model
    order_after = order_model.find_by_id(order_id, projection=order_model.DRIVER_PROJECTION)
    current_images = order_after.get('images', {}).get(image_type, [])
    
    # Handle migration from old single image format
    if not isinstance(current_images, list):
        current_images = [current_images] if current_images else []
    
    # Only trigger status update if this resulted in exactly 1 image (was the first)
    should_trigger_status_update = len(current_images) == 1

    # Update order status ONLY if this was the first image (status transition)
    if should_trigger_status_update:
        if image_type == 'pickup':
            driver_service.update_pickup_images_status(order_id, driver['id'])
            flash('Noutokuva lisätty! Odottaa admin hyväksyntää.', 'success')
        elif image_type == 'delivery':
            driver_service.update_delivery_images_status(order_id, driver['id'])
            flash('Toimituskuva lisätty! Odottaa admin hyväksyntää.', 'success')
    else:
        image_type_fi = 'Nouto' if image_type == 'pickup' else 'Toimitus'
        flash(f'{image_type_fi}kuva lisätty onnistuneesti', 'success')

    return redirect(url_for('driver.job_detail', order_id=order_id))


@driver_bp.route('/api/job/<int:order_id>/upload', methods=['POST'])
@driver_required
def upload_image_ajax(order_id):
    """AJAX endpoint for uploading images (supports multiple uploads without page reload)"""
    driver = auth_service.get_current_user()
    image_type = request.form.get('image_type')

    # Validation
    if image_type not in ['pickup', 'delivery']:
        return jsonify({'success': False, 'error': 'Virheellinen kuvatyyppi'}), 400

    # Verify driver can add images for this stage
    if image_type == 'pickup' and not driver_service.can_add_pickup_images(order_id, driver['id']):
        return jsonify({'success': False, 'error': 'Et voi lisätä noutokuvia tässä vaiheessa'}), 403

    if image_type == 'delivery' and not driver_service.can_add_delivery_images(order_id, driver['id']):
        return jsonify({'success': False, 'error': 'Et voi lisätä toimituskuvia tässä vaiheessa'}), 403

    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'Kuvaa ei valittu'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Kuvaa ei valittu'}), 400

    # Check image limit
    can_add, limit_error = image_service.validate_image_limit(order_id, image_type, max_images=15)
    if not can_add:
        return jsonify({'success': False, 'error': limit_error}), 400

    # Save and process image using ImageService
    image_info, error = image_service.save_order_image(file, order_id, image_type, driver.get('email', 'driver'))

    if error:
        return jsonify({'success': False, 'error': error}), 400

    # Add image to order using ImageService (atomic MongoDB $push operation)
    success, add_error = image_service.add_image_to_order(order_id, image_type, image_info)

    if not success:
        return jsonify({'success': False, 'error': add_error}), 500

    # Get updated order and check if status update should be triggered
    # The key is: trigger ONLY if status is still at "arrived" state (transition point)
    from models.order import order_model
    order_after = order_model.find_by_id(order_id, projection=order_model.DRIVER_PROJECTION)
    current_status = order_after.get('status')
    current_images = order_after.get('images', {}).get(image_type, [])
    
    # Handle migration from old single image format
    if not isinstance(current_images, list):
        current_images = [current_images] if current_images else []
    
    # Trigger status update based on current status, not image count
    # This handles all scenarios: normal flow, simultaneous uploads, and manual resets
    # If status is at "arrived" state, this upload should trigger the transition
    should_trigger_status_update = False
    if image_type == 'pickup' and current_status == order_model.STATUS_DRIVER_ARRIVED:
        should_trigger_status_update = True
    elif image_type == 'delivery' and current_status == order_model.STATUS_DELIVERY_ARRIVED:
        should_trigger_status_update = True

    status_updated = False
    message = ''

    # Update status ONLY if order is at the transition point
    if should_trigger_status_update:
        if image_type == 'pickup':
            driver_service.update_pickup_images_status(order_id, driver['id'])
            message = 'Noutokuva lisätty! Odottaa admin hyväksyntää.'
            status_updated = True
        elif image_type == 'delivery':
            driver_service.update_delivery_images_status(order_id, driver['id'])
            message = 'Toimituskuva lisätty! Odottaa admin hyväksyntää.'
            status_updated = True
    else:
        image_type_fi = 'Nouto' if image_type == 'pickup' else 'Toimitus'
        message = f'{image_type_fi}kuva lisätty onnistuneesti'

    return jsonify({
        'success': True,
        'message': message,
        'image': image_info,
        'image_count': len(current_images),
        'status_updated': status_updated
    })


@driver_bp.route('/api/job/<int:order_id>/image/<string:image_type>/<string:image_id>', methods=['DELETE'])
@driver_required
def delete_image_ajax(order_id, image_type, image_id):
    """AJAX endpoint for deleting images"""
    driver = auth_service.get_current_user()

    # Verify driver owns this job
    from models.order import order_model
    order = order_model.find_by_id(order_id, projection=order_model.DRIVER_PROJECTION)
    if not order or order.get('driver_id') != driver['id']:
        return jsonify({'success': False, 'error': 'Ei oikeuksia'}), 403

    # Delete image
    success, error = image_service.delete_order_image(order_id, image_type, image_id)

    if not success:
        return jsonify({'success': False, 'error': error}), 400

    # Get updated image count
    order = order_model.find_by_id(order_id, projection=order_model.DRIVER_PROJECTION)
    current_images = order.get('images', {}).get(image_type, [])

    return jsonify({
        'success': True,
        'message': 'Kuva poistettu',
        'image_count': len(current_images)
    })


@driver_bp.route('/my-jobs')
@driver_required
def my_jobs():
    """List all driver's jobs"""
    driver = auth_service.get_current_user()
    all_jobs = driver_service.get_driver_jobs(driver['id'])

    return render_template('driver/my_jobs.html', jobs=all_jobs, driver=driver, current_user=driver)


@driver_bp.route('/profile')
@driver_required
def profile():
    """Driver profile page"""
    driver = auth_service.get_current_user()
    stats = driver_service.get_driver_statistics(driver['id'])

    return render_template('driver/profile.html', driver=driver, stats=stats, current_user=driver)


# API endpoints for AJAX calls
@driver_bp.route('/api/job/<int:order_id>/status')
@driver_required
def get_job_status(order_id):
    """Get current job status"""
    from models.order import order_model
    order = order_model.find_by_id(order_id, projection=order_model.DRIVER_PROJECTION)

    if not order:
        return jsonify({'error': 'Tilaus ei löytynyt'}), 404

    driver = auth_service.get_current_user()
    if order.get('driver_id') != driver['id']:
        return jsonify({'error': 'Ei oikeuksia'}), 403

    return jsonify({
        'status': order.get('status'),
        'updated_at': format_helsinki_time(order.get('updated_at'))
    })


@driver_bp.route('/terms', methods=['GET', 'POST'])
def terms():
    """Driver terms and conditions page"""
    # Check if user is logged in
    user = auth_service.get_current_user()
    if not user or user.get('role') != 'driver':
        flash('Kirjaudu sisään kuljettajana', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'GET':
        # Load terms content from markdown file
        import os
        import markdown

        terms_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'content', 'driver_terms_fi.md')

        try:
            with open(terms_file, 'r', encoding='utf-8') as f:
                terms_markdown = f.read()
                terms_html = markdown.markdown(terms_markdown)
        except Exception as e:
            print(f"Error loading terms: {e}")
            terms_html = "<p>Virhe ladattaessa sääntöjä. Ota yhteyttä tukeen.</p>"

        return render_template('driver/terms.html', terms_content=terms_html, current_user=user)

    # POST - Accept terms
    if request.form.get('accept_terms'):
        from models.user import user_model
        success = user_model.accept_terms(user['id'])

        if success:
            flash('Kiitos! Olet hyväksynyt kuljettajan säännöt.', 'success')
            return redirect(url_for('driver.dashboard'))
        else:
            flash('Virhe hyväksynnässä. Yritä uudelleen.', 'error')
            return redirect(url_for('driver.terms'))

    flash('Sinun tulee hyväksyä säännöt jatkaaksesi', 'error')
    return redirect(url_for('driver.terms'))