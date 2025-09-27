# Driver Workflow Documentation

This document describes the complete driver workflow system in the Levoro car rental/transport application, including status transitions, UI interactions, and business rules.

## Status Flow Overview

The order progresses through the following statuses in the driver workflow:

```
NEW → CONFIRMED → ASSIGNED_TO_DRIVER → DRIVER_ARRIVED → PICKUP_IMAGES_ADDED → IN_TRANSIT → DELIVERY_ARRIVED → DELIVERY_IMAGES_ADDED → DELIVERED
```

### Finnish Status Translations

| English Status | Finnish Translation | Description |
|---|---|---|
| NEW | UUSI | Initial order state |
| CONFIRMED | TEHTÄVÄ_VAHVISTETTU | Admin-confirmed, ready for driver assignment |
| ASSIGNED_TO_DRIVER | MÄÄRITETTY_KULJETTAJALLE | Driver assigned to order |
| DRIVER_ARRIVED | KULJETTAJA_SAAPUNUT | Driver arrived at pickup location |
| PICKUP_IMAGES_ADDED | NOUTOKUVAT_LISÄTTY | Pickup photos uploaded |
| IN_TRANSIT | TOIMITUKSESSA | Vehicle in transit to delivery |
| DELIVERY_ARRIVED | KULJETUS_SAAPUNUT | Driver arrived at delivery location |
| DELIVERY_IMAGES_ADDED | TOIMITUSKUVAT_LISÄTTY | Delivery photos uploaded |
| DELIVERED | TOIMITETTU | Order completed successfully |
| CANCELLED | PERUUTETTU | Order cancelled |

## Driver Workflow Steps

### 1. Order Visibility (`routes/driver.py`)
- **Driver Access Rule**: Only orders with status `CONFIRMED` are visible to drivers
- **Available Orders**: Retrieved via `get_available_orders()` method
- **Validation**: Orders must not have an assigned driver (`driver_id` field empty)

### 2. Job Acceptance
**Driver Action**: Click "Ota työ vastaan" (Accept Job)
- **Precondition**: Order status = `CONFIRMED`
- **Status Change**: `CONFIRMED` → `ASSIGNED_TO_DRIVER`
- **Database Update**: Sets `driver_id` and `assignment_time`
- **Email Notification**: Customer receives assignment notification

### 3. Arrival at Pickup Location
**Driver Action**: Click "Saavuin noutopaikalle" (Arrived at Pickup)
- **Precondition**: Order status = `ASSIGNED_TO_DRIVER`
- **Status Change**: `ASSIGNED_TO_DRIVER` → `DRIVER_ARRIVED`
- **Database Update**: Sets `pickup_arrival_time`
- **UI State**: Pickup image upload becomes available

### 4. Pickup Image Upload (Mandatory)
**Driver Action**: Upload pickup photos via image modal
- **Precondition**: Order status = `DRIVER_ARRIVED`
- **Validation**: At least one image required before proceeding
- **Status Change**: `DRIVER_ARRIVED` → `PICKUP_IMAGES_ADDED`
- **UI State**: "Aloita kuljetus" button becomes available

### 5. Start Transport
**Driver Action**: Click "Aloita kuljetus" (Start Transport)
- **Precondition**: Order status = `PICKUP_IMAGES_ADDED`
- **Status Change**: `PICKUP_IMAGES_ADDED` → `IN_TRANSIT`
- **Database Update**: Sets `pickup_completed_time`
- **Customer Notification**: Email sent about transport start

### 6. Arrival at Delivery Location
**Driver Action**: Click "Saavuin toimituspaikalle" (Arrived at Delivery)
- **Precondition**: Order status = `IN_TRANSIT`
- **Status Change**: `IN_TRANSIT` → `DELIVERY_ARRIVED`
- **Database Update**: Sets `delivery_arrival_time`
- **UI State**: Delivery image upload becomes available

### 7. Delivery Image Upload (Mandatory)
**Driver Action**: Upload delivery photos via image modal
- **Precondition**: Order status = `DELIVERY_ARRIVED`
- **Validation**: At least one image required before completion
- **Status Change**: `DELIVERY_ARRIVED` → `DELIVERY_IMAGES_ADDED`
- **UI State**: "Viimeistele toimitus" button becomes available

### 8. Complete Delivery
**Driver Action**: Click "Viimeistele toimitus" (Complete Delivery)
- **Precondition**: Order status = `DELIVERY_IMAGES_ADDED`
- **Status Change**: `DELIVERY_IMAGES_ADDED` → `DELIVERED`
- **Database Update**: Sets `delivery_completed_time`
- **Customer Notification**: Final delivery confirmation email

## Business Rules and Validations

### Image Upload Requirements
- **Pickup Images**: Mandatory after driver arrival at pickup
- **Delivery Images**: Mandatory after driver arrival at delivery
- **Validation**: Implemented in `services/driver_service.py`
  - `can_add_pickup_images()`: Checks `DRIVER_ARRIVED` status
  - `can_add_delivery_images()`: Checks `DELIVERY_ARRIVED` status

### Status Progression Validation
- **Sequential Flow**: Each status can only transition to the next logical status
- **No Skipping**: Drivers cannot skip intermediate steps
- **Image Gates**: Transport and delivery cannot proceed without required images

### Admin Oversight
- **Initial Gate**: Only `CONFIRMED` orders are available to drivers
- **Manual Confirmation**: Admins must confirm `NEW` orders before driver visibility
- **Override Capability**: Admins can manually change any order status

## Driver Interface Components

### Dashboard (`templates/driver/dashboard.html`)
- **Available Jobs**: Shows `CONFIRMED` orders without assigned drivers
- **My Active Jobs**: Shows driver's assigned orders in progress
- **Job Statistics**: Completed jobs count and performance metrics

### Job Detail View (`templates/driver/job_detail.html`)
- **Status-Dependent Actions**: UI buttons change based on current status
- **Progress Indicator**: Visual status progression display
- **Image Upload Modals**: Context-aware upload interfaces
- **Customer Information**: Contact details and special instructions

### Job List (`templates/driver/my_jobs.html`)
- **Status Filtering**: Color-coded status indicators
- **Quick Actions**: Direct links to job details
- **Progress Summary**: At-a-glance status overview

## Email Notifications

### Customer Notifications (`services/email_service.py`)
- **Assignment**: When driver accepts job
- **Status Updates**: At each major status transition
- **Completion**: Final delivery confirmation
- **Translations**: Status-specific Finnish descriptions

### Admin Notifications
- **New Orders**: Sent to support@levoro.fi for confirmation
- **New Users**: User registration alerts for approval

## Technical Implementation

### Database Schema
```
orders: {
  id: int,
  status: string,
  driver_id: int (optional),
  assignment_time: datetime,
  pickup_arrival_time: datetime,
  pickup_completed_time: datetime,
  delivery_arrival_time: datetime,
  delivery_completed_time: datetime,
  ...
}
```

### Key Service Methods
- `driver_service.accept_job()`: Assigns driver to order
- `driver_service.arrive_at_pickup()`: Marks pickup arrival
- `driver_service.start_transport()`: Begins transit
- `driver_service.arrive_at_delivery()`: Marks delivery arrival
- `driver_service.complete_delivery()`: Finalizes order

### Status Translation Functions
- `app.py:translate_status()`: Main UI translations
- `services/order_service.py:translate_status()`: Service layer translations
- `services/email_service.py`: Email-specific translations

## Error Handling

### Common Validation Errors
- **"Tilaus ei ole saatavilla"**: Order not available (wrong status or already assigned)
- **"Lisää ensin noutokuvat"**: Pickup images required before transport
- **"Lisää ensin toimituskuvat"**: Delivery images required before completion

### Recovery Scenarios
- **Status Mismatch**: Admin can manually adjust status
- **Missing Images**: Driver can upload images at appropriate status
- **Network Issues**: Actions are idempotent and can be retried

## Performance Considerations

- **Status Queries**: Indexed on `status` and `driver_id` fields
- **Driver Dashboard**: Cached order counts and statistics
- **Image Processing**: Async upload with progress indicators
- **Email Queue**: Background processing for notifications

This workflow ensures proper order tracking, customer communication, and quality control through mandatory image documentation at each critical step.