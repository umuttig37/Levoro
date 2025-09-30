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
    order = order_model.find_by_id(order_id)

    if not order:
        flash('Tilaus ei löytynyt', 'error')
        return redirect(url_for('driver.dashboard'))

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

    # Add image to order using ImageService
    success, add_error = image_service.add_image_to_order(order_id, image_type, image_info)

    if not success:
        flash(add_error, 'error')
        return redirect(url_for('driver.job_detail', order_id=order_id))

    # Update order status after first image of each type
    from models.order import order_model
    order = order_model.find_by_id(order_id)
    current_images = order.get('images', {}).get(image_type, [])
    current_status = order.get('status')

    # If this is the first image and status hasn't been updated yet, update status
    if len(current_images) == 1:
        if image_type == 'pickup' and current_status == order_model.STATUS_DRIVER_ARRIVED:
            driver_service.update_pickup_images_status(order_id, driver['id'])
            flash('Noutokuva lisätty! Voit nyt aloittaa kuljetuksen.', 'success')
        elif image_type == 'delivery' and current_status == order_model.STATUS_DELIVERY_ARRIVED:
            driver_service.update_delivery_images_status(order_id, driver['id'])
            flash('Toimituskuva lisätty! Voit nyt päättää toimituksen.', 'success')
        else:
            image_type_fi = 'Nouto' if image_type == 'pickup' else 'Toimitus'
            flash(f'{image_type_fi}kuva lisätty onnistuneesti', 'success')
    else:
        image_type_fi = 'Nouto' if image_type == 'pickup' else 'Toimitus'
        flash(f'{image_type_fi}kuva lisätty onnistuneesti', 'success')

    return redirect(url_for('driver.job_detail', order_id=order_id))


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
    order = order_model.find_by_id(order_id)

    if not order:
        return jsonify({'error': 'Tilaus ei löytynyt'}), 404

    driver = auth_service.get_current_user()
    if order.get('driver_id') != driver['id']:
        return jsonify({'error': 'Ei oikeuksia'}), 403

    return jsonify({
        'status': order.get('status'),
        'updated_at': format_helsinki_time(order.get('updated_at'))
    })