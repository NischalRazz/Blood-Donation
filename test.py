from app import app, db
from sqlalchemy import text

with app.app_context():
    # Add the address column using text() for raw SQL
    sql = text("ALTER TABLE donation_program ADD COLUMN IF NOT EXISTS address TEXT")
    db.session.execute(sql)
    db.session.commit()
    print("Address column added successfully!")