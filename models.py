from extensions import db
from flask_login import UserMixin
from datetime import datetime, timedelta
import pyotp
import secrets
import json

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), nullable=False, default='donor')
    # Additional profile fields
    blood_type = db.Column(db.String(5))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    gender = db.Column(db.String(10))
    date_of_birth = db.Column(db.Date)
    medical_conditions = db.Column(db.Text)
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 2FA fields
    totp_secret = db.Column(db.String(32))
    totp_enabled = db.Column(db.Boolean, default=False)

    # Donor verification fields
    is_verified = db.Column(db.Boolean, default=False)
    verification_status = db.Column(db.String(20), default='unverified')  # 'unverified', 'pending', 'approved', 'rejected'
    verification_date = db.Column(db.DateTime)
    last_donation_date = db.Column(db.DateTime)
    next_eligible_date = db.Column(db.DateTime)
    verification_note = db.Column(db.Text)
    
    # Suspension fields
    is_active = db.Column(db.Boolean, default=True)
    suspension_reason = db.Column(db.Text)
    suspended_at = db.Column(db.DateTime)
    suspended_until = db.Column(db.DateTime)
    suspended_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    suspended_by_user = db.relationship('User', remote_side=[id], backref='suspended_users')

    def get_totp_uri(self):
        """Generate the TOTP URI for QR code generation"""
        if self.totp_secret:
            return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
                name=self.email,
                issuer_name="Blood Donation System"
            )
        return None

    def verify_totp(self, token):
        """Verify the TOTP token"""
        if not self.totp_secret:
            return False
        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(token)

    def generate_totp_secret(self):
        """Generate a new TOTP secret"""
        self.totp_secret = pyotp.random_base32()
        return self.totp_secret

    def can_donate(self):
        """Check if user is eligible to donate based on verification and last donation date"""
        if not self.is_verified or self.verification_status != 'approved':
            return False, "You need to complete the verification process before donating."

        if self.next_eligible_date and self.next_eligible_date > datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0):
            return False, f"You are not eligible to donate until {self.next_eligible_date.strftime('%Y-%m-%d')}."

        return True, "You are eligible to donate blood."

    def get_full_name(self):
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}"

    def generate_password_reset_token(self):
        """Generate a new password reset token for the user"""
        # Invalidate any existing tokens
        for token in self.password_resets:
            if not token.used and datetime.utcnow() < token.expires_at:
                token.invalidate()

        # Create a new token
        reset = PasswordReset(user_id=self.id)
        db.session.add(reset)
        db.session.commit()
        return reset.token

    def verify_password_reset_token(self, token):
        """Verify if a given token is valid for this user"""
        reset = PasswordReset.query.filter_by(user_id=self.id, token=token, used=False).first()
        if reset and reset.is_valid():
            return reset
        return None

    def is_suspended(self):
        """Check if user is currently suspended"""
        if not self.is_active:
            # Check if it's a timed suspension that has expired
            if self.suspended_until and datetime.utcnow() >= self.suspended_until:
                # Auto-unsuspend if suspension period has ended
                self.unsuspend()
                return False
            return True
        return False

    def suspend(self, reason, duration=None, suspended_by_user=None):
        """Suspend the user for a specified duration or indefinitely
        
        Args:
            reason: Reason for suspension
            duration: Can be either:
                     - Number of hours (int/float)
                     - datetime object for until when suspended
                     - None for indefinite suspension
            suspended_by_user: User ID of admin performing suspension
        """
        self.is_active = False
        self.suspension_reason = reason
        self.suspended_at = datetime.utcnow()
        
        if duration is not None:
            if isinstance(duration, (int, float)):
                # Duration in hours
                self.suspended_until = self.suspended_at + timedelta(hours=duration)
            elif isinstance(duration, datetime):
                # Specific datetime
                self.suspended_until = duration
            else:
                # Invalid duration type, treat as indefinite
                self.suspended_until = None
        else:
            self.suspended_until = None  # Indefinite suspension
            
        if suspended_by_user:
            self.suspended_by = suspended_by_user
        
        return True

    def unsuspend(self, unsuspended_by_user=None):
        """Remove suspension from the user
        
        Args:
            unsuspended_by_user: User ID of admin removing suspension
        """
        if not self.is_suspended():
            return False
        
        self.is_active = True
        self.suspension_reason = None
        self.suspended_at = None
        self.suspended_until = None
        self.suspended_by = None
        
        return True

    def get_suspension_status(self):
        """Get detailed suspension status information"""
        if not self.is_suspended():
            return {
                'is_suspended': False,
                'reason': None,
                'suspended_at': None,
                'suspended_until': None,
                'suspended_by': None,
                'time_remaining': None
            }
        
        time_remaining = None
        if self.suspended_until:
            remaining = self.suspended_until - datetime.utcnow()
            if remaining.total_seconds() > 0:
                days = remaining.days
                hours, remainder = divmod(remaining.seconds, 3600)
                minutes = remainder // 60
                time_remaining = {
                    'days': days,
                    'hours': hours,
                    'minutes': minutes,
                    'total_hours': remaining.total_seconds() / 3600
                }
        
        suspended_by_user = None
        if self.suspended_by:
            suspended_by_user = User.query.get(self.suspended_by)
        
        return {
            'is_suspended': True,
            'reason': self.suspension_reason,
            'suspended_at': self.suspended_at,
            'suspended_until': self.suspended_until,
            'suspended_by': suspended_by_user,
            'time_remaining': time_remaining
        }
class BloodRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blood_type = db.Column(db.String(5), nullable=False)
    units_needed = db.Column(db.Integer, nullable=False, default=1)
    urgency = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    hospital = db.Column(db.String(200))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    required_by = db.Column(db.DateTime)

    # Relationships
    requester = db.relationship('User', backref='blood_requests')

class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blood_type = db.Column(db.String(5), nullable=False)
    donation_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    units = db.Column(db.Integer, nullable=False, default=1)
    center = db.Column(db.String(200))
    status = db.Column(db.String(20), default='pending')  # 'pending', 'completed', 'cancelled'
    notes = db.Column(db.Text)

    # Relationships
    donor = db.relationship('User', backref='donations')

class DonorVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    submission_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'approved', 'rejected'
    id_document_filename = db.Column(db.String(200))
    medical_certificate_filename = db.Column(db.String(200))
    address_proof_filename = db.Column(db.String(200))
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    review_date = db.Column(db.DateTime)
    review_notes = db.Column(db.Text)

    # Health questionnaire responses stored as JSON
    questionnaire_responses = db.Column(db.Text)  # Stored as JSON

    # Relationships
    donor = db.relationship('User', foreign_keys=[donor_id], backref='verifications')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id])

class PasswordReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)

    # Relationship
    user = db.relationship('User', backref='password_resets')

    def __init__(self, user_id, expires_in=24):
        """
        Initialize a new password reset token

        Args:
            user_id: The ID of the user requesting the password reset
            expires_in: Hours until the token expires (default: 24)
        """
        self.user_id = user_id
        self.token = secrets.token_urlsafe(64)
        self.created_at = datetime.utcnow()
        self.expires_at = self.created_at + timedelta(hours=expires_in)
        self.used = False

    def is_valid(self):
        """Check if the token is valid (not expired and not used)"""
        return not self.used and datetime.utcnow() < self.expires_at

    def invalidate(self):
        """Mark the token as used"""
        self.used = True

class AdminActionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    admin = db.relationship('User', foreign_keys=[admin_id])
    target_user = db.relationship('User', foreign_keys=[target_user_id])
class Testimonial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(100), nullable=False)  # e.g., "Donor", "Recipient"
    content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ImpactStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)  # e.g., "Lives Saved"
    count = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'info', 'success', 'warning', 'danger'
    link = db.Column(db.String(200))  # Optional link for the notification
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    user = db.relationship('User', backref='notifications')

    @staticmethod
    def create_notification(user_id, title, message, type='info', link=None):
        """Helper method to create a new notification"""
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            link=link
        )
        db.session.add(notification)
        db.session.commit()
        return notification


# Add this to your models.py file

class DonationProgram(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(200), nullable=False)
    address = db.Column(db.Text, nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    max_donors = db.Column(db.Integer, default=50)
    current_donors = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='upcoming')  # 'upcoming', 'ongoing', 'completed', 'cancelled'
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)

    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by])
    registrations = db.relationship('ProgramRegistration', backref='program', lazy='dynamic')

    def get_registration_count(self):
        """Get the number of donors registered for this program"""
        return ProgramRegistration.query.filter_by(program_id=self.id).count()

    def is_registered(self, user_id):
        """Check if a user is registered for this program"""
        return ProgramRegistration.query.filter_by(
            program_id=self.id,
            donor_id=user_id
        ).first() is not None

    def has_space_available(self):
        """Check if the program has space for more donors"""
        return self.get_registration_count() < self.max_donors

    def update_donor_count(self):
        """Update the current donor count"""
        self.current_donors = self.get_registration_count()


class ProgramRegistration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('donation_program.id'), nullable=False)
    donor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='registered')  # 'registered', 'checked_in', 'donated', 'no_show', 'cancelled'
    notes = db.Column(db.Text)

    # Relationships
    donor = db.relationship('User', backref='program_registrations')

    # Make sure each donor can only register once for each program
    __table_args__ = (db.UniqueConstraint('program_id', 'donor_id', name='unique_program_registration'),)


class BloodInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blood_type = db.Column(db.String(5), nullable=False)
    units = db.Column(db.Integer, nullable=False, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Threshold levels for alerts
    critical_level = db.Column(db.Integer, default=10)
    low_level = db.Column(db.Integer, default=30)

    @classmethod
    def get_inventory_status(cls):
        """Get the status of all blood types in inventory"""
        inventory = cls.query.all()

        result = {}
        for item in inventory:
            if item.units <= item.critical_level:
                status = 'critical'
            elif item.units <= item.low_level:
                status = 'low'
            else:
                status = 'normal'

            result[item.blood_type] = {
                'units': item.units,
                'status': status,
                'critical_level': item.critical_level,
                'low_level': item.low_level,
                'last_updated': item.last_updated
            }

        return result

    @classmethod
    def update_inventory(cls, blood_type, units_change):
        """Update inventory for a specific blood type"""
        inventory_item = cls.query.filter_by(blood_type=blood_type).first()

        if not inventory_item:
            inventory_item = cls(blood_type=blood_type, units=0)
            db.session.add(inventory_item)

        # Update units (don't allow negative values)
        inventory_item.units = max(0, inventory_item.units + units_change)

        # Check if alert is needed
        alert_needed = False
        if inventory_item.units <= inventory_item.critical_level:
            alert_needed = 'critical'
        elif inventory_item.units <= inventory_item.low_level:
            alert_needed = 'low'

        db.session.commit()

        return inventory_item, alert_needed