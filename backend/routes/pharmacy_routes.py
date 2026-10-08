from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from backend.services.pharmacy_service import PharmacyService
from backend.services.inventory_service import InventoryService
from backend.services.prescription_service import PrescriptionService
from backend.models import Pharmacy, Order, PharmacyInventory, Medicine
from backend.database import db

pharmacy_bp = Blueprint('pharmacy', __name__, url_prefix='/api')

@pharmacy_bp.route('/pharmacies', methods=['GET'])
def list_verified_pharmacies():
    """
    Public customer locator: lists ONLY active and admin-verified pharmacies.
    Optionally calculates distance if user provides latitude and longitude.
    """
    lat = request.args.get('latitude', type=float)
    lon = request.args.get('longitude', type=float)
    pharmacies = PharmacyService.list_verified_pharmacies(user_lat=lat, user_lon=lon)
    return jsonify({
        'count': len(pharmacies),
        'pharmacies': pharmacies
    }), 200


@pharmacy_bp.route('/pharmacies/<int:pharmacy_id>', methods=['GET'])
def get_pharmacy_details(pharmacy_id):
    pharmacy = PharmacyService.get_pharmacy_by_id(pharmacy_id)
    if not pharmacy:
        return jsonify({'error': 'Pharmacy not found.'}), 404

    data = pharmacy.to_dict()
    inventory = InventoryService.get_pharmacy_inventory(pharmacy_id)
    data['inventory'] = inventory
    return jsonify({'pharmacy': data}), 200


@pharmacy_bp.route('/pharmacy/orders', methods=['GET'])
def get_pharmacy_orders():
    """
    Pharmacy Portal: returns all orders placed for the logged-in user's pharmacy.
    """
    if not current_user.is_authenticated or current_user.role != 'pharmacy':
        return jsonify({'error': 'Unauthorized. Pharmacy login required.'}), 403

    pharmacy = PharmacyService.get_pharmacy_by_owner_id(current_user.id)
    if not pharmacy:
        return jsonify({'error': 'No pharmacy associated with this account.'}), 404

    orders = Order.query.filter_by(pharmacy_id=pharmacy.id).order_by(Order.created_at.desc()).all()
    return jsonify({
        'pharmacy': pharmacy.to_dict(),
        'orders': [o.to_dict() for o in orders]
    }), 200


@pharmacy_bp.route('/pharmacy/inventory', methods=['GET', 'POST', 'PUT'])
def manage_inventory():
    """
    Pharmacy Portal: View and manage inventory.
    """
    if not current_user.is_authenticated or current_user.role != 'pharmacy':
        return jsonify({'error': 'Unauthorized. Pharmacy login required.'}), 403

    pharmacy = PharmacyService.get_pharmacy_by_owner_id(current_user.id)
    if not pharmacy:
        return jsonify({'error': 'No pharmacy associated with this account.'}), 404

    if request.method == 'GET':
        items = InventoryService.get_pharmacy_inventory(pharmacy.id)
        return jsonify({'inventory': items}), 200

    data = request.get_json() or {}
    medicine_id = data.get('medicine_id')
    quantity = data.get('quantity')
    price = data.get('price')
    batch_number = data.get('batch_number')
    expiry_date = data.get('expiry_date')
    notes = data.get('notes')

    if not medicine_id or quantity is None or price is None:
        return jsonify({'error': 'medicine_id, quantity, and price are required.'}), 400

    try:
        inv = InventoryService.update_inventory(
            pharmacy_id=pharmacy.id,
            medicine_id=medicine_id,
            quantity=int(quantity),
            price=float(price),
            batch_number=batch_number,
            expiry_date=expiry_date,
            notes=notes
        )
        return jsonify({
            'message': 'Inventory updated successfully.',
            'item': inv.to_dict()
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@pharmacy_bp.route('/pharmacy/prescriptions/<int:prescription_id>/review', methods=['POST'])
def review_prescription(prescription_id):
    """
    Manual human review of uploaded prescription by pharmacy owner.
    """
    if not current_user.is_authenticated or current_user.role != 'pharmacy':
        return jsonify({'error': 'Unauthorized.'}), 403

    data = request.get_json() or {}
    status = data.get('status') # 'APPROVED' or 'REJECTED'
    notes = data.get('notes')

    try:
        prescription = PrescriptionService.review_prescription(
            prescription_id=prescription_id,
            reviewer_user=current_user,
            status=status,
            notes=notes
        )
        return jsonify({
            'message': f'Prescription {status.lower()} successfully.',
            'prescription': prescription.to_dict()
        }), 200
    except (ValueError, PermissionError) as e:
        return jsonify({'error': str(e)}), 400
