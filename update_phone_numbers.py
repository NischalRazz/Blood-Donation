from app import app, db
from models import User
import random

def generate_phone_number():
    
    operators = ['984','974','976']
    operator = random.choice(operators)
    number = ''.join([str(random.randint(0, 9)) for _ in range(7)])
    return f"{operator}{number}"

def update_user_phone_numbers():
    with app.app_context():
        users = User.query.all()
        count = 0
        for user in users:
            user.phone = generate_phone_number()
            count += 1
        db.session.commit()
        print(f"Updated {count} users with phone numbers")

if __name__ == "__main__":
    update_user_phone_numbers()
