"""
Migration script to add notifications table to the database
"""

from app import app, db
from models import Notification
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_notifications_table():
    """Create the notifications table"""
    with app.app_context():
        try:
            # Create the notifications table
            logger.info("Creating notifications table...")
            db.create_all()
            logger.info("Notifications table created successfully!")
            return True
        except Exception as e:
            logger.error(f"Error creating notifications table: {str(e)}")
            return False

if __name__ == "__main__":
    print("Adding notifications table to database...")
    if create_notifications_table():
        print("✅ Notifications table added successfully!")
    else:
        print("❌ Failed to add notifications table. Check the logs for details.")