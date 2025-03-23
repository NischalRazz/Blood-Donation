from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import os

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def init_app(app):
    """Initialize application extensions"""
    # Ensure upload directories exist and are writable
    uploads_path = os.path.join(app.root_path, 'static', 'uploads')
    upload_dirs = [
        os.path.join(uploads_path, 'id_documents'),
        os.path.join(uploads_path, 'medical_certificates'),
        os.path.join(uploads_path, 'address_proofs')
    ]
    
    for directory in upload_dirs:
        try:
            os.makedirs(directory, exist_ok=True)
            # Ensure the directory is readable and writable
            os.chmod(directory, 0o755)
        except Exception as e:
            app.logger.error(f"Error creating upload directory {directory}: {str(e)}")
