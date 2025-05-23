# Blood Donation System

A comprehensive web application for managing blood donations, connecting donors with receivers, and streamlining the blood donation process.

## Features

- **User Management**
  - Multiple user roles (Admin, Donor, Receiver)
  - Secure authentication with 2FA support
  - Profile management
  - Password reset functionality

- **Donor Features**
  - Donor verification system
  - Document upload (ID, Medical certificates)
  - Donation tracking
  - Next eligible donation date calculation
  - Donation certificates

- **Receiver Features**
  - Blood request management
  - Real-time blood availability
  - Blood type compatibility matching
  - Request status tracking

- **Admin Features**
  - Verification management
  - Blood inventory control
  - User management
  - Impact statistics
  - Testimonials management
  - Activity logs

- **Communication**
  - Notifications
  - Email alerts

## Technical Stack

- **Backend**: Flask (Python)
- **Database**: PostgreSQL
- **Authentication**: Flask-Login
- **File Upload**: Werkzeug
- **Migration**: Flask-Migrate
- **Security**: CSRF Protection, 2FA

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd blood_donation_system
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   Create a `.env` file with the following variables:
   ```
   SESSION_SECRET=your_secret_key
   DATABASE_URL=postgresql://postgres:your_password@localhost:5432/bloodbridge
   ```

5. **Initialize the database**
   ```bash
   flask db upgrade
   ```

6. **Run the application**
   ```bash
   flask run
   ```

## Project Structure

```
blood_donation_system/
├── app.py                 # Main application file
├── models.py             # Database models
├── routes/               # Route handlers
├── static/              # Static files (CSS, JS, images)
├── templates/           # HTML templates
├── migrations/          # Database migrations
└── utils.py            # Utility functions
```

## Database Schema

- Users (Admin, Donor, Receiver)
- Blood Requests
- Donations
- Verifications
- Blood Inventory
- Notifications
- Impact Statistics
- Testimonials
- Admin Action Logs

## Security Features

- Password hashing
- CSRF protection
- Two-factor authentication
- Secure file uploads
- Role-based access control
- Session management

## API Documentation

The application follows RESTful principles for its endpoints:

- `/api/users`: User management
- `/api/donations`: Donation management
- `/api/requests`: Blood request management
- `/api/inventory`: Blood inventory management

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request
