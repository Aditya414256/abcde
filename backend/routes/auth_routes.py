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
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

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
