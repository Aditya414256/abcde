from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from backend.models import Pharmacy, User, Order, Medicine
from backend.services.pharmacy_service import PharmacyService
from backend.services.notification_service import NotificationService
from backend.database import db

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

def check_admin():
    if not current_user.is_authenticated or current_user.role != 'admin':
        return False
    return True

@admin_bp.route('/pharmacies', methods=['GET'])
def list_all_pharmacies():
    if not check_admin():
        return jsonify({'error': 'Admin authorization required.'}), 403

    status_filter = request.args.get('status')
    query = Pharmacy.query
    if status_filter:
        query = query.filter_by(verification_status=status_filter)

    pharmacies = query.order_by(Pharmacy.created_at.desc()).all()
    return jsonify({
        'pharmacies': [p.to_dict(include_owner=True) for p in pharmacies]
    }), 200


@admin_bp.route('/pharmacies/<int:pharmacy_id>/verify', methods=['POST'])
def verify_pharmacy(pharmacy_id):
    if not check_admin():
        return jsonify({'error': 'Admin authorization required.'}), 403

    data = request.get_json() or {}
    action = data.get('action') # 'approve' or 'reject'

    if action not in ['approve', 'reject']:
        return jsonify({'error': "Action must be 'approve' or 'reject'."}), 400

    new_status = 'APPROVED' if action == 'approve' else 'REJECTED'

    try:
        pharmacy = PharmacyService.verify_pharmacy(pharmacy_id, new_status)

        # Notify pharmacy owner
        title = "Pharmacy Verification Approved" if action == 'approve' else "Pharmacy Verification Rejected"
        msg = (f"Congratulations! Your pharmacy '{pharmacy.name}' has been verified and is now live on MediFind."
               if action == 'approve' else
               f"Your pharmacy registration for '{pharmacy.name}' was not approved. Please contact support or check license details.")

        NotificationService.create_notification(
            user_id=pharmacy.owner_id,
            title=title,
            message=msg
        )

        return jsonify({
            'message': f"Pharmacy successfully {new_status.lower()}.",
            'pharmacy': pharmacy.to_dict(include_owner=True)
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@admin_bp.route('/pharmacies/<int:pharmacy_id>/toggle-active', methods=['POST'])
def toggle_active(pharmacy_id):
    if not check_admin():
        return jsonify({'error': 'Admin authorization required.'}), 403

    pharmacy = Pharmacy.query.get(pharmacy_id)
    if not pharmacy:
        return jsonify({'error': 'Pharmacy not found.'}), 404

    pharmacy.is_active = not pharmacy.is_active
    db.session.commit()

    return jsonify({
        'message': f"Pharmacy is now {'active' if pharmacy.is_active else 'inactive'}.",
        'pharmacy': pharmacy.to_dict()
    }), 200


@admin_bp.route('/stats', methods=['GET'])
def get_stats():
    if not check_admin():
        return jsonify({'error': 'Admin authorization required.'}), 403

    total_users = User.query.count()
    total_pharmacies = Pharmacy.query.count()
    pending_pharmacies = Pharmacy.query.filter_by(verification_status='PENDING').count()
    verified_pharmacies = Pharmacy.query.filter_by(is_verified=True).count()
    total_orders = Order.query.count()
    total_medicines = Medicine.query.count()

    return jsonify({
        'stats': {
            'total_users': total_users,
            'total_pharmacies': total_pharmacies,
            'pending_verifications': pending_pharmacies,
            'verified_pharmacies': verified_pharmacies,
            'total_orders': total_orders,
            'total_medicines': total_medicines
        }
    }), 200
