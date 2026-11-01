from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from backend.models import User
from backend.services.pharmacy_service import PharmacyService
from backend.database import db

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register/customer', methods=['POST'])
def register_customer():
    data = request.get_json() or {}
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')
    phone = data.get('phone', '').strip()

    if not full_name or not email or not password:
        return jsonify({'error': 'Full name, email, and password are required.'}), 400

    if password != confirm_password:
        return jsonify({'error': 'Passwords do not match.'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters.'}), 400

    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify({'error': 'An account with this email already exists.'}), 409

    user = User(
        email=email,
        full_name=full_name,
        phone=phone,
        role='customer'
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user)
    return jsonify({
        'message': 'Account created successfully.',
        'user': user.to_dict(),
        'redirect_url': 'HomePage.html'
    }), 201


@auth_bp.route('/register-pharmacy', methods=['POST'])
def register_pharmacy():
    data = request.get_json() or {}
    owner_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    pharmacy_name = data.get('pharmacy_name', '').strip()
    license_number = data.get('license_number', '').strip()
    pharmacy_phone = data.get('pharmacy_phone', '').strip()
    pharmacy_email = data.get('pharmacy_email', '').strip()
    address = data.get('address', '').strip()
    city = data.get('city', '').strip()
    state = data.get('state', '').strip()
    pincode = data.get('pincode', '').strip()

    supports_pickup = bool(data.get('supports_pickup', True))
    supports_delivery = bool(data.get('supports_delivery', False))

    if not all([owner_name, email, password, pharmacy_name, license_number, address, city, state, pincode]):
        return jsonify({'error': 'All required fields marked with * must be filled.'}), 400

    if password != confirm_password:
        return jsonify({'error': 'Passwords do not match.'}), 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'error': 'An account with this email already exists.'}), 409

    try:
        user = User(
            email=email,
            full_name=owner_name,
            phone=pharmacy_phone,
            role='pharmacy'
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # Seed with coordinates based on known city or default
        lat = data.get('latitude', 12.9716) # Default Bangalore or provided
        lon = data.get('longitude', 77.5946)

        pharmacy = PharmacyService.register_pharmacy(
            owner_id=user.id,
            name=pharmacy_name,
            license_number=license_number,
            phone=pharmacy_phone,
            email=pharmacy_email or email,
            address=address,
            city=city,
            state=state,
            pincode=pincode,
            supports_pickup=supports_pickup,
            supports_delivery=supports_delivery,
            latitude=lat,
            longitude=lon
        )
        db.session.commit()

        login_user(user)
        return jsonify({
            'message': 'Pharmacy registered successfully. Your account is pending admin verification.',
            'user': user.to_dict(),
            'pharmacy': pharmacy.to_dict(),
            'redirect_url': 'pharmacy-dashboard.html'
        }), 201

    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Registration failed. Please check your information.'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or request.form or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or 

    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid email or password.'}), 401

    login_user(user)

    # Role-based redirection per Requirement #20:
    # Customer -> Customer Home (HomePage.html)
    # Pharmacy -> Pharmacy Dashboard (pharmacy-dashboard.html)
    # Admin -> Admin Dashboard (admin-dashboard.html)
    redirect_map = {
        'customer': 'HomePage.html',
        'pharmacy': 'pharmacy-dashboard.html',
        'admin': 'admin-dashboard.html'
    }
    redirect_url = redirect_map.get(user.role, 'HomePage.html')

    return jsonify({
        'message': 'Login successful.',
        'user': user.to_dict(),
        'redirect_url': redirect_url
    }), 200


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    logout_user()
    return jsonify({'message': 'Logged out successfully.'}), 200


@auth_bp.route('/current-user', methods=['GET'])
def get_current_user():
    if current_user.is_authenticated:
        data = current_user.to_dict()
        if current_user.role == 'pharmacy':
            pharmacy = PharmacyService.get_pharmacy_by_owner_id(current_user.id)
            data['pharmacy'] = pharmacy.to_dict() if pharmacy else None
        return jsonify({'authenticated': True, 'user': data}), 200
    return jsonify({'authenticated': False, 'user': None}), 200


@auth_bp.route('/profile', methods=['PATCH', 'PUT'])
def update_profile():
    """
    Customer, pharmacy owner, or admin updates their own profile.
    Updatable fields: full_name, phone.
    Password change requires current_password + new_password + confirm_password.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Login required.'}), 401

    data = request.get_json() or {}

    full_name = data.get('full_name', '').strip()
    phone = data.get('phone', '').strip()
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    updated = False

    if full_name:
        current_user.full_name = full_name
        updated = True

    if phone is not None and phone != current_user.phone:
        current_user.phone = phone or None
        updated = True

    # Password change — only attempted when new_password is supplied
    if new_password:
        if not current_password:
            return jsonify({'error': 'Current password is required to set a new password.'}), 400
        if not current_user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect.'}), 400
        if len(new_password) < 6:
            return jsonify({'error': 'New password must be at least 6 characters.'}), 400
        if new_password != confirm_password:
            return jsonify({'error': 'New passwords do not match.'}), 400
        current_user.set_password(new_password)
        updated = True

    if not updated:
        return jsonify({'message': 'No changes made.', 'user': current_user.to_dict()}), 200

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to update profile.'}), 500

    return jsonify({
        'message': 'Profile updated successfully.',
        'user': current_user.to_dict(),
    }), 200
