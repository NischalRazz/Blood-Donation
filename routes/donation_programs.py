# Create a new file called routes/donation_programs.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from models import DonationProgram, ProgramRegistration, BloodInventory, User, Notification, Donation
from extensions import db
from datetime import datetime, timedelta
from utils import admin_required, donor_required, log_admin_action, calculate_next_donation_date
import csv
import io

donation_programs = Blueprint('donation_programs', __name__)

# Public-facing program listing
@donation_programs.route('/donation-programs')
def list_programs():
    """Public page listing upcoming donation programs"""
    # Get upcoming and ongoing programs
    upcoming_programs = DonationProgram.query.filter(
        DonationProgram.date >= datetime.utcnow().date(),
        DonationProgram.is_public == True,
        DonationProgram.status.in_(['upcoming', 'ongoing'])
    ).order_by(DonationProgram.date, DonationProgram.start_time).all()
    
    # Check if user is registered for any programs
    user_registrations = {}
    if current_user.is_authenticated and current_user.role == 'donor':
        for program in upcoming_programs:
            user_registrations[program.id] = program.is_registered(current_user.id)
    
    return render_template(
        'donation_programs.html',
        upcoming_programs=upcoming_programs,
        user_registrations=user_registrations
    )

# Admin-only routes for managing programs
@donation_programs.route('/admin/donation-programs')
@login_required
@admin_required
def admin_programs():
    """Admin view for managing donation programs"""
    status_filter = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Build query based on filters
    query = DonationProgram.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    # Order by date (newest first)
    query = query.order_by(DonationProgram.date.desc(), DonationProgram.start_time.desc())
    
    # Paginate results
    programs = query.paginate(page=page, per_page=per_page)
    
    return render_template(
        'admin_donation_programs.html',
        programs=programs,
        status_filter=status_filter,
        DonationProgram=DonationProgram
    )

@donation_programs.route('/admin/donation-programs/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_program():
    """Create a new donation program"""
    if request.method == 'POST':
        try:
            # Parse form data
            program = DonationProgram(
                title=request.form['title'],
                description=request.form.get('description'),
                location=request.form['location'],
                address=request.form['address'],
                date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
                start_time=datetime.strptime(request.form['start_time'], '%H:%M').time(),
                end_time=datetime.strptime(request.form['end_time'], '%H:%M').time(),
                max_donors=int(request.form['max_donors']),
                status='upcoming',
                created_by=current_user.id,
                is_public=request.form.get('is_public') == 'on'
            )
            
            db.session.add(program)
            
            # Log admin action
            log_admin_action(
                admin_user=current_user,
                action_type='donation_program_created',
                details={
                    'title': program.title,
                    'location': program.location,
                    'date': str(program.date),
                    'max_donors': program.max_donors
                }
            )
            
            db.session.commit()
            
            # If program is public, notify eligible donors
            if program.is_public:
                # Find eligible donors who are verified and available
                eligible_donors = User.query.filter_by(
                    role='donor',
                    is_verified=True,
                    is_available=True
                ).all()
                
                for donor in eligible_donors:
                    # Skip donors who aren't eligible to donate on that date
                    if donor.next_eligible_date and donor.next_eligible_date.date() > program.date:
                        continue
                        
                    # Create notification
                    Notification.create_notification(
                        user_id=donor.id,
                        title="New Blood Donation Event",
                        message=f"New blood donation event: {program.title} on {program.date.strftime('%b %d, %Y')} at {program.location}",
                        type="info",
                        link=url_for('donation_programs.list_programs')
                    )
            
            flash('Donation program created successfully!', 'success')
            return redirect(url_for('donation_programs.admin_programs'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating donation program: {str(e)}', 'danger')
    
    return render_template('donation_program_form.html', now=datetime.utcnow())

@donation_programs.route('/admin/donation-programs/<int:program_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_program(program_id):
    """Edit an existing donation program"""
    program = DonationProgram.query.get_or_404(program_id)
    
    if request.method == 'POST':
        try:
            program.title = request.form['title']
            program.description = request.form.get('description')
            program.location = request.form['location']
            program.address = request.form['address']
            program.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            program.start_time = datetime.strptime(request.form['start_time'], '%H:%M').time()
            program.end_time = datetime.strptime(request.form['end_time'], '%H:%M').time()
            program.max_donors = int(request.form['max_donors'])
            program.is_public = request.form.get('is_public') == 'on'
            
            # Log admin action
            log_admin_action(
                admin_user=current_user,
                action_type='donation_program_updated',
                details={
                    'program_id': program.id,
                    'title': program.title,
                    'changes': {
                        'location': program.location,
                        'date': str(program.date),
                        'max_donors': program.max_donors
                    }
                }
            )
            
            db.session.commit()
            flash('Donation program updated successfully!', 'success')
            return redirect(url_for('donation_programs.admin_programs'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating donation program: {str(e)}', 'danger')
    
    return render_template('donation_program_form.html', program=program, now=datetime.utcnow())

@donation_programs.route('/admin/donation-programs/<int:program_id>/registrations')
@login_required
@admin_required
def view_program_registrations(program_id):
    """View all registrations for a program"""
    program = DonationProgram.query.get_or_404(program_id)
    status_filter = request.args.get('status', 'all')
    
    # Apply status filter if requested
    if status_filter != 'all':
        registrations = ProgramRegistration.query.filter_by(
            program_id=program_id, 
            status=status_filter
        ).all()
    else:
        registrations = ProgramRegistration.query.filter_by(
            program_id=program_id
        ).all()
    
    # For export functionality
    if request.args.get('format') == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Donor ID', 'Name', 'Email', 'Blood Type', 'Registration Date', 'Status'])
        
        # Write data
        for reg in registrations:
            writer.writerow([
                reg.donor_id,
                reg.donor.get_full_name(),
                reg.donor.email,
                reg.donor.blood_type,
                reg.registration_date.strftime('%Y-%m-%d %H:%M'),
                reg.status
            ])
        
        # Return CSV file
        output.seek(0)
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=registrations_{program_id}.csv"}
        )
    
    return render_template(
        'program_registrations.html',
        program=program,
        registrations=registrations
    )

@donation_programs.route('/admin/donation-programs/<int:program_id>/update-status/<status>', methods=['POST'])
@login_required
@admin_required
def update_program_status(program_id, status):
    """Update the status of a donation program"""
    if status not in ['upcoming', 'ongoing', 'completed', 'cancelled']:
        flash('Invalid status', 'danger')
        return redirect(url_for('donation_programs.admin_programs'))
    
    program = DonationProgram.query.get_or_404(program_id)
    
    try:
        old_status = program.status
        program.status = status
        
        # Log the admin action
        log_admin_action(
            admin_user=current_user,
            action_type=f'donation_program_status_update',
            details={
                'program_id': program.id,
                'old_status': old_status,
                'new_status': status
            }
        )
        
        # If program is completed, process all registrations accordingly
        if status == 'completed':
            registrations = ProgramRegistration.query.filter_by(
                program_id=program.id, 
                status='checked_in'
            ).all()
            
            for reg in registrations:
                # Mark as donated unless otherwise specified
                if reg.status == 'checked_in':
                    reg.status = 'donated'
        
        # If program is cancelled, notify registered donors
        if status == 'cancelled':
            registrations = ProgramRegistration.query.filter_by(program_id=program.id).all()
            
            for reg in registrations:
                Notification.create_notification(
                    user_id=reg.donor_id,
                    title="Donation Program Cancelled",
                    message=f"The donation program '{program.title}' scheduled for {program.date.strftime('%b %d, %Y')} has been cancelled.",
                    type="warning",
                    link=url_for('donation_programs.list_programs')
                )
                
                # Update registration status
                reg.status = 'cancelled'
        
        db.session.commit()
        flash(f'Program status updated to {status}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating program status: {str(e)}', 'danger')
    
    return redirect(url_for('donation_programs.admin_programs'))

@donation_programs.route('/donation-programs/<int:program_id>/register', methods=['POST'])
@login_required
@donor_required
def register_for_program(program_id):
    """Register a donor for a donation program"""
    program = DonationProgram.query.get_or_404(program_id)
    
    # Check if the program is still accepting registrations
    if program.status != 'upcoming' or not program.has_space_available():
        flash('This program is no longer accepting registrations', 'warning')
        return redirect(url_for('donation_programs.list_programs'))
    
    # Check if donor is already registered
    if program.is_registered(current_user.id):
        flash('You are already registered for this program', 'info')
        return redirect(url_for('donation_programs.list_programs'))
    
    # Check if donor is eligible to donate
    can_donate, message = current_user.can_donate()
    if not can_donate:
        flash(message, 'warning')
        return redirect(url_for('donation_programs.list_programs'))
    
    try:
        # Create registration
        registration = ProgramRegistration(
            program_id=program_id,
            donor_id=current_user.id,
            status='registered'
        )
        
        db.session.add(registration)
        
        # Update donor count
        program.update_donor_count()
        
        db.session.commit()
        
        # Create confirmation notification
        Notification.create_notification(
            user_id=current_user.id,
            title="Registration Confirmed",
            message=f"You are registered for '{program.title}' on {program.date.strftime('%b %d, %Y')}. Please arrive between {program.start_time.strftime('%I:%M %p')} and {program.end_time.strftime('%I:%M %p')}.",
            type="success",
            link=url_for('donation_programs.view_registration', program_id=program_id)
        )
        
        flash('Registration successful!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error registering for the program: {str(e)}', 'danger')
    
    return redirect(url_for('donation_programs.list_programs'))

@donation_programs.route('/donation-programs/<int:program_id>/cancel-registration', methods=['POST'])
@login_required
@donor_required
def cancel_registration(program_id):
    """Cancel a donor's registration for a program"""
    program = DonationProgram.query.get_or_404(program_id)
    
    # Only allow cancellation for upcoming programs
    if program.status != 'upcoming':
        flash('Registration can only be cancelled for upcoming programs', 'warning')
        return redirect(url_for('donation_programs.list_programs'))
    
    registration = ProgramRegistration.query.filter_by(
        program_id=program_id,
        donor_id=current_user.id
    ).first()
    
    if not registration:
        flash('You are not registered for this program', 'warning')
        return redirect(url_for('donation_programs.list_programs'))
    
    try:
        # Update registration status
        registration.status = 'cancelled'
        
        # Update donor count
        program.update_donor_count()
        
        db.session.commit()
        flash('Registration cancelled successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error cancelling registration: {str(e)}', 'danger')
    
    return redirect(url_for('donation_programs.list_programs'))

@donation_programs.route('/donation-programs/<int:program_id>/view')
@login_required
@donor_required
def view_registration(program_id):
    """View donor's registration details for a program"""
    program = DonationProgram.query.get_or_404(program_id)
    
    registration = ProgramRegistration.query.filter_by(
        program_id=program_id,
        donor_id=current_user.id
    ).first()
    
    if not registration:
        flash('You are not registered for this program', 'warning')
        return redirect(url_for('donation_programs.list_programs'))
    
    return render_template(
        'view_registration.html',
        program=program,
        registration=registration
    )

# Admin check-in process
@donation_programs.route('/admin/donation-programs/<int:program_id>/check-in/<int:donor_id>', methods=['POST'])
@login_required
@admin_required
def check_in_donor(program_id, donor_id):
    """Mark a donor as checked in for a program"""
    registration = ProgramRegistration.query.filter_by(
        program_id=program_id,
        donor_id=donor_id
    ).first_or_404()
    
    try:
        registration.status = 'checked_in'
        db.session.commit()
        flash('Donor checked in successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error checking in donor: {str(e)}', 'danger')
    
    return redirect(url_for('donation_programs.view_program_registrations', program_id=program_id))

@donation_programs.route('/admin/donation-programs/<int:program_id>/mark-no-show/<int:donor_id>', methods=['POST'])
@login_required
@admin_required
def mark_donor_no_show(program_id, donor_id):
    """Mark a donor as no-show for a program"""
    registration = ProgramRegistration.query.filter_by(
        program_id=program_id,
        donor_id=donor_id
    ).first_or_404()
    
    try:
        registration.status = 'no_show'
        db.session.commit()
        flash('Donor marked as no-show', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating donor status: {str(e)}', 'danger')
    
    return redirect(url_for('donation_programs.view_program_registrations', program_id=program_id))

@donation_programs.route('/admin/donation-programs/<int:program_id>/mark-donated/<int:donor_id>', methods=['POST'])
@login_required
@admin_required
def mark_donor_donated(program_id, donor_id):
    """Mark a donor as having donated for a program"""
    registration = ProgramRegistration.query.filter_by(
        program_id=program_id,
        donor_id=donor_id
    ).first_or_404()
    
    try:
        registration.status = 'donated'
        db.session.commit()
        flash('Donor marked as donated', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating donor status: {str(e)}', 'danger')
    
    return redirect(url_for('donation_programs.view_program_registrations', program_id=program_id))

@donation_programs.route('/admin/donation-programs/<int:program_id>/cancel-registration/<int:donor_id>', methods=['POST'])
@login_required
@admin_required
def cancel_donor_registration(program_id, donor_id):
    """Cancel a donor's registration (admin action)"""
    registration = ProgramRegistration.query.filter_by(
        program_id=program_id,
        donor_id=donor_id
    ).first_or_404()
    
    try:
        registration.status = 'cancelled'
        
        # Update program's donor count
        program = DonationProgram.query.get(program_id)
        program.update_donor_count()
        
        db.session.commit()
        flash('Registration cancelled successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error cancelling registration: {str(e)}', 'danger')
    
    return redirect(url_for('donation_programs.view_program_registrations', program_id=program_id))

@donation_programs.route('/admin/registration/<int:registration_id>/add-notes', methods=['POST'])
@login_required
@admin_required
def add_registration_notes(registration_id):
    """Add notes to a registration"""
    registration = ProgramRegistration.query.get_or_404(registration_id)
    
    try:
        registration.notes = request.form.get('notes')
        db.session.commit()
        flash('Notes saved successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error saving notes: {str(e)}', 'danger')
    
    return redirect(url_for('donation_programs.view_program_registrations', program_id=registration.program_id))

@donation_programs.route('/admin/registration/<int:registration_id>/record-donation', methods=['POST'])
@login_required
@admin_required
def record_donation(registration_id):
    """Record a donation from a program registration"""
    registration = ProgramRegistration.query.get_or_404(registration_id)
    donor = User.query.get(registration.donor_id)
    
    try:
        units = int(request.form.get('units', 1))
        
        # Create a donation record
        from models import Donation
        donation = Donation(
            donor_id=registration.donor_id,
            blood_type=donor.blood_type,
            units=units,
            center=registration.program.location,
            notes=f"Donated at program: {registration.program.title}",
            status='completed',
            donation_date=datetime.utcnow()
        )
        db.session.add(donation)
        
        # Update donor information
        donor.last_donation_date = datetime.utcnow()
        donor.next_eligible_date = calculate_next_donation_date(donor.last_donation_date)
        
        # Update blood inventory
        inventory_item, alert_level = BloodInventory.update_inventory(donor.blood_type, units)
        
        # Create alerts if needed
        if alert_level:
            # Alert all admins
            admins = User.query.filter_by(role='admin').all()
            
            alert_title = f"{'CRITICAL' if alert_level == 'critical' else 'LOW'} Blood Stock"
            alert_message = f"{donor.blood_type} blood stock is {'critically low' if alert_level == 'critical' else 'running low'} ({inventory_item.units} units available)"
            alert_type = 'danger' if alert_level == 'critical' else 'warning'
            
            for admin in admins:
                Notification.create_notification(
                    user_id=admin.id,
                    title=alert_title,
                    message=alert_message,
                    type=alert_type,
                    link=url_for('donation_programs.blood_inventory')
                )
        
        db.session.commit()
        flash(f'Donation of {units} unit(s) recorded successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording donation: {str(e)}', 'danger')
    
    return redirect(url_for('donation_programs.view_program_registrations', program_id=registration.program_id))

# Blood Inventory Management
@donation_programs.route('/admin/blood-inventory')
@login_required
@admin_required
def blood_inventory():
    """View and manage blood inventory"""
    inventory = BloodInventory.query.all()
    
    # Get alert counts for dashboard
    critical_count = sum(1 for item in inventory if item.units <= item.critical_level)
    low_count = sum(1 for item in inventory if item.critical_level < item.units <= item.low_level)
    
    # Get donation data for charts
    donations_by_type = {}
    for blood_type in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
        donations_by_type[blood_type] = Donation.query.filter_by(
            blood_type=blood_type,
            status='completed'
        ).count()
    
    return render_template(
        'blood_inventory.html',
        inventory=inventory,
        critical_count=critical_count,
        low_count=low_count,
        donations_by_type=donations_by_type
    )

@donation_programs.route('/admin/blood-inventory/update', methods=['POST'])
@login_required
@admin_required
def update_inventory():
    """Manually update blood inventory"""
    blood_type = request.form.get('blood_type')
    units = int(request.form.get('units', 0))
    
    if not blood_type or blood_type not in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
        flash('Invalid blood type', 'danger')
        return redirect(url_for('donation_programs.blood_inventory'))
    
    try:
        # Update inventory and check for alerts
        inventory_item, alert_level = BloodInventory.update_inventory(blood_type, units)
        
        # Log admin action
        log_admin_action(
            admin_user=current_user,
            action_type='inventory_update',
            details={
                'blood_type': blood_type,
                'units_change': units,
                'new_total': inventory_item.units
            }
        )
        
        # Create alerts if needed
        if alert_level:
            # Alert all admins
            admins = User.query.filter_by(role='admin').all()
            
            alert_title = f"{'CRITICAL' if alert_level == 'critical' else 'LOW'} Blood Stock"
            alert_message = f"{blood_type} blood stock is {'critically low' if alert_level == 'critical' else 'running low'} ({inventory_item.units} units available)"
            alert_type = 'danger' if alert_level == 'critical' else 'warning'
            
            for admin in admins:
                Notification.create_notification(
                    user_id=admin.id,
                    title=alert_title,
                    message=alert_message,
                    type=alert_type,
                    link=url_for('donation_programs.blood_inventory')
                )
        
        flash(f'Blood inventory updated successfully', 'success')
        if alert_level:
            flash(f'Alert: {blood_type} blood stock is {alert_level}!', alert_level)
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating inventory: {str(e)}', 'danger')
    
    return redirect(url_for('donation_programs.blood_inventory'))

@donation_programs.route('/admin/blood-inventory/thresholds', methods=['POST'])
@login_required
@admin_required
def update_thresholds():
    """Update alert thresholds for blood inventory"""
    critical_level = int(request.form.get('critical_level', 10))
    low_level = int(request.form.get('low_level', 30))
    
    try:
        # Update all inventory items with new thresholds
        inventory_items = BloodInventory.query.all()
        for item in inventory_items:
            item.critical_level = critical_level
            item.low_level = low_level
        
        # Log admin action
        log_admin_action(
            admin_user=current_user,
            action_type='threshold_update',
            details={
                'critical_level': critical_level,
                'low_level': low_level
            }
        )
        
        db.session.commit()
        flash('Alert thresholds updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating thresholds: {str(e)}', 'danger')
    
    return redirect(url_for('donation_programs.blood_inventory'))
