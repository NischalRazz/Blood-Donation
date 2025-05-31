#!/bin/bash
# Blood Donation System - Linux/macOS Startup Script

echo "Starting Blood Donation System..."
echo

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment. Make sure Python 3 is installed."
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies."
    exit 1
fi

# Check if database exists, if not initialize it
if [ ! -f "blood_donation.db" ]; then
    echo "Initializing database..."
    python migrate.py
    if [ $? -ne 0 ]; then
        echo "Error: Database initialization failed."
        exit 1
    fi
    
    echo "Seeding initial data..."
    python seed_data.py
fi

# Create upload directories if they don't exist
mkdir -p static/uploads/id_documents
mkdir -p static/uploads/address_proofs

# Set permissions for upload directories
chmod -R 755 static/uploads

echo
echo "================================================="
echo "Blood Donation System is starting..."
echo
echo "Application will be available at:"
echo "http://localhost:5000"
echo
echo "Admin panel: http://localhost:5000/admin/login"
echo
echo "To create an admin account, press Ctrl+C to stop"
echo "and run: python create_admin.py"
echo "================================================="
echo

# Start the application
python app.py
