"""
Migration script to add suspension fields to User model
Run this to add suspension functionality to existing database
"""

from app import app, db
from sqlalchemy import text
import logging

def add_suspension_fields():
    """Add suspension fields to the User table"""
    with app.app_context():
        try:
            # Check if columns already exist
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('user')]
            
            migrations_executed = []
            
            # Add is_active column if it doesn't exist
            if 'is_active' not in columns:
                db.session.execute(text('ALTER TABLE "user" ADD COLUMN is_active BOOLEAN DEFAULT TRUE'))
                migrations_executed.append("Added is_active column")
                
            # Add suspension_reason column if it doesn't exist
            if 'suspension_reason' not in columns:
                db.session.execute(text('ALTER TABLE "user" ADD COLUMN suspension_reason TEXT'))
                migrations_executed.append("Added suspension_reason column")
                
            # Add suspended_at column if it doesn't exist
            if 'suspended_at' not in columns:
                db.session.execute(text('ALTER TABLE "user" ADD COLUMN suspended_at TIMESTAMP'))
                migrations_executed.append("Added suspended_at column")
                
            # Add suspended_until column if it doesn't exist
            if 'suspended_until' not in columns:
                db.session.execute(text('ALTER TABLE "user" ADD COLUMN suspended_until TIMESTAMP'))
                migrations_executed.append("Added suspended_until column")
                
            # Add suspended_by column if it doesn't exist
            if 'suspended_by' not in columns:
                db.session.execute(text('ALTER TABLE "user" ADD COLUMN suspended_by INTEGER REFERENCES "user" (id)'))
                migrations_executed.append("Added suspended_by column")
                
            # Commit all changes
            db.session.commit()
            
            if migrations_executed:
                print("Migration completed successfully!")
                for migration in migrations_executed:
                    print(f"  - {migration}")
            else:
                print("No migrations needed - all suspension fields already exist")
                
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Migration failed: {str(e)}")
            logging.error(f"Migration error: {str(e)}")
            return False

if __name__ == '__main__':
    print("Running suspension fields migration...")
    success = add_suspension_fields()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")
