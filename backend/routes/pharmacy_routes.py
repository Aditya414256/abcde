import logging
import os
import uuid
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
from backend.services.pharmacy_service import PharmacyService
from backend.services.inventory_service import InventoryService
from backend.services.prescription_service import PrescriptionService
from backend.models import Pharmacy, Order, PharmacyInventory, Medicine
from backend.database import db
from backend.config import Config

logger = logging.getLogger(__name__)

# Allowed extensions for pharmacy verification documents (same as prescriptions)
_ALLOWED_DOC_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'webp'}

pharmacy_bp = Blueprint('pharmacy', __name__, url_prefix='/api')


@pharmacy_bp.route('/pharmacies', methods=['GET'])
def list_pharmacies():
    """
    Public pharmacy directory: lists ALL active pharmacies regardless of
    verification status. is_active and is_verified are distinct flags.
    Active pharmacies with pending verification or no inventory are still listed.
    Optionally calculates distance if user provides latitude and longitude.
    """
    lat = request.args.get('latitude', type=float)
    lon = request.args.get('longitude', type=float)
    pharmacies = PharmacyService.list_active_pharmacies(user_lat=lat, user_lon=lon)
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
    Approval / rejection is separate from order acceptance.
    """
    if not current_user.is_authenticated or current_user.role != 'pharmacy':
        return jsonify({'error': 'Unauthorized.'}), 403

    data = request.get_json() or {}
    status = data.get('status')  # 'APPROVED' or 'REJECTED'
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


@pharmacy_bp.route('/pharmacy/verification-doc', methods=['POST'])
def upload_verification_doc():
    """
    Pharmacy owner uploads their drug-license / registration document for admin review.
    The file is stored in protected local storage (not publicly served).
    Admin reviews the document during the verification workflow.
    """
    if not current_user.is_authenticated or current_user.role != 'pharmacy':
        return jsonify({'error': 'Pharmacy login required.'}), 403

    pharmacy = PharmacyService.get_pharmacy_by_owner_id(current_user.id)
    if not pharmacy:
        return jsonify({'error': 'No pharmacy associated with this account.'}), 404

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded.'}), 400

    file = request.files['file']
    if not file or not file.filename:
        return jsonify({'error': 'No file selected.'}), 400

    filename = secure_filename(file.filename)
    extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if extension not in _ALLOWED_DOC_EXTENSIONS:
        return jsonify({
            'error': f"Invalid file extension. Allowed: {', '.join(sorted(_ALLOWED_DOC_EXTENSIONS))}"
        }), 400

    # Store in a separate folder from prescriptions
    doc_folder = os.path.join(os.path.dirname(Config.UPLOAD_FOLDER), 'pharmacy_docs')
    os.makedirs(doc_folder, exist_ok=True)

    unique_filename = f"pharma_{pharmacy.id}_{uuid.uuid4().hex}_{filename}"
    full_path = os.path.join(doc_folder, unique_filename)

    try:
        # Remove old doc file if it exists
        if pharmacy.verification_doc_path and os.path.exists(pharmacy.verification_doc_path):
            try:
                os.remove(pharmacy.verification_doc_path)
            except OSError:
                logger.warning("Could not remove old verification doc: %s", pharmacy.verification_doc_path)

        file.save(full_path)
    except Exception:
        logger.exception("Failed to save verification document for pharmacy %s", pharmacy.id)
        return jsonify({'error': 'Failed to save document.'}), 500

    pharmacy.verification_doc_path = full_path
    pharmacy.verification_doc_filename = filename
    db.session.commit()

    return jsonify({
        'message': 'Verification document uploaded successfully. Awaiting admin review.',
        'has_verification_doc': True,
        'original_filename': filename,
    }), 200


@pharmacy_bp.route('/pharmacy/verification-doc', methods=['GET'])
def get_verification_doc():
    """
    Admin or the pharmacy owner can download the verification document.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized.'}), 401

    if current_user.role not in ('admin', 'pharmacy'):
        return jsonify({'error': 'Unauthorized.'}), 403

    if current_user.role == 'pharmacy':
        pharmacy = PharmacyService.get_pharmacy_by_owner_id(current_user.id)
    else:
        # Admin: can specify pharmacy_id as query param
        pharmacy_id = request.args.get('pharmacy_id', type=int)
        if not pharmacy_id:
            return jsonify({'error': 'pharmacy_id is required for admin.'}), 400
        pharmacy = PharmacyService.get_pharmacy_by_id(pharmacy_id)

    if not pharmacy:
        return jsonify({'error': 'Pharmacy not found.'}), 404

    if not pharmacy.verification_doc_path:
        return jsonify({'error': 'No verification document uploaded yet.'}), 404

    if not os.path.exists(pharmacy.verification_doc_path):
        return jsonify({'error': 'Document file not found on server.'}), 404

    return send_file(
        pharmacy.verification_doc_path,
        download_name=pharmacy.verification_doc_filename or 'verification_document',
    )
