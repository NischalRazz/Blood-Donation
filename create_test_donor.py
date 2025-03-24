from app import app, db
from models import User, DonationProgram
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

def create_test_donor():
    """Create a test donor account"""
    with app.app_context():
        # Check if test donor already exists
        donor = User.query.filter_by(email='testdonor@example.com').first()
        if donor:
            print("Test donor already exists")
            return donor
        
        # Create new donor
        donor = User(
            email='testdonor@example.com',
            password_hash=generate_password_hash('password123'),
            first_name='Test',
            last_name='Donor',
            role='donor',
            blood_type='O+',
            phone='1234567890',
            address='123 Test Street',
            gender='Male',
            date_of_birth=datetime(1990, 1, 1),
            is_verified=True,
            verification_status='approved',
            is_available=True
        )
        
        db.session.add(donor)
        db.session.commit()
        print("Created test donor account")
        return donor

def create_test_program():
    """Create a test donation program"""
    with app.app_context():
        # Check if test program already exists
        program = DonationProgram.query.filter_by(title='Test Donation Drive').first()
        if program:
            print("Test program already exists")
            return program
            
        # Create new program
        tomorrow = datetime.utcnow().date() + timedelta(days=1)
        program = DonationProgram(
            title='Test Donation Drive',
            description='A test blood donation program',
            location='Test Hospital',
            address='456 Hospital Road',
            date=tomorrow,
            start_time=datetime.strptime('09:00', '%H:%M').time(),
            end_time=datetime.strptime('17:00', '%H:%M').time(),
            max_donors=50,
            status='upcoming',
            created_by=1,  # Assuming admin user has ID 1
            is_public=True
        )
        
        db.session.add(program)
        db.session.commit()
        print("Created test donation program")
        return program

if __name__ == "__main__":
    donor = create_test_donor()
    program = create_test_program()
    print("\nTest data created successfully!")
    print(f"Donor email: testdonor@example.com")
    print(f"Password: password123")
