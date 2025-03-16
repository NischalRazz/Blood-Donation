"""
Seed script to populate initial testimonials and impact statistics.
Run this after setting up your database to have some initial data.
"""

from app import app, db
from models import Testimonial, ImpactStat

def seed_testimonials():
    """Create initial testimonials"""
    testimonials = [
        {
            "name": "Sarah Johnson",
            "role": "Regular Donor",
            "content": "I've been donating blood for years, but BloodBridge made the process so much easier. The reminders are helpful, and knowing my blood has directly saved lives is incredibly fulfilling."
        },
        {
            "name": "Michael Rodriguez",
            "role": "Recipient Family",
            "content": "When my son needed emergency blood transfusion after an accident, BloodBridge helped us find donors quickly. The response from the community was overwhelming. Forever grateful."
        },
        {
            "name": "Dr. Emily Chen",
            "role": "Medical Professional",
            "content": "As a doctor, I've seen firsthand how critical blood supplies are in emergency situations. BloodBridge has helped ensure our hospital never runs short of essential blood types."
        },
        {
            "name": "David Thompson",
            "role": "First-time Donor",
            "content": "I was nervous about donating blood for the first time, but the process was so streamlined and the staff were incredibly supportive. I'm now a regular donor thanks to BloodBridge!"
        }
    ]
    
    for data in testimonials:
        testimonial = Testimonial(
            name=data["name"],
            role=data["role"],
            content=data["content"],
            is_active=True
        )
        db.session.add(testimonial)
    
    db.session.commit()
    print(f"Created {len(testimonials)} testimonials")

def seed_impact_stats():
    """Create initial impact statistics"""
    stats = [
        {
            "title": "Donors Registered",
            "count": 5000
        },
        {
            "title": "Lives Saved",
            "count": 15000
        },
        {
            "title": "Blood Banks",
            "count": 200
        },
        {
            "title": "Successful Matches",
            "count": 1200
        }
    ]
    
    for data in stats:
        stat = ImpactStat(
            title=data["title"],
            count=data["count"],
            is_active=True
        )
        db.session.add(stat)
    
    db.session.commit()
    print(f"Created {len(stats)} impact statistics")

if __name__ == "__main__":
    with app.app_context():
        # Check if testimonials already exist
        existing_testimonials = Testimonial.query.count()
        if existing_testimonials == 0:
            seed_testimonials()
        else:
            print(f"Skipping testimonials seed: {existing_testimonials} testimonials already exist")
        
        # Check if impact stats already exist
        existing_stats = ImpactStat.query.count()
        if existing_stats == 0:
            seed_impact_stats()
        else:
            print(f"Skipping impact stats seed: {existing_stats} stats already exist")