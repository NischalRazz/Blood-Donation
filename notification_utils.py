# Create a new file: notification_utils.py

from models import Notification, User, db
from flask import url_for

def create_verification_notification(user_id, verification_status, verification_id=None):
    """Create a notification when verification status changes"""
    if verification_status == 'approved':
        title = "Verification Approved"
        message = "Your donor verification has been approved. You can now schedule blood donations."
        link = url_for('verification_status')
    elif verification_status == 'rejected':
        title = "Verification Rejected"
        message = "Your verification was not approved. Please check the feedback and submit new documents."
        link = url_for('verification_status')
    elif verification_status == 'pending':
        title = "Verification Submitted"
        message = "Your verification documents have been submitted. We'll review them soon."
        link = url_for('verification_status')
    else:
        return None

    return Notification.create(
        user_id=user_id,
        title=title,
        message=message,
        notification_type='verification',
        related_id=verification_id
    )

def create_donation_notification(user_id, donation_id, status):
    """Create a notification about donation status"""
    if status == 'pending':
        title = "Donation Recorded"
        message = "Your blood donation has been recorded. Thank you for saving lives!"
    elif status == 'completed':
        title = "Donation Confirmed"
        message = "Your blood donation has been confirmed. You've helped save up to 3 lives!"
    elif status == 'cancelled':
        title = "Donation Cancelled"
        message = "Your blood donation has been cancelled."
    else:
        return None
        
    return Notification.create(
        user_id=user_id,
        title=title,
        message=message,
        notification_type='donation',
        related_id=donation_id
    )

def create_blood_request_notification(request_id, blood_type):
    """Notify donors of matching blood type about a new request"""
    from models import User
    
    # Find donors with matching blood type
    matching_donors = User.query.filter_by(role='donor', blood_type=blood_type, is_verified=True).all()
    
    notifications = []
    for donor in matching_donors:
        notification = Notification.create(
            user_id=donor.id,
            title="Urgent Blood Needed",
            message=f"Someone needs {blood_type} blood. You're a match! Please check if you can help.",
            notification_type='request_match',
            related_id=request_id
        )
        notifications.append(notification)
        
    return notifications

def create_request_update_notification(requester_id, request_id, status):
    """Create a notification when a blood request status changes"""
    if status == 'fulfilled':
        title = "Request Fulfilled"
        message = "Your blood request has been fulfilled. The blood bank will contact you with further details."
    elif status == 'processing':
        title = "Request Processing"
        message = "We're processing your blood request. Donors are being notified."
    elif status == 'cancelled':
        title = "Request Cancelled"
        message = "Your blood request has been cancelled."
    else:
        return None
        
    return Notification.create(
        user_id=requester_id,
        title=title,
        message=message,
        notification_type='request_update',
        related_id=request_id
    )

def create_eligibility_notification(user_id):
    """Notify user when they become eligible to donate again"""
    return Notification.create(
        user_id=user_id,
        title="You Can Donate Again",
        message="Good news! You're now eligible to donate blood again. Schedule your next donation today!",
        notification_type='eligibility',
        related_id=None
    )

def admin_mass_notification(title, message, notification_type, user_role=None):
    """Create a notification for all users or users of a specific role"""
    if user_role:
        users = User.query.filter_by(role=user_role).all()
    else:
        users = User.query.all()
        
    notifications = []
    for user in users:
        notification = Notification.create(
            user_id=user.id,
            title=title,
            message=message,
            notification_type=notification_type
        )
        notifications.append(notification)
        
    return notifications