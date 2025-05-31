#!/usr/bin/env python3
"""
Blood Donation System - Deployment Verification Script
Run this script after deployment to verify everything is working correctly.
"""

import os
import sys
import sqlite3
from datetime import datetime

def check_python_version():
    """Check if Python version is compatible"""
    print("Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python {version.major}.{version.minor} found. Python 3.8+ required.")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible")
    return True

def check_database():
    """Check if database exists and has required tables"""
    print("\nChecking database...")
    db_path = "blood_donation.db"
    
    if not os.path.exists(db_path):
        print("❌ Database not found. Run 'python migrate.py' to create it.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for key tables
        required_tables = ['users', 'blood_requests', 'donations', 'notifications', 'admin_action_logs']
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        missing_tables = [table for table in required_tables if table not in existing_tables]
        if missing_tables:
            print(f"❌ Missing tables: {', '.join(missing_tables)}")
            conn.close()
            return False
        
        # Check for suspension fields
        cursor.execute("PRAGMA table_info(users);")
        columns = [column[1] for column in cursor.fetchall()]
        suspension_fields = ['is_suspended', 'suspended_until', 'suspension_reason', 'suspended_by']
        missing_fields = [field for field in suspension_fields if field not in columns]
        
        if missing_fields:
            print(f"❌ Missing suspension fields in users table: {', '.join(missing_fields)}")
            conn.close()
            return False
        
        conn.close()
        print("✅ Database structure verified")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        return False

def check_directories():
    """Check if required directories exist"""
    print("\nChecking directories...")
    required_dirs = [
        "static/uploads/id_documents",
        "static/uploads/address_proofs",
        "templates",
        "static/css",
        "static/js"
    ]
    
    all_exist = True
    for directory in required_dirs:
        if os.path.exists(directory):
            print(f"✅ {directory}")
        else:
            print(f"❌ {directory} - Missing")
            all_exist = False
    
    return all_exist

def check_dependencies():
    """Check if required packages are installed"""
    print("\nChecking dependencies...")
    required_packages = [
        'flask', 'flask_sqlalchemy', 'flask_login', 'flask_wtf', 
        'werkzeug', 'wtforms', 'flask_mail'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - Not installed")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\nTo install missing packages, run:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_app_imports():
    """Check if the application can be imported without errors"""
    print("\nChecking application imports...")
    try:
        # Add current directory to path
        sys.path.insert(0, os.getcwd())
        
        # Test imports
        import models
        import app
        print("✅ Application imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {str(e)}")
        return False

def main():
    """Run all verification checks"""
    print("Blood Donation System - Deployment Verification")
    print("=" * 50)
    
    checks = [
        check_python_version,
        check_dependencies,
        check_database,
        check_directories,
        check_app_imports
    ]
    
    results = []
    for check in checks:
        result = check()
        results.append(result)
    
    print("\n" + "=" * 50)
    print("VERIFICATION SUMMARY")
    print("=" * 50)
    
    if all(results):
        print("🎉 All checks passed! Your Blood Donation System is ready to run.")
        print("\nTo start the application:")
        print("- Windows: Run 'start_windows.bat'")
        print("- Linux/macOS: Run 'bash start_unix.sh'")
        print("- Manual: Run 'python app.py'")
        print("\nTo create an admin account: python create_admin.py")
    else:
        print("❌ Some checks failed. Please fix the issues above before running the application.")
        failed_count = sum(1 for result in results if not result)
        print(f"\n{failed_count} out of {len(results)} checks failed.")
    
    print(f"\nVerification completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
