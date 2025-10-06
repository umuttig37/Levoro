# Levoro - Autonkuljetuspalvelut

Professional vehicle transport service platform built with Flask.

## 📚 Documentation

### **Start Here**
- **[CLAUDE.md](CLAUDE.md)** - 📖 Complete application architecture, development guide, and patterns
- **[issues.md](issues.md)** - 🐛 Current open issues and pending tasks
- **[docs/](docs/)** - 📂 Additional documentation (features, testing, archive)

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Virtual environment
- SQLite database

### Development Setup

```bash
# 1. Clone and navigate to project
cd Levoro

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# 6. Run the application
python app.py
```

### Development Mode

```bash
# In .env file, set:
FLASK_ENV=development

# This enables:
# - Email mock system (saves to static/dev_emails/)
# - Debug mode
# - Auto-reload on code changes
```

## 🏗️ Architecture

```
Levoro/
├── app.py                  # Main Flask application
├── models/                 # Database models (Order, User, DriverApplication)
├── routes/                 # Route handlers (admin, api, auth, driver, main)
├── services/               # Business logic (email, order, driver, auth, image)
├── utils/                  # Helper functions (formatters, status translations)
├── templates/              # Jinja2 templates
├── static/                 # Static assets (CSS, JS, images)
└── docs/                   # Documentation

Pattern: Service Layer Architecture
- Routes: Thin controllers, handle HTTP
- Services: Business logic, database operations
- Models: Data structure and database access
```

## 👥 User Roles

1. **Customer** - Place transport orders, track status
2. **Driver** - Accept jobs, update status, upload photos
3. **Admin** - Manage orders, verify photos, assign drivers, set pricing

## 🔑 Key Features

- **Order Management** - Multi-step order wizard with real-time pricing
- **Driver Portal** - Job listings, acceptance workflow, photo uploads
- **Admin Dashboard** - Complete order control, driver rewards, status management
- **Email Notifications** - Professional responsive templates (no emojis!)
- **Image Management** - Pickup/delivery photo uploads with GCS integration
- **Role-Based Access** - Secure authentication and authorization

## 🧪 Testing

```bash
# Test email mock system
python test_email_mock.py

# View generated emails
# Open: http://localhost:8000/static/dev_emails/index.html

# Test email templates visually
python test_email_templates.py
```

See [docs/testing/](docs/testing/) for comprehensive testing guides.

## 📧 Email System

**Development Mode**: Emails saved as HTML to `static/dev_emails/`
**Production Mode**: Emails sent via SMTP

All email templates use:
- ✅ Responsive design (mobile-first)
- ✅ Blue theme (#3b82f6)
- ✅ NO EMOJIS (professional icons)
- ✅ Base template system

See [docs/features/EMAIL_TEMPLATE_REDESIGN.md](docs/features/EMAIL_TEMPLATE_REDESIGN.md)

## 🚗 Order Workflow

```
Customer creates order
    ↓
Admin reviews and sets driver reward
    ↓
Order becomes visible to drivers
    ↓
Driver accepts job
    ↓
Driver uploads pickup photos → Admin verifies → Admin sets IN_TRANSIT
    ↓
Driver marks arrived at destination
    ↓
Driver uploads delivery photos → Admin verifies → Admin sets DELIVERED
```

**Key Rule**: Admin controls all critical status changes (IN_TRANSIT, DELIVERED)

See [docs/features/WORKFLOW_ANALYSIS.md](docs/features/WORKFLOW_ANALYSIS.md)

## 🛠️ Development Commands

```bash
# Run application
python app.py

# Run with specific port
python app.py --port 8080

# Data integrity check
python check_data_integrity.py

# Initialize email inbox
python initialize_email_inbox.py

# Maintenance scripts
python cleanup_orphaned_records.py
python fix_user_status.py
```

## 📁 Project Structure Details

### Models (`models/`)
- `database.py` - BaseModel, CounterManager, database utilities
- `user.py` - User model (customer, driver, admin roles)
- `order.py` - Order model with status workflow
- `driver_application.py` - Driver application model

### Services (`services/`)
- `order_service.py` - Order CRUD, status updates, pricing
- `auth_service.py` - Authentication, registration, login
- `driver_service.py` - Driver applications, job listings
- `email_service.py` - Email notifications, template rendering
- `image_service.py` - Image uploads, GCS integration
- `gcs_service.py` - Google Cloud Storage operations

### Routes (`routes/`)
- `main.py` - Public pages (home, contact)
- `auth.py` - Login, register, logout
- `admin.py` - Admin dashboard and order management
- `driver.py` - Driver dashboard and job operations
- `api.py` - AJAX endpoints for dynamic features

## 🔒 Security

- Password hashing with werkzeug.security
- Session-based authentication
- Role-based access control (@login_required decorators)
- Input validation and sanitization
- Secure file uploads with type/size validation

## 🌐 Deployment

```bash
# Production deployment (Heroku)
# Uses: Procfile, runtime.txt, requirements.txt

# Set environment variables
FLASK_ENV=production
SECRET_KEY=<your-secret-key>
DATABASE_URL=<your-database-url>
GOOGLE_CLOUD_PROJECT=<gcs-project>
GCS_BUCKET_NAME=<bucket-name>
```

## 📝 Contributing

1. Read [CLAUDE.md](CLAUDE.md) for architecture and patterns
2. Check [issues.md](issues.md) for current tasks
3. Follow the service layer pattern
4. Maintain role-based access control
5. NO EMOJIS in production code (use icons)
6. Update documentation for new features

## 📞 Support

- Email: support@levoro.fi
- Website: www.levoro.fi

## 📄 License

Proprietary - Levoro Oy

---

**For detailed technical documentation, always refer to [CLAUDE.md](CLAUDE.md)**
