"""
Migration script to add suspension fields to User model
Run this with Flask-Migrate or manually
"""

from app import app, db
from flask_migrate import Migrate, upgrade

def add_suspension_fields():
    with app.app_context():
        # Check if columns already exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('user')]
        
        # Add columns if they don't exist
        if 'is_active' not in columns:
            db.engine.execute('ALTER TABLE "user" ADD COLUMN is_active BOOLEAN DEFAULT TRUE')
            print("Added is_active column")
            
        if 'suspension_reason' not in columns:
            db.engine.execute('ALTER TABLE "user" ADD COLUMN suspension_reason TEXT')
            print("Added suspension_reason column")
            
        if 'suspended_at' not in columns:
            db.engine.execute('ALTER TABLE "user" ADD COLUMN suspended_at TIMESTAMP')
            print("Added suspended_at column")
            
        if 'suspended_by' not in columns:
            db.engine.execute('ALTER TABLE "user" ADD COLUMN suspended_by INTEGER REFERENCES "user" (id)')
            print("Added suspended_by column")
            
        print("Migration completed successfully")

if __name__ == '__main__':
    add_suspension_fields()