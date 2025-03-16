import os
import json
import logging
import re
from datetime import datetime, timedelta
from flask import Flask, abort, jsonify, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import qrcode
import io
import base64

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Initialize Flask app first
app = Flask(__name__)

# Then configure the app
app.secret_key = os.environ.get("SESSION_SECRET", "dev_key_123")
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://postgres:Ss%40071424@localhost:5432/bloodbridge"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# File upload configuration
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'pdf'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload directory if it doesn't exist
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'id_documents'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'medical_certificates'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'address_proofs'), exist_ok=True)

# Import these after initializing app
from extensions import db
from models import User, BloodRequest, Donation, DonorVerification, Testimonial, ImpactStat, Notification
from utils import admin_required, calculate_blood_compatibility, donor_required, log_admin_action, receiver_required, format_verification_status, calculate_next_donation_date, validate_password_complexity

# Initialize SQLAlchemy
db.init_app(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helper Functions
def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_file(file, subfolder):
    """Save file to upload folder and return filename"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add timestamp to filename to make it unique
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"{timestamp}_{filename}"
        
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, filename)
        file.save(upload_path)
        return filename
    return None

# Context processor for common variables
@app.context_processor
def inject_common_variables():
    context = {'now': datetime.utcnow()}
    
    # If user is logged in as admin, inject admin dashboard data
    if current_user.is_authenticated and current_user.role == 'admin':
        # Get counts for admin dashboard
        context['pending_verifications_count'] = DonorVerification.query.filter_by(status='pending').count()
        context['pending_requests_count'] = BloodRequest.query.filter_by(status='pending').count()
        context['pending_donations_count'] = Donation.query.filter_by(status='pending').count()
        
        # Get recent verifications for admin dashboard
        context['recent_verifications'] = DonorVerification.query.order_by(
            DonorVerification.submission_date.desc()
        ).limit(5).all()
    
    # Add format_verification_status function to templates
    context['format_verification_status'] = format_verification_status
    
    return context

# Routes
@app.route('/')
def index():
    # Get active testimonials
    testimonials = Testimonial.query.filter_by(is_active=True).order_by(Testimonial.created_at.desc()).limit(2).all()
    
    # Get active impact statistics
    impact_stats = ImpactStat.query.filter_by(is_active=True).all()
    
    return render_template('index.html', testimonials=testimonials, impact_stats=impact_stats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            if user.totp_enabled:
                # Store user ID in session for 2FA verification
                session['pending_user_id'] = user.id
                return redirect(url_for('verify_2fa'))
            login_user(user)
            return redirect(get_dashboard_route(user.role))
        flash('Invalid email or password', 'danger')
    return render_template('login.html')

@app.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    if 'pending_user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['pending_user_id'])
    if not user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        token = request.form.get('token')
        if user.verify_totp(token):
            login_user(user)
            session.pop('pending_user_id', None)
            return redirect(get_dashboard_route(user.role))
        flash('Invalid 2FA code', 'danger')

    return render_template('verify_2fa.html')

@app.route('/setup-2fa', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    if not current_user.totp_secret:
        current_user.generate_totp_secret()
        db.session.commit()

    if request.method == 'POST':
        token = request.form.get('token')
        if current_user.verify_totp(token):
            current_user.totp_enabled = True
            db.session.commit()
            flash('Two-factor authentication has been enabled', 'success')
            return redirect(url_for('profile'))
        flash('Invalid 2FA code', 'danger')

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(current_user.get_totp_uri())
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert QR code to base64 for displaying in template
    buffered = io.BytesIO()
    img.save(buffered)
    qr_code = base64.b64encode(buffered.getvalue()).decode()

    return render_template('setup_2fa.html', 
                         qr_code=f"data:image/png;base64,{qr_code}",
                         secret=current_user.totp_secret)

@app.route('/disable-2fa', methods=['POST'])
@login_required
def disable_2fa():
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.session.commit()
    flash('Two-factor authentication has been disabled', 'success')
    return redirect(url_for('profile'))

@app.route('/verify-donor', methods=['GET', 'POST'])
@login_required
@donor_required
def verify_donor():
    """Page for donors to submit verification documents"""
    # Check if user already has a pending or approved verification
    existing_verification = DonorVerification.query.filter(
        DonorVerification.donor_id == current_user.id, 
        DonorVerification.status.in_(['pending', 'approved'])
    ).first()
    
    if existing_verification and existing_verification.status == 'approved':
        flash('You are already verified!', 'info')
        return redirect(url_for('donor_dashboard'))
    
    if existing_verification and existing_verification.status == 'pending':
        flash('Your verification is still being reviewed.', 'info')
        return redirect(url_for('verification_status'))
    
    if request.method == 'POST':
        try:
            # Handle file uploads
            id_document = request.files.get('id_document')
            medical_certificate = request.files.get('medical_certificate')
            address_proof = request.files.get('address_proof')
            
            id_filename = save_file(id_document, 'id_documents') if id_document else None
            medical_filename = save_file(medical_certificate, 'medical_certificates') if medical_certificate else None
            address_filename = save_file(address_proof, 'address_proofs') if address_proof else None
            
            # Capture questionnaire responses
            questionnaire_data = {
                'recent_illness': request.form.get('recent_illness'),
                'medication': request.form.get('medication'),
                'last_donation': request.form.get('last_donation'),
                'has_allergies': request.form.get('has_allergies'),
                'allergies_details': request.form.get('allergies_details'),
                'blood_transfusion': request.form.get('blood_transfusion'),
                'recent_surgery': request.form.get('recent_surgery'),
                'chronic_conditions': request.form.get('chronic_conditions'),
                'travel_history': request.form.get('travel_history'),
                'consented': request.form.get('consent') == 'on'
            }
            
            # Create verification record
            verification = DonorVerification(
                donor_id=current_user.id,
                status='pending',
                id_document_filename=id_filename,
                medical_certificate_filename=medical_filename,
                address_proof_filename=address_filename,
                questionnaire_responses=json.dumps(questionnaire_data)
            )
            
            # Update user verification status
            current_user.verification_status = 'pending'
            
            db.session.add(verification)
            
            # Notify all admins about new verification
            admins = User.query.filter_by(role='admin').all()
            for admin in admins:
                notification_handlers['admin_verification'](
                    admin.id,
                    f"{current_user.first_name} {current_user.last_name}"
                )
            
            db.session.commit()
            flash('Your verification documents have been submitted and will be reviewed shortly.', 'success')
            return redirect(url_for('verification_status'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Verification submission error: {str(e)}")
            flash('An error occurred while submitting your verification. Please try again.', 'danger')
    
    return render_template('verify_donor.html')

@app.route('/verification-status')
@login_required
@donor_required
def verification_status():
    """Page for donors to check their verification status"""
    verification = DonorVerification.query.filter_by(donor_id=current_user.id).order_by(DonorVerification.submission_date.desc()).first()
    
    if not verification:
        flash('You have not submitted any verification documents yet.', 'info')
        return redirect(url_for('verify_donor'))
    
    return render_template('verification_status.html', verification=verification)

@app.route('/admin/verifications')
@login_required
@admin_required
def admin_verifications():
    """Admin page to view all pending verifications"""
    status_filter = request.args.get('status', 'pending')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    if status_filter == 'all':
        verifications = DonorVerification.query.order_by(DonorVerification.submission_date.desc())
    else:
        verifications = DonorVerification.query.filter_by(status=status_filter).order_by(DonorVerification.submission_date.desc())
    
    pagination = verifications.paginate(page=page, per_page=per_page)
    
    return render_template('admin_verifications.html', pagination=pagination, status_filter=status_filter)

@app.route('/admin/review-verification/<int:verification_id>', methods=['POST'])
@login_required
@admin_required
def review_verification(verification_id):
    try:
        verification = DonorVerification.query.get_or_404(verification_id)
        action = request.form.get('action')
        notes = request.form.get('notes')
        
        if action == 'approve':
            verification.status = 'approved'
            verification.donor.verification_status = 'approved'
            verification.donor.is_verified = True
            
            # Notify donor of approval
            notification_handlers['donor_verification_result'](
                verification.donor_id,
                'approved'
            )
            
        elif action == 'reject':
            verification.status = 'rejected'
            verification.donor.verification_status = 'rejected'
            verification.donor.is_verified = False
            
            # Notify donor of rejection
            notification_handlers['donor_verification_result'](
                verification.donor_id,
                'rejected'
            )
        
        verification.reviewer_id = current_user.id
        verification.review_date = datetime.utcnow()
        verification.review_notes = notes
        
        db.session.commit()
        flash(f'Verification has been {verification.status}.', 'success')
        return redirect(url_for('admin_verifications'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Verification review error: {str(e)}")
        flash('An error occurred while reviewing the verification. Please try again.', 'danger')
        return redirect(url_for('review_verification', verification_id=verification_id))
    
@app.route('/view-document/<document_type>/<filename>')
@login_required
def view_document(document_type, filename):
    """Route to view uploaded documents"""
    # Security check: make sure only admins or the document owner can view documents
    if document_type not in ['id_documents', 'medical_certificates', 'address_proofs']:
        abort(404)
    
    # Find which verification this document belongs to
    verification = None
    if document_type == 'id_documents':
        verification = DonorVerification.query.filter_by(id_document_filename=filename).first()
    elif document_type == 'medical_certificates':
        verification = DonorVerification.query.filter_by(medical_certificate_filename=filename).first()
    elif document_type == 'address_proofs':
        verification = DonorVerification.query.filter_by(address_proof_filename=filename).first()
    
    if not verification:
        abort(404)
    
    # Check if current user is authorized to view this document
    if current_user.role != 'admin' and verification.donor_id != current_user.id:
        abort(403)
    
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], document_type), filename)

@app.route('/donate', methods=['GET', 'POST'])
@login_required
def donate():
    if current_user.role != 'donor':
        flash('Only donors can access this page.', 'warning')
        return redirect(url_for('index'))
    
    # Check if donor is verified
    if not current_user.is_verified:
        flash('You need to be verified before you can donate blood. Please complete the verification process.', 'warning')
        return redirect(url_for('verify_donor'))
    
    # Check eligibility based on last donation date
    can_donate, message = current_user.can_donate()
    if not can_donate:
        flash(message, 'warning')
        return redirect(url_for('donor_dashboard'))

    if request.method == 'POST':
        try:
            donation = Donation(
                donor_id=current_user.id,
                blood_type=current_user.blood_type,
                units=int(request.form['units']),
                center=request.form['center'],
                notes=request.form.get('notes', ''),
                status='pending'  # Start with pending status
            )
            db.session.add(donation)
            
            # Update user's donation dates
            current_user.last_donation_date = datetime.utcnow()
            current_user.next_eligible_date = calculate_next_donation_date(current_user.last_donation_date)
            
            db.session.commit()
            flash('Donation recorded successfully! It will be verified by the blood bank.', 'success')
            return redirect(url_for('donor_dashboard'))
        except Exception as e:
            logging.error(f"Donation recording error: {str(e)}")
            flash('An error occurred while recording the donation. Please try again.', 'danger')
    return render_template('donate.html')

def get_dashboard_route(role):
    return {
        'admin': url_for('admin_dashboard'),
        'donor': url_for('donor_dashboard'),
        'receiver': url_for('receiver_dashboard')
    }.get(role, url_for('index'))

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    blood_requests = BloodRequest.query.order_by(BloodRequest.created_at.desc()).limit(5).all()
    donations = Donation.query.order_by(Donation.donation_date.desc()).limit(5).all()
    
    # Get recent verifications
    recent_verifications = DonorVerification.query.order_by(
        DonorVerification.submission_date.desc()
    ).limit(5).all()
    
    return render_template(
        'admin_dashboard.html',
        blood_requests=blood_requests,
        donations=donations,
        recent_verifications=recent_verifications
    )

@app.route('/donor')
@login_required
def donor_dashboard():
    if current_user.role != 'donor':
        return redirect(url_for('index'))
    donations = Donation.query.filter_by(donor_id=current_user.id).order_by(Donation.donation_date.desc()).all()
    return render_template('donor_dashboard.html', donations=donations)

@app.route('/receiver')
@login_required
def receiver_dashboard():
    if current_user.role != 'receiver':
        return redirect(url_for('index'))
    requests = BloodRequest.query.filter_by(requester_id=current_user.id).order_by(BloodRequest.created_at.desc()).all()
    return render_template('receiver_dashboard.html', requests=requests)

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/request-blood', methods=['GET', 'POST'])
@login_required
def request_blood():
    if request.method == 'POST':
        try:
            blood_type = request.form['blood_type']
            urgency = request.form['urgency']
            
            # Create blood request
            blood_request = BloodRequest(
                requester_id=current_user.id,
                blood_type=blood_type,
                units_needed=int(request.form['units']),
                urgency=urgency,
                hospital=request.form['hospital'],
                notes=request.form.get('notes', ''),
                required_by=datetime.strptime(request.form['required_by'], '%Y-%m-%d') if request.form.get('required_by') else None
            )
            db.session.add(blood_request)
            
            # Notify matching donors
            notification_handlers['matching_donors'](
                blood_request.id,
                blood_type,
                urgency
            )
            
            # Notify admins
            notification_handlers['admin_blood_request'](
                blood_type,
                urgency
            )
            
            db.session.commit()
            flash('Blood request created successfully!', 'success')
            return redirect(url_for('receiver_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Blood request creation error: {str(e)}")
            flash('An error occurred while creating the request. Please try again.', 'danger')
    
    return render_template('request_blood.html')

@app.route('/blood-requests')
@login_required
def blood_requests():
    if current_user.role == 'admin':
        requests = BloodRequest.query.order_by(BloodRequest.created_at.desc()).all()
    elif current_user.role == 'receiver':
        requests = BloodRequest.query.filter_by(requester_id=current_user.id).order_by(BloodRequest.created_at.desc()).all()
    else:
        # For donors, show compatible requests based on their blood type
        compatible_types = calculate_blood_compatibility(current_user.blood_type)
        requests = BloodRequest.query.filter(BloodRequest.blood_type.in_(compatible_types)).order_by(BloodRequest.created_at.desc()).all()

    return render_template('blood_requests.html', requests=requests)

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Here we'll just flash a message for now
        flash('Thank you for your message. We will get back to you soon!', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/teams')
def teams():
    return render_template('teams.html')

@app.route('/donation-tips')
def donation_tips():
    return render_template('donation_tips.html')

@app.route('/blood-banks')
def blood_banks():
    return render_template('blood_banks.html')

@app.route('/help-support')
def help_support():
    return render_template('help_support.html')

@app.route('/eligibility-check')
def eligibility_check():
    return render_template('eligibility_check.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            # Basic user information
            user = User(
                email=request.form['email'],
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                password_hash=generate_password_hash(request.form['password']),
                role=request.form.get('role', 'donor'),
                # Additional profile information
                blood_type=request.form.get('blood_type'),
                phone=request.form.get('phone'),
                address=request.form.get('address'),
                gender=request.form.get('gender'),
                date_of_birth=datetime.strptime(request.form.get('date_of_birth', ''), '%Y-%m-%d') if request.form.get('date_of_birth') else None
            )

            if User.query.filter_by(email=user.email).first():
                flash('Email already registered', 'danger')
                return render_template('register.html')

            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Registration successful!', 'success')
            return redirect(get_dashboard_route(user.role))
        except Exception as e:
            logging.error(f"Registration error: {str(e)}")
            flash('An error occurred during registration. Please try again.', 'danger')
            return render_template('register.html')
    return render_template('register.html')

# New routes for testimonials and impact stats management
@app.route('/admin/testimonials', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_testimonials():
    """Admin page to manage testimonials"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            new_testimonial = Testimonial(
                name=request.form.get('name'),
                role=request.form.get('role'),
                content=request.form.get('content'),
                is_active=request.form.get('is_active') == 'on'
            )
            db.session.add(new_testimonial)
            db.session.commit()
            flash('Testimonial added successfully', 'success')
            
        elif action == 'edit':
            testimonial_id = request.form.get('testimonial_id')
            testimonial = Testimonial.query.get_or_404(testimonial_id)
            testimonial.name = request.form.get('name')
            testimonial.role = request.form.get('role')
            testimonial.content = request.form.get('content')
            testimonial.is_active = request.form.get('is_active') == 'on'
            db.session.commit()
            flash('Testimonial updated successfully', 'success')
            
        elif action == 'delete':
            testimonial_id = request.form.get('testimonial_id')
            testimonial = Testimonial.query.get_or_404(testimonial_id)
            db.session.delete(testimonial)
            db.session.commit()
            flash('Testimonial deleted successfully', 'success')
    
    testimonials = Testimonial.query.order_by(Testimonial.created_at.desc()).all()
    return render_template('admin_testimonials.html', testimonials=testimonials)

@app.route('/admin/impact-stats', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_impact_stats():
    """Admin page to manage impact statistics"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            new_stat = ImpactStat(
                title=request.form.get('title'),
                count=int(request.form.get('count')),
                is_active=request.form.get('is_active') == 'on'
            )
            db.session.add(new_stat)
            db.session.commit()
            flash('Impact statistic added successfully', 'success')
            
        elif action == 'edit':
            stat_id = request.form.get('stat_id')
            stat = ImpactStat.query.get_or_404(stat_id)
            stat.title = request.form.get('title')
            stat.count = int(request.form.get('count'))
            stat.is_active = request.form.get('is_active') == 'on'
            db.session.commit()
            flash('Impact statistic updated successfully', 'success')
            
        elif action == 'delete':
            stat_id = request.form.get('stat_id')
            stat = ImpactStat.query.get_or_404(stat_id)
            db.session.delete(stat)
            db.session.commit()
            flash('Impact statistic deleted successfully', 'success')
    
    impact_stats = ImpactStat.query.all()
    return render_template('admin_impact_stats.html', impact_stats=impact_stats)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle forgot password requests"""
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Please enter your email address.', 'danger')
            return redirect(url_for('forgot_password'))
        
        user = User.query.filter_by(email=email).first()
        
        # Even if the user doesn't exist, don't reveal this information
        # to prevent email enumeration attacks
        if user:
            token = user.generate_password_reset_token()
            
            # In production, use the actual host
            reset_url = request.host_url.rstrip('/') + url_for('reset_password')
            
            if send_password_reset_email(user, token, reset_url):
                flash('Password reset instructions have been sent to your email.', 'success')
            else:
                flash('There was an error sending the password reset email. Please try again later.', 'danger')
        else:
            # Log this but don't tell the user (to prevent email enumeration)
            logging.info(f"Password reset requested for non-existent email: {email}")
            # Still show success message to prevent email enumeration
            flash('If your email is registered, you will receive password reset instructions.', 'success')
        
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Handle password reset with token verification"""
    token = request.args.get('token') or request.form.get('token')
    
    if not token:
        flash('Invalid or missing reset token.', 'danger')
        return redirect(url_for('login'))
    
    # Find the reset token in the database
    reset = PasswordReset.query.filter_by(token=token, used=False).first()
    
    if not reset or not reset.is_valid():
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('login'))
    
    user = User.query.get(reset.user_id)
    
    if not user:
        flash('User account not found.', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('reset_password.html', token=token)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)
        
        # Update the user's password
        user.password_hash = generate_password_hash(password)
        
        # Invalidate the token
        reset.invalidate()
        
        db.session.commit()
        
        flash('Your password has been reset successfully. You can now log in with your new password.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', token=token)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """Admin page to view and manage users"""
    role_filter = request.args.get('role', 'all')
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    query = User.query
    
    if role_filter != 'all':
        query = query.filter_by(role=role_filter)
    
    if search_query:
        query = query.filter(
            db.or_(
                User.email.ilike(f'%{search_query}%'),
                User.first_name.ilike(f'%{search_query}%'),
                User.last_name.ilike(f'%{search_query}%')
            )
        )
    
    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page)
    
    return render_template('admin_users.html', 
                          pagination=pagination, 
                          role_filter=role_filter,
                          search_query=search_query)

@app.route('/admin/reset-user-password/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_reset_password(user_id):
    """Allow admins to reset user passwords"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_reset = request.form.get('confirm_reset')
        
        # Validate confirmation
        if not confirm_reset:
            flash('You must confirm the password reset.', 'danger')
            return render_template('admin_reset_password.html', user=user)
        
        # Validate password complexity
        is_valid, error_message = validate_password_complexity(password)
        if not is_valid:
            flash(error_message, 'danger')
            return render_template('admin_reset_password.html', user=user)
        
        try:
            # Update the user's password
            old_hash = user.password_hash  # Keep for logging
            user.password_hash = generate_password_hash(password)
            db.session.commit()
            
            # Log the password reset action
            log_admin_action(
                admin_user=current_user, 
                action_type='password_reset', 
                target_user=user,
                details={
                    'method': 'admin_reset',
                    'old_hash_changed': old_hash != user.password_hash
                }
            )
            
            flash(f'Password for {user.email} has been reset successfully.', 'success')
            return redirect(url_for('admin_users'))
        
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error resetting password for user {user.email}: {str(e)}")
            flash('An error occurred while resetting the password.', 'danger')
    
    return render_template('admin_reset_password.html', user=user)

# Email utility function (should be in email_utils.py, but included here for completeness)
def send_password_reset_email(user, token, reset_url):
    """
    Send a password reset email to a user
    
    Args:
        user: User object
        token: Password reset token
        reset_url: Base URL for password reset (e.g., https://example.com/reset-password)
    
    Returns:
        bool: True if the email was sent successfully
    """
    reset_link = f"{reset_url}?token={token}"
    
    subject = "Reset Your BloodBridge Password"
    
    # HTML version
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="text-align: center; margin-bottom: 20px;">
                <h2 style="color: #dc3545;">BloodBridge</h2>
            </div>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px;">
                <h3>Hello {user.first_name},</h3>
                
                <p>We received a request to reset your password for your BloodBridge account.</p>
                
                <p>To reset your password, please click the button below:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" style="background-color: #dc3545; color: white; padding: 12px 25px; text-decoration: none; border-radius: 4px; font-weight: bold;">Reset Password</a>
                </div>
                
                <p>If you didn't request this password reset, you can ignore this email and your password will remain unchanged.</p>
                
                <p>This password reset link will expire in 24 hours.</p>
                
                <p>Thank you,<br>
                The BloodBridge Team</p>
            </div>
            
            <div style="margin-top: 20px; font-size: 12px; color: #6c757d; text-align: center;">
                <p>If you're having trouble clicking the button, copy and paste the URL below into your web browser:</p>
                <p style="word-break: break-all;">{reset_link}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text version
    text_content = f"""
    Hello {user.first_name},
    
    We received a request to reset your password for your BloodBridge account.
    
    To reset your password, please visit the link below:
    
    {reset_link}
    
    If you didn't request this password reset, you can ignore this email and your password will remain unchanged.
    
    This password reset link will expire in 24 hours.
    
    Thank you,
    The BloodBridge Team
    """
    
    # This is just a placeholder since the actual implementation is in email_utils.py
    # In practice, you would use something like:
    # return send_email(user.email, subject, html_content, text_content)
    return True

from datetime import datetime, timedelta
import humanize

# Add this template filter
@app.template_filter('timeago')
def timeago_filter(date):
    """Convert datetime to "time ago" text"""
    now = datetime.utcnow()
    return humanize.naturaltime(now - date)

# Add this to your context processor
@app.context_processor
def inject_notifications():
    """Inject notifications into all templates"""
    if current_user.is_authenticated:
        # Get recent notifications for dropdown (limited to 5)
        recent_notifications = Notification.query.filter_by(user_id=current_user.id)\
            .order_by(Notification.created_at.desc())\
            .limit(5).all()
        
        # Get unread notifications
        unread_notifications = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).all()
        
        return {
            'recent_notifications': recent_notifications,  # For dropdown
            'unread_notifications': unread_notifications  # For badge
        }
    return {}

@app.route('/notifications')
@login_required
def notifications():
    """View all notifications"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc())\
        .paginate(page=page, per_page=per_page)
    
    return render_template('notifications.html', notifications=notifications)

@app.route('/notifications/mark-read', methods=['POST'])
@login_required
def mark_all_read():
    """Mark all notifications as read"""
    try:
        Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).update({'is_read': True})
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/notifications/<int:notification_id>/mark-read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a specific notification as read"""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        abort(403)
    
    try:
        notification.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# Example function to create notifications for different events
def create_notification_for_event(event_type, user_id, **kwargs):
    """Create notifications for different events"""
    notifications = {
        'verification_approved': {
            'title': 'Verification Approved',
            'message': 'Your donor verification has been approved! You can now start donating blood.',
            'type': 'success',
            'link': url_for('verification_status')
        },
        'verification_rejected': {
            'title': 'Verification Rejected',
            'message': 'Your donor verification was rejected. Please review the feedback and submit again.',
            'type': 'danger',
            'link': url_for('verification_status')
        },
        'blood_request_match': {
            'title': 'Blood Request Match',
            'message': f"Your blood type matches a {kwargs.get('urgency', 'new')} request.",
            'type': 'info',
            'link': url_for('blood_requests')
        },
        'donation_reminder': {
            'title': 'Ready to Donate',
            'message': 'You are now eligible to donate blood again!',
            'type': 'success',
            'link': url_for('donate')
        },
        'request_fulfilled': {
            'title': 'Blood Request Fulfilled',
            'message': 'Your blood request has been fulfilled!',
            'type': 'success',
            'link': url_for('blood_requests')
        }
    }
    
    if event_type in notifications:
        notification_data = notifications[event_type]
        Notification.create_notification(
            user_id=user_id,
            title=notification_data['title'],
            message=notification_data['message'],
            type=notification_data['type'],
            link=notification_data['link']
        )

@app.route('/test-notifications')
@login_required
def test_notifications():
    """Test page for notifications"""
    recent_notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc())\
        .limit(5).all()
    return render_template('test_notifications.html', recent_notifications=recent_notifications)

@app.route('/create-test-notification', methods=['POST'])
@login_required
def create_test_notification():
    """Create a test notification"""
    notification_type = request.json.get('type', 'info')
    
    # Create different messages based on type
    notifications = {
        'info': {
            'title': 'Info Notification',
            'message': 'This is a test info notification.',
            'link': url_for('notifications')
        },
        'success': {
            'title': 'Success Notification',
            'message': 'Your action was completed successfully!',
            'link': url_for('notifications')
        },
        'warning': {
            'title': 'Warning Notification',
            'message': 'Please be aware of this important notice.',
            'link': url_for('notifications')
        },
        'danger': {
            'title': 'Urgent Notification',
            'message': 'Immediate attention required!',
            'link': url_for('notifications')
        }
    }
    
    notif_data = notifications.get(notification_type, notifications['info'])
    
    # Create the notification
    notification = Notification.create_notification(
        user_id=current_user.id,
        title=notif_data['title'],
        message=notif_data['message'],
        type=notification_type,
        link=notif_data['link']
    )
    
    # Get unread count for badge update
    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return jsonify({
        'success': True,
        'notification': {
            'title': notification.title,
            'message': notification.message,
            'type': notification.type
        },
        'unread_count': unread_count
    })
def create_notification_handlers():
    """Set up notification handlers for specific events"""
    
    def notify_admin_new_verification(admin_id, donor_name):
        """Notify admin about new verification request"""
        Notification.create_notification(
            user_id=admin_id,
            title="New Verification Request",
            message=f"New donor verification request from {donor_name}",
            type="info",
            link=url_for('admin_verifications')
        )
    
    def notify_donor_verification_result(donor_id, status):
        """Notify donor about verification result"""
        if status == 'approved':
            Notification.create_notification(
                user_id=donor_id,
                title="Verification Approved",
                message="Your donor verification has been approved! You can now donate blood.",
                type="success",
                link=url_for('verification_status')
            )
        elif status == 'rejected':
            Notification.create_notification(
                user_id=donor_id,
                title="Verification Rejected",
                message="Your verification was rejected. Please check the feedback and submit again.",
                type="danger",
                link=url_for('verification_status')
            )
    
    def notify_matching_donors(request_id, blood_type, urgency):
        """Notify donors with matching blood type about new request"""
        # Find all verified donors with matching blood type
        matching_donors = User.query.filter_by(
            role='donor',
            blood_type=blood_type,
            is_verified=True
        ).all()
        
        # Notify each matching donor
        for donor in matching_donors:
            Notification.create_notification(
                user_id=donor.id,
                title="Blood Request Match",
                message=f"New {urgency} blood request matching your blood type ({blood_type})",
                type="info" if urgency == 'normal' else urgency,
                link=url_for('blood_requests')
            )
    
    def notify_admins_blood_request(blood_type, urgency):
        """Notify all admins about new blood request"""
        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            Notification.create_notification(
                user_id=admin.id,
                title="New Blood Request",
                message=f"New {urgency} blood request for {blood_type}",
                type="info" if urgency == 'normal' else urgency,
                link=url_for('blood_requests')
            )
    
    return {
        'admin_verification': notify_admin_new_verification,
        'donor_verification_result': notify_donor_verification_result,
        'matching_donors': notify_matching_donors,
        'admin_blood_request': notify_admins_blood_request
    }

# Initialize notification handlers
notification_handlers = create_notification_handlers()
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)