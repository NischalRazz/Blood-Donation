"""
Test script to verify notifications functionality
"""

from app import app, db
from models import Notification, User

def test_create_notification():
    """Test creating a notification"""
    with app.app_context():
        # Get the first user (for testing)
        user = User.query.first()
        if not user:
            print("No users found in database!")
            return
        
        try:
            # Create a test notification
            notification = Notification.create_notification(
                user_id=user.id,
                title="Test Notification",
                message="This is a test notification to verify the system is working.",
                type="info",
                link="/notifications"
            )
            
            print(f"✅ Test notification created successfully for user {user.email}!")
            
            # Verify we can retrieve it
            test_notif = Notification.query.get(notification.id)
            if test_notif:
                print("✅ Successfully retrieved notification from database!")
                
                # Clean up the test notification
                db.session.delete(test_notif)
                db.session.commit()
                print("✅ Test notification cleaned up!")
            
        except Exception as e:
            print(f"❌ Error during testing: {str(e)}")

if __name__ == "__main__":
    print("Testing notifications system...")
    test_create_notification()