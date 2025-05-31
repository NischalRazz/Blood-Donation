# Blood Donation System - Deployment Instructions

## System Requirements
- **Operating System**: Windows 10/11, Linux, or macOS
- **Python**: Version 3.8 or higher
- **Database**: SQLite (included) or PostgreSQL/MySQL for production
- **Memory**: Minimum 4GB RAM
- **Storage**: At least 2GB free space

## Pre-Deployment Setup

### 1. Install Python and Git
```bash
# Windows (using Chocolatey - optional)
choco install python git

# Or download from:
# Python: https://python.org/downloads/
# Git: https://git-scm.com/downloads/
```

### 2. Clone/Transfer the Project
```bash
# Option A: Clone from repository (if using Git)
git clone <repository-url> blood_donation_system
cd blood_donation_system

# Option B: Copy files manually
# Copy the entire project folder to the target location
```

## Deployment Steps

### 1. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the project root with the following configuration:

```env
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your-very-secret-key-here-change-this
DATABASE_URL=sqlite:///blood_donation.db

# Email Configuration (for notifications)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

# Security
WTF_CSRF_ENABLED=True
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
```

### 4. Database Setup
```bash
# Initialize the database
python migrate.py

# Seed initial data (testimonials and stats)
python seed_data.py

# Create admin user (follow prompts)
python create_admin.py
```

### 5. File Permissions Setup
```bash
# Create upload directories and set permissions
mkdir -p static/uploads/id_documents
mkdir -p static/uploads/address_proofs

# Windows (PowerShell as Administrator)
icacls "static\uploads" /grant Everyone:(OI)(CI)M

# Linux/macOS
chmod -R 755 static/uploads
```

### 6. Test the Application
```bash
# Start the development server for testing
python app.py

# The application should be available at:
# http://localhost:5000
```

## Production Deployment

### Option 1: Using Gunicorn (Recommended for Linux/macOS)
```bash
# Install Gunicorn
pip install gunicorn

# Start the application
gunicorn --bind 0.0.0.0:5000 --workers 3 app:app
```

### Option 2: Using Waitress (Recommended for Windows)
```bash
# Install Waitress
pip install waitress

# Start the application
waitress-serve --host=0.0.0.0 --port=5000 app:app
```

### Option 3: Using Apache/Nginx (Advanced)
Configure Apache or Nginx as a reverse proxy to the Python application.

## Post-Deployment Configuration

### 1. Admin Account Setup
- Run `python create_admin.py` to create your first admin account
- Login at `/admin/login` with the created credentials

### 2. System Configuration
- Configure email settings for notifications
- Set up backup procedures for the database
- Configure SSL certificates for HTTPS (production)

### 3. User Suspension Feature
The suspension functionality is now fully implemented with:
- **Admin Interface**: Suspend/unsuspend users from admin panel
- **Duration Options**: 1 hour to 1 year suspension periods
- **Auto-Expiration**: Suspensions automatically expire
- **Audit Trail**: All suspension actions are logged
- **Status Display**: Clear suspension status in admin views

## Security Checklist

- [ ] Change the default `SECRET_KEY` in `.env`
- [ ] Set `FLASK_ENV=production` for production deployment
- [ ] Enable HTTPS with SSL certificates
- [ ] Configure firewall rules to restrict access
- [ ] Set up regular database backups
- [ ] Review and update file upload permissions
- [ ] Configure email authentication (app passwords)

## Troubleshooting

### Common Issues

1. **Database Migration Errors**
   ```bash
   # Reset database if needed
   rm blood_donation.db
   python migrate.py
   ```

2. **Permission Errors on Uploads**
   ```bash
   # Windows
   icacls "static\uploads" /grant Everyone:(OI)(CI)F
   
   # Linux/macOS
   chmod -R 777 static/uploads
   ```

3. **Email Notifications Not Working**
   - Verify SMTP settings in `.env`
   - Use app passwords for Gmail
   - Check firewall/antivirus blocking SMTP

4. **Suspension Feature Issues**
   - Verify database migration completed successfully
   - Check admin permissions are properly set
   - Review application logs for errors

### Log Files
- Application logs: Check console output or configure logging
- Admin actions: Stored in `admin_action_logs` table
- Suspension history: Available in admin interface

## Maintenance

### Regular Tasks
- **Database Backup**: Schedule regular backups of `blood_donation.db`
- **Log Rotation**: Monitor and rotate application logs
- **Updates**: Keep dependencies updated with `pip install -r requirements.txt --upgrade`
- **Suspension Cleanup**: Expired suspensions are automatically handled

### Monitoring
- Monitor disk space in `static/uploads/`
- Check database size growth
- Monitor application performance and response times
- Review suspension logs for patterns

## Support

For technical issues:
1. Check the troubleshooting section above
2. Review application logs for error messages
3. Verify all configuration settings in `.env`
4. Test database connectivity and permissions

## Version Information
- **Flask Version**: 2.0+
- **Python Version**: 3.8+
- **Database**: SQLite (default) or PostgreSQL/MySQL
- **Features**: Complete user suspension system with admin controls
