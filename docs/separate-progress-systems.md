     # Separate Progress Systems - Implementation Complete ✅

     **Status**: ✅ IMPLEMENTED (All 11 phases complete)
     **Date**: 2025-01-12
     **Ready for**: Migration + Testing

     ## Core Principle

     Two completely independent systems:
     1. **Driver Progress** - Driver completes workflow independently, never waits for admin
     2. **Customer Order Status** - Admin manually updates based on notifications, triggers customer emails

     Driver actions ONLY update `driver_progress` field and notify admin. Order status is IRRELEVANT to driver workflow.

     ## Implementation Status

     ✅ **Phase 1**: Database schema + OrderModel helper methods
     ✅ **Phase 2**: DriverService complete rewrite (6 new methods)
     ✅ **Phase 3**: ImageService minimum validation (5 images)
     ✅ **Phase 4**: Driver routes updated (6 new endpoints)
     ✅ **Phase 5**: Driver UI template rewrite (progress-based)
     ✅ **Phase 6**: Email notifications (6 admin notifications)
     ✅ **Phase 7**: Admin panel timeline display
     ✅ **Phase 8**: Status translations updated
     ✅ **Phase 9**: Migration script created
     ✅ **Phase 10**: Dev email mock system verified
     ✅ **Phase 11**: Documentation complete

     ## Quick Start

     ```bash
     # 1. Run migration
     python migrations/add_driver_progress.py

     # 2. Test in development
     # Set FLASK_ENV=development in .env
     python app.py

     # 3. View dev emails
     # Open: http://localhost:8000/static/dev_emails/index.html
     ```

     ---
     Phase 1: Database Schema & Model Updates

     1.1 Add driver_progress Field to Orders

     File: models/order.py

     driver_progress: {
         arrived_at_pickup: { timestamp: DateTime, notified: bool },
         pickup_images_complete: { timestamp: DateTime, count: int, notified: bool },
         started_transit: { timestamp: DateTime, notified: bool },
         arrived_at_delivery: { timestamp: DateTime, notified: bool },
         delivery_images_complete: { timestamp: DateTime, count: int, notified: bool },
         marked_complete: { timestamp: DateTime, notified: bool }
     }

     New Methods:
     def update_driver_progress(order_id, progress_key, metadata) -> Tuple[bool, str]:
         """Update driver progress atomically"""

     def get_driver_progress_status(order_id) -> Dict:
         """Get current driver progress state"""

     def has_minimum_images(order_id, image_type, minimum=5) -> Tuple[bool, int]:
         """Check if order has minimum images"""

     1.2 Keep Existing Status System (For Customers Only)

     - All STATUS_* constants unchanged
     - Order status now ONLY controlled by admin
     - Status changes still trigger customer emails

     ---
     Phase 2: Driver Service - Complete Rewrite

     2.1 New Driver Progress Methods

     File: services/driver_service.py

     Replace existing status update methods with:

     def driver_arrived_pickup(order_id, driver_id) -> Tuple[bool, str]:
         """Driver arrived at pickup location
         - Updates driver_progress.arrived_at_pickup
         - Sends admin notification
         - NO order status change
         """

     def driver_complete_pickup_images(order_id, driver_id) -> Tuple[bool, str]:
         """Driver completed 5+ pickup images
         - Validates minimum 5 images
         - Updates driver_progress.pickup_images_complete
         - Sends BATCH email to admin with image count
         - NO order status change
         """

     def driver_start_transit(order_id, driver_id) -> Tuple[bool, str]:
         """Driver clicked "Aloita ajo" button
         - Updates driver_progress.started_transit
         - Sends admin notification
         - NO order status change
         - Driver can do this immediately after uploading images
         """

     def driver_arrived_delivery(order_id, driver_id) -> Tuple[bool, str]:
         """Driver arrived at delivery location
         - Updates driver_progress.arrived_at_delivery  
         - Sends admin notification
         - NO order status change
         """

     def driver_complete_delivery_images(order_id, driver_id) -> Tuple[bool, str]:
         """Driver completed 5+ delivery images
         - Validates minimum 5 images
         - Updates driver_progress.delivery_images_complete
         - Sends BATCH email to admin with image count
         - NO order status change
         """

     def driver_mark_complete(order_id, driver_id) -> Tuple[bool, str]:
         """Driver clicked "Toimitettu" button (job done from driver perspective)
         - Updates driver_progress.marked_complete
         - Sends admin notification
         - NO order status change
         - Driver workflow is complete
         """

     Remove These Methods:
     - mark_arrival() - replaced by driver_arrived_pickup()
     - start_transport() - replaced by driver_start_transit()
     - arrive_at_delivery() - replaced by driver_arrived_delivery()
     - complete_delivery() - replaced by driver_mark_complete()
     - update_pickup_images_status() - replaced by driver_complete_pickup_images()
     - update_delivery_images_status() - replaced by driver_complete_delivery_images()

     2.2 Update Permission Checks

     def can_add_pickup_images(order_id, driver_id) -> bool:
         """Driver can upload pickup images if they've arrived at pickup"""
         progress = order_model.get_driver_progress_status(order_id)
         return progress.get('arrived_at_pickup') is not None

     def can_add_delivery_images(order_id, driver_id) -> bool:
         """Driver can upload delivery images if they've started transit"""
         progress = order_model.get_driver_progress_status(order_id)
         return progress.get('started_transit') is not None

     ---
     Phase 3: Image Upload System

     3.1 Minimum Image Validation

     File: services/image_service.py

     def validate_minimum_images(order_id, image_type, minimum=5) -> Tuple[bool, int, str]:
         """
         Returns: (meets_requirement, current_count, error_message)
         Used to enable/disable "Vahvista" buttons
         """

     3.2 Driver Upload Endpoints

     File: routes/driver.py

     Changes:
     - Remove automatic status updates from image upload
     - Return image count in response
     - Let frontend enable "Vahvista" button when count >= 5
     - "Vahvista" button calls separate endpoint to trigger batch notification

     ---
     Phase 4: Driver Routes - Complete Workflow

     4.1 Update All Driver Action Routes

     File: routes/driver.py

     @driver_bp.route('/job/<int:order_id>/arrive_pickup', methods=['POST'])
     def arrive_pickup(order_id):
         """Step 1: Driver arrives at pickup"""
         driver = auth_service.get_current_user()
         success, error = driver_service.driver_arrived_pickup(order_id, driver['id'])
         # Admin notified, driver proceeds to upload images

     @driver_bp.route('/job/<int:order_id>/confirm_pickup_images', methods=['POST'])
     def confirm_pickup_images(order_id):
         """Step 2: Driver confirms 5+ pickup images uploaded"""
         driver = auth_service.get_current_user()
         success, error = driver_service.driver_complete_pickup_images(order_id, driver['id'])
         # Validates 5+ images, sends batch email to admin
         # "Aloita ajo" button becomes available

     @driver_bp.route('/job/<int:order_id>/start_transit', methods=['POST'])
     def start_transit(order_id):
         """Step 3: Driver starts transit (NO WAITING for admin)"""
         driver = auth_service.get_current_user()
         success, error = driver_service.driver_start_transit(order_id, driver['id'])
         # Admin notified, driver proceeds to delivery

     @driver_bp.route('/job/<int:order_id>/arrive_delivery', methods=['POST'])
     def arrive_delivery(order_id):
         """Step 4: Driver arrives at delivery"""
         driver = auth_service.get_current_user()
         success, error = driver_service.driver_arrived_delivery(order_id, driver['id'])
         # Admin notified, driver proceeds to upload images

     @driver_bp.route('/job/<int:order_id>/confirm_delivery_images', methods=['POST'])
     def confirm_delivery_images(order_id):
         """Step 5: Driver confirms 5+ delivery images uploaded"""
         driver = auth_service.get_current_user()
         success, error = driver_service.driver_complete_delivery_images(order_id, driver['id'])
         # Validates 5+ images, sends batch email to admin
         # "Toimitettu" button becomes available

     @driver_bp.route('/job/<int:order_id>/mark_complete', methods=['POST'])
     def mark_complete(order_id):
         """Step 6: Driver marks job complete (NO WAITING for admin)"""
         driver = auth_service.get_current_user()
         success, error = driver_service.driver_mark_complete(order_id, driver['id'])
         # Admin notified, driver workflow complete

     ---
     Phase 5: Driver UI - Independent Workflow

     5.1 Driver Job Detail Template

     File: templates/driver/job_detail.html

     Complete Button Flow (Based on driver_progress, NOT order status):

     {% if not order.driver_id %}
       <!-- Available job -->
       <button>Ota työ vastaan</button>

     {% elif order.driver_id == driver.id %}
       <!-- Job belongs to this driver - show based on DRIVER PROGRESS -->

       {% set progress = order.driver_progress or {} %}
       
       {% if not progress.arrived_at_pickup %}
         <!-- Step 1: Not arrived yet -->
         <button action="arrive_pickup">Saavuin noutopaikalle</button>
       
       {% elif not progress.pickup_images_complete %}
         <!-- Step 2: Upload pickup images -->
         <div class="image-upload-section">
           <p>Lisää vähintään 5 noutokuvaa</p>
           <p>Kuvia lisätty: <span id="pickup-count">{{ pickup_image_count }}</span>/5</p>
           <button id="confirm-pickup-btn" disabled>Vahvista noutokuvat</button>
           <!-- Button enabled via JavaScript when count >= 5 -->
         </div>
       
       {% elif not progress.started_transit %}
         <!-- Step 3: Start transit (NO WAITING) -->
         <button action="start_transit">Aloita ajo</button>

       {% elif not progress.arrived_at_delivery %}
         <!-- Step 4: Arrive at delivery -->
         <button action="arrive_delivery">Saavuin toimituspaikalle</button>

       {% elif not progress.delivery_images_complete %}
         <!-- Step 5: Upload delivery images -->
         <div class="image-upload-section">
           <p>Lisää vähintään 5 toimituskuvaa</p>
           <p>Kuvia lisätty: <span id="delivery-count">{{ delivery_image_count }}</span>/5</p>
           <button id="confirm-delivery-btn" disabled>Vahvista toimituskuvat</button>
         </div>

       {% elif not progress.marked_complete %}
         <!-- Step 6: Mark complete (NO WAITING) -->
         <button action="mark_complete">Toimitettu</button>

       {% else %}
         <!-- Step 7: Driver done -->
         <div class="completed-state">
           <p>✓ Tehtävä suoritettu!</p>
           <p>Admin käsittelee toimituksen.</p>
         </div>
       {% endif %}

     {% else %}
       <!-- Job belongs to another driver -->
       <p>Tämä työ on määritetty toiselle kuljettajalle</p>
     {% endif %}

     Key Changes:
     - Remove ALL references to order.status for driver actions
     - Use order.driver_progress to determine button state
     - Remove "Odottaa admin hyväksyntää" messages
     - Driver flows through ALL steps without stopping

     5.2 Image Counter UI

     Add to template:

     <!-- Pickup Images Section -->
     <div id="pickup-images-section">
       <h3>Noutokuvat</h3>
       <div class="image-counter" id="pickup-counter">
         <span class="count">{{ pickup_image_count }}</span>/5
       </div>
       <!-- Upload form -->
       <button id="confirm-pickup-btn" 
               class="btn btn-primary" 
               disabled="{{ 'disabled' if pickup_image_count < 5 else '' }}">
         Vahvista noutokuvat ({{ pickup_image_count }}/5)
       </button>
     </div>

     <!-- Same for delivery images -->

     5.3 JavaScript for Dynamic Updates

     File: static/js/driver-image-upload.js

     // After each image upload, update counter
     function updateImageCounter(imageType, newCount) {
       const countElement = document.getElementById(`${imageType}-count`);
       const confirmButton = document.getElementById(`confirm-${imageType}-btn`);

       countElement.textContent = newCount;

       // Enable button when count >= 5
       if (newCount >= 5) {
         confirmButton.disabled = false;
         confirmButton.classList.add('enabled');
       }
     }

     // AJAX upload with counter update
     function uploadImage(imageType, file) {
       // ... upload logic ...
       // On success:
       updateImageCounter(imageType, response.image_count);
     }

     ---
     Phase 6: Email Notifications

     6.1 New Admin Notification Method

     File: services/email_service.py

     def send_admin_driver_progress_notification(order_id, driver_name, progress_event, order_data, metadata=None):
         """
         Single method for all driver progress notifications
         
         progress_event values:
         - "ARRIVED_PICKUP": Driver arrived at pickup
         - "PICKUP_IMAGES_COMPLETE": Driver completed 5+ images (metadata: count)
         - "STARTED_TRANSIT": Driver started transit
         - "ARRIVED_DELIVERY": Driver arrived at delivery
         - "DELIVERY_IMAGES_COMPLETE": Driver completed 5+ images (metadata: count)
         - "MARKED_COMPLETE": Driver marked job complete
         
         **IMPORTANT: Works with dev email mock system**
         - In FLASK_ENV=development: Saves to static/dev_emails/
         - In production: Sends via Zoho SMTP
         - Uses existing send_email() method which handles both modes
         """
         admin_email = os.getenv("ADMIN_EMAIL", "support@levoro.fi")

         event_descriptions = {
             "ARRIVED_PICKUP": f"{driver_name} on saapunut noutopaikalle",
             "PICKUP_IMAGES_COMPLETE": f"{driver_name} on lisännyt {metadata.get('count', 0)} noutokuvaa",
             "STARTED_TRANSIT": f"{driver_name} on aloittanut kuljetuksen",
             "ARRIVED_DELIVERY": f"{driver_name} on saapunut toimituspaikalle",
             "DELIVERY_IMAGES_COMPLETE": f"{driver_name} on lisännyt {metadata.get('count', 0)} toimituskuvaa",
             "MARKED_COMPLETE": f"{driver_name} on merkinnyt toimituksen valmiiksi"
         }

         base_url = os.getenv("BASE_URL", "http://localhost:8000")
         order_detail_url = f"{base_url}/admin/order/{order_id}"

         # Render HTML email template
         html_body = f"""
         <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
           <div style="background: linear-gradient(135deg, #f59e0b, #d97706); color: white; padding: 30px; border-radius: 12px;">
             <h1>Kuljettajan eteneminen</h1>
             <p>Tilaus #{order_id}</p>
           </div>
           
           <div style="padding: 30px; background: #f3f4f6; border-radius: 8px; margin: 20px 0;">
             <h2 style="color: #92400e;">{event_descriptions.get(progress_event, progress_event)}</h2>
             <p><strong>Kuljettaja:</strong> {driver_name}</p>
             <p><strong>Tilaus:</strong> #{order_id}</p>
             <p><strong>Reitti:</strong> {order_data.get('pickup_address')} → {order_data.get('dropoff_address')}</p>
           </div>
           
           <div style="text-align: center; margin: 30px 0;">
             <a href="{order_detail_url}" style="background: #3b82f6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none;">
               Näytä tilaus admin-paneelissa
             </a>
           </div>
           
           <div style="background: #dbeafe; padding: 15px; border-radius: 8px;">
             <p style="margin: 0; color: #1e40af; font-size: 14px;">
               <strong>Huomio:</strong> Kuljettaja etenee itsenäisesti. Voit päivittää tilauksen tilan admin-paneelista kun haluat ilmoittaa asiakkaalle.
             </p>
           </div>
         </div>
         """

         # Use existing send_email() method - automatically handles dev/prod modes
         return self.send_email(
             subject=f"[Levoro] Kuljettajan eteneminen - Tilaus #{order_id}",
             recipients=[admin_email],
             html_body=html_body
         )

     Key Points:
     - Uses existing send_email() method which already supports dev mode
     - In FLASK_ENV=development: Emails saved to static/dev_emails/
     - View at: http://localhost:8000/static/dev_emails/index.html
     - Same behavior as existing email notifications

     6.2 Development Email Testing

     Existing System (No Changes Needed):

     The current send_email() method in email_service.py already handles development mode:
     - Lines 55-68: Checks FLASK_ENV=development
     - Calls _save_email_to_file() instead of sending via SMTP
     - Saves to static/dev_emails/ directory
     - Updates index.html with list of all emails
     - Auto-refresh every 5 seconds

     New driver progress emails will automatically:
     - ✅ Be saved as HTML files in dev mode
     - ✅ Appear in the email inbox at /static/dev_emails/index.html
     - ✅ Show metadata (from, to, subject, timestamp)
     - ✅ Be viewable by clicking "View Email"

     Testing Driver Progress Emails in Dev:
     1. Set FLASK_ENV=development in .env
     2. Run application: python app.py
     3. Complete driver workflow (accept job, arrive, upload images, etc.)
     4. Open: http://localhost:8000/static/dev_emails/index.html
     5. See all 6 driver progress emails:
       - "Driver arrived at pickup"
       - "Driver added 5 pickup images" (batch)
       - "Driver started transit"
       - "Driver arrived at delivery"
       - "Driver added 5 delivery images" (batch)
       - "Driver marked complete"

     6.3 Email Template Design

     Template structure:
     - Header: "Kuljettajan eteneminen - Tilaus #123"
     - Event description (Finnish)
     - Driver name and timestamp
     - Order details (route, reg number, etc.)
     - Important note: "Kuljettaja etenee itsenäisesti. Voit päivittää tilauksen tilan admin-paneelista."
     - Link to admin order detail page

     ---
     Phase 7: Admin Panel Updates

     7.1 Remove Old Approval System

     File: routes/admin.py

     Remove these routes:
     - /order/<id>/approve-pickup-images (lines 692-722)
     - /order/<id>/approve-delivery-images (lines 725-755)

     7.2 Add Driver Progress Display

     File: templates/admin/order_detail.html

     Add new section showing driver progress:

     <div class="driver-progress-panel">
       <h3>Kuljettajan eteneminen</h3>
       {% set progress = order.driver_progress or {} %}

       <div class="progress-timeline">
         <div class="progress-item {{ 'completed' if progress.arrived_at_pickup else 'pending' }}">
           <span class="icon">{{ '✓' if progress.arrived_at_pickup else '○' }}</span>
           <span class="label">Saapunut noutopaikalle</span>
           {% if progress.arrived_at_pickup %}
             <span class="timestamp">{{ progress.arrived_at_pickup.timestamp|helsinki_time }}</span>
           {% endif %}
         </div>

         <div class="progress-item {{ 'completed' if progress.pickup_images_complete else 'pending' }}">
           <span class="icon">{{ '✓' if progress.pickup_images_complete else '○' }}</span>
           <span class="label">Noutokuvat lisätty</span>
           {% if progress.pickup_images_complete %}
             <span class="count">({{ progress.pickup_images_complete.count }} kuvaa)</span>
             <span class="timestamp">{{ progress.pickup_images_complete.timestamp|helsinki_time }}</span>
           {% endif %}
         </div>

         <div class="progress-item {{ 'completed' if progress.started_transit else 'pending' }}">
           <span class="icon">{{ '✓' if progress.started_transit else '○' }}</span>
           <span class="label">Kuljetus aloitettu</span>
           {% if progress.started_transit %}
             <span class="timestamp">{{ progress.started_transit.timestamp|helsinki_time }}</span>
           {% endif %}
         </div>

         <div class="progress-item {{ 'completed' if progress.arrived_at_delivery else 'pending' }}">
           <span class="icon">{{ '✓' if progress.arrived_at_delivery else '○' }}</span>
           <span class="label">Saapunut toimituspaikalle</span>
           {% if progress.arrived_at_delivery %}
             <span class="timestamp">{{ progress.arrived_at_delivery.timestamp|helsinki_time }}</span>
           {% endif %}
         </div>

         <div class="progress-item {{ 'completed' if progress.delivery_images_complete else 'pending' }}">
           <span class="icon">{{ '✓' if progress.delivery_images_complete else '○' }}</span>
           <span class="label">Toimituskuvat lisätty</span>
           {% if progress.delivery_images_complete %}
             <span class="count">({{ progress.delivery_images_complete.count }} kuvaa)</span>
             <span class="timestamp">{{ progress.delivery_images_complete.timestamp|helsinki_time }}</span>
           {% endif %}
         </div>

         <div class="progress-item {{ 'completed' if progress.marked_complete else 'pending' }}">
           <span class="icon">{{ '✓' if progress.marked_complete else '○' }}</span>
           <span class="label">Kuljettaja merkinnyt valmiiksi</span>
           {% if progress.marked_complete %}
             <span class="timestamp">{{ progress.marked_complete.timestamp|helsinki_time }}</span>
           {% endif %}
         </div>
       </div>

       <div class="progress-note">
         <p><strong>Huomio:</strong> Kuljettaja etenee itsenäisesti. Päivitä tilauksen tila alla olevasta valikosta.</p>
       </div>
     </div>

     <!-- Separate section: Admin controls order status -->
     <div class="order-status-control">
       <h3>Tilauksen tila (asiakkaalle näkyvä)</h3>
       <form method="POST" action="{{ url_for('admin.update_order') }}">
         <select name="status">
           <!-- All existing statuses -->
         </select>
         <button type="submit">Päivitä tila</button>
       </form>
       <p class="info">Tilan muutos lähettää asiakkaalle sähköpostin.</p>
     </div>

     CSS for timeline:
     - Vertical timeline with checkmarks
     - Green for completed, gray for pending
     - Timestamps in smaller font
     - Image counts prominently displayed

     ---
     Phase 8: Status Translation Updates

     8.1 Update Customer Display

     File: utils/status_translations.py

     # Line 10 - Update display text
     'ASSIGNED_TO_DRIVER': 'Noudossa',  # Changed from 'Kuljettaja määritetty'

     # Line 24 - Update description  
     'ASSIGNED_TO_DRIVER': 'Kuljettaja on noudossa. Saat ilmoituksen kun kuljetus alkaa.',

     Keep all other translations unchanged.

     ---
     Phase 9: Database Migration

     9.1 Migration Script

     File: migrations/add_driver_progress.py

     def migrate_driver_progress():
         """Add driver_progress field to all orders"""
         from models.order import order_model
         from datetime import datetime, timezone

         # Get all orders
         orders = order_model.find({})

         for order in orders:
             order_id = order['id']
             driver_progress = {}

             # Infer progress from current status and images
             status = order.get('status')
             images = order.get('images', {})

             # Set notified=True to avoid duplicate emails
             if status in ['DRIVER_ARRIVED', 'PICKUP_IMAGES_ADDED', 'IN_TRANSIT',
                           'DELIVERY_ARRIVED', 'DELIVERY_IMAGES_ADDED', 'DELIVERED']:
                 driver_progress['arrived_at_pickup'] = {
                     'timestamp': order.get('arrival_time') or order.get('updated_at'),
                     'notified': True
                 }

             if status in ['PICKUP_IMAGES_ADDED', 'IN_TRANSIT', 'DELIVERY_ARRIVED',
                           'DELIVERY_IMAGES_ADDED', 'DELIVERED']:
                 pickup_count = len(images.get('pickup', []))
                 driver_progress['pickup_images_complete'] = {
                     'timestamp': order.get('pickup_started') or order.get('updated_at'),
                     'count': pickup_count,
                     'notified': True
                 }

             if status in ['IN_TRANSIT', 'DELIVERY_ARRIVED', 'DELIVERY_IMAGES_ADDED', 'DELIVERED']:
                 driver_progress['started_transit'] = {
                     'timestamp': order.get('pickup_started') or order.get('updated_at'),
                     'notified': True
                 }

             if status in ['DELIVERY_ARRIVED', 'DELIVERY_IMAGES_ADDED', 'DELIVERED']:
                 driver_progress['arrived_at_delivery'] = {
                     'timestamp': order.get('delivery_arrival_time') or order.get('updated_at'),
                     'notified': True
                 }

             if status in ['DELIVERY_IMAGES_ADDED', 'DELIVERED']:
                 delivery_count = len(images.get('delivery', []))
                 driver_progress['delivery_images_complete'] = {
                     'timestamp': order.get('delivery_completed') or order.get('updated_at'),
                     'count': delivery_count,
                     'notified': True
                 }

             if status == 'DELIVERED':
                 driver_progress['marked_complete'] = {
                     'timestamp': order.get('delivery_completed') or order.get('updated_at'),
                     'notified': True
                 }

             # Update order with driver_progress
             order_model.update_one(
                 {'id': order_id},
                 {'$set': {'driver_progress': driver_progress}}
             )

         print(f"✓ Migrated {len(orders)} orders with driver_progress field")

     ---
     Phase 10: Testing Strategy

     10.1 Development Email Testing Workflow

     Set up dev environment:
     # .env file
     FLASK_ENV=development

     # Start app
     python app.py

     Test driver progress emails:
     1. Open email inbox: http://localhost:8000/static/dev_emails/index.html
     2. Complete driver workflow:
       - Accept job
       - Arrive pickup → Check inbox for "saapunut noutopaikalle" email
       - Upload 5 images → Click "Vahvista" → Check inbox for "lisännyt 5 noutokuvaa" email
       - Click "Aloita ajo" → Check inbox for "aloittanut kuljetuksen" email
       - Arrive delivery → Check inbox
       - Upload 5 images → Click "Vahvista" → Check inbox
       - Click "Toimitettu" → Check inbox
     3. Verify 6 emails total in inbox
     4. Click each email to view full HTML
     5. Verify metadata (from, to, subject, timestamp)

     10.2 Full Workflow Test

     Test Scenario:
     1. Customer creates order → Admin confirms → Admin assigns driver
     2. Driver accepts job
       - Driver sees: "Saavuin noutopaikalle" button
       - Admin gets email (check dev inbox): "Driver X accepted job"
     3. Driver arrives pickup (clicks button)
       - driver_progress.arrived_at_pickup updated
       - Admin gets email: "Driver arrived at pickup"
       - Driver sees: Image upload section + disabled "Vahvista" button
     4. Driver uploads 4 images
       - Counter shows: "4/5"
       - Button remains disabled
       - NO email sent
     5. Driver uploads 5th image
       - Counter shows: "5/5"
       - "Vahvista noutokuvat" button enables (green)
     6. Driver clicks "Vahvista noutokuvat"
       - driver_progress.pickup_images_complete updated
       - Admin gets BATCH email: "Driver added 5 pickup images"
       - Driver sees: "Aloita ajo" button (NO WAITING)
     7. Driver clicks "Aloita ajo"
       - driver_progress.started_transit updated
       - Admin gets email: "Driver started transit"
       - Driver sees: "Saavuin toimituspaikalle" button
     8. Admin manually updates status to IN_TRANSIT
       - Customer gets email: "Kuljetuksessa"
       - Driver workflow unaffected (continues independently)
     9. Driver arrives delivery (clicks button)
       - driver_progress.arrived_at_delivery updated
       - Admin gets email: "Driver arrived at delivery"
       - Driver sees: Image upload + disabled "Vahvista" button
     10. Driver uploads 5 delivery images + clicks "Vahvista"
       - driver_progress.delivery_images_complete updated
       - Admin gets BATCH email: "Driver added 5 delivery images"
       - Driver sees: "Toimitettu" button (NO WAITING)
     11. Driver clicks "Toimitettu"
       - driver_progress.marked_complete updated
       - Admin gets email: "Driver marked complete"
       - Driver sees: "Tehtävä suoritettu!" message
       - Order status still unchanged (whatever admin set it to)
     12. Admin manually updates status to DELIVERED
       - Customer gets email: "Toimitettu"
       - Workflow complete

     Verify in dev email inbox:
     - Total emails: 8 (6 driver progress + 2 customer status updates)
     - All driver emails have [Levoro] prefix
     - All show correct order details
     - Batch emails show image counts

     10.3 Edge Cases

     - Driver uploads 6+ images (counter shows 6/5, still valid)
     - Driver leaves page after 4 images, returns later (counter persists)
     - Multiple drivers try to accept same job (first one wins)
     - Admin changes status while driver working (no conflict)
     - Network failure during image upload (retry mechanism)
     - Driver clicks "Vahvista" with 4 images (validation error)
     - Dev email inbox with 50+ emails (pagination works)

     ---
     Phase 11: Implementation Order

     1. Models & Database - Add driver_progress field + helper methods
     2. Migration - Add field to existing orders (run in dev first)
     3. Driver Service - Rewrite all driver progress methods
     4. Email Service - Add admin notification method (uses existing dev mode)
     5. Driver Routes - Update all action endpoints
     6. Driver UI - Complete template rewrite with progress-based logic
     7. Driver JavaScript - Image counter + button enable/disable
     8. Admin Panel - Add progress timeline display
     9. Status Translations - Update "Noudossa" text
     10. Testing - Full workflow + edge cases + dev email verification
     11. Documentation - Update CLAUDE.md and issues.md

     ---
     Success Criteria

     ✅ Driver completes entire workflow without waiting for admin
     ✅ "Aloita ajo" button available immediately after confirming pickup images
     ✅ "Toimitettu" button available immediately after confirming delivery images
     ✅ Admin receives 6 notification emails (not 10+)
     ✅ Batch emails include image counts (not individual uploads)
     ✅ Minimum 5 images enforced (button disabled until 5)
     ✅ Image counter updates in real-time (X/5)
     ✅ Driver UI uses driver_progress, NOT order.status
     ✅ Customer emails only sent when admin updates status
     ✅ Admin sees driver progress timeline
     ✅ Backward compatible with existing orders
     ✅ No duplicate notifications
     ✅ Dev email mock system works for driver progress emails
     ✅ All 6 driver progress emails visible in dev inbox
     ✅ Email metadata correct (from, to, subject)