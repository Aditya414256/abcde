"""
Medicine availability request routes.

Customer endpoints:
  POST   /api/requests              — submit a new request
  GET    /api/requests/my           — list own requests
  DELETE /api/requests/<id>         — cancel a PENDING request

Pharmacy endpoints:
  GET    /api/pharmacy/requests     — list all requests for this pharmacy
  PATCH  /api/requests/<id>/status  — update request status
"""
import logging
from flask import Blueprint, request, jsonify
from flask_login import current_user
from backend.services.request_service import RequestService
from backend.services.pharmacy_service import PharmacyService

logger = logging.getLogger(__name__)

request_bp = Blueprint('requests', __name__, url_prefix='/api')


# ── Customer: submit a request ──────────────────────────────────────────────

@request_bp.route('/requests', methods=['POST'])
def create_medicine_request():
    """Customer submits a medicine availability request to a pharmacy."""
    if not current_user.is_authenticated or current_user.role != 'customer':
        return jsonify({'error': 'Customer login required.'}), 401

    data = request.get_json() or {}
    pharmacy_id = data.get('pharmacy_id')
    medicine_id = data.get('medicine_id')
    medicine_name_text = data.get('medicine_name_text', '').strip()
    quantity_needed = data.get('quantity_needed', 1)
    customer_notes = data.get('customer_notes')

    if not pharmacy_id:
        return jsonify({'error': 'pharmacy_id is required.'}), 400

    try:
        req = RequestService.create_request(
            customer_id=current_user.id,
            pharmacy_id=pharmacy_id,
            quantity_needed=quantity_needed,
            medicine_id=medicine_id,
            medicine_name_text=medicine_name_text,
            customer_notes=customer_notes,
        )
        return jsonify({
            'message': 'Your medicine request has been submitted.',
            'request': req.to_dict(),
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        logger.exception("Unexpected error creating medicine request.")
        return jsonify({'error': 'Failed to submit medicine request.'}), 500


# ── Customer: list own requests ──────────────────────────────────────────────

@request_bp.route('/requests/my', methods=['GET'])
def get_my_requests():
    """Customer views their own medicine availability requests."""
    if not current_user.is_authenticated or current_user.role != 'customer':
        return jsonify({'error': 'Customer login required.'}), 401

    reqs = RequestService.get_customer_requests(current_user.id)
    return jsonify({'requests': [r.to_dict() for r in reqs]}), 200


# ── Customer: cancel a PENDING request ──────────────────────────────────────

@request_bp.route('/requests/<int:request_id>', methods=['DELETE'])
def cancel_medicine_request(request_id):
    """Customer cancels their own PENDING medicine request."""
    if not current_user.is_authenticated or current_user.role != 'customer':
        return jsonify({'error': 'Customer login required.'}), 401

    try:
        RequestService.cancel_request(request_id=request_id, customer_id=current_user.id)
        return jsonify({'message': 'Medicine request cancelled.'}), 200
    except (ValueError, PermissionError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        logger.exception("Unexpected error cancelling medicine request %s.", request_id)
        return jsonify({'error': 'Failed to cancel medicine request.'}), 500


# ── Pharmacy: list requests ──────────────────────────────────────────────────

@request_bp.route('/pharmacy/requests', methods=['GET'])
def get_pharmacy_medicine_requests():
    """Pharmacy owner views all medicine availability requests for their pharmacy."""
    if not current_user.is_authenticated or current_user.role != 'pharmacy':
        return jsonify({'error': 'Pharmacy login required.'}), 403

    pharmacy = PharmacyService.get_pharmacy_by_owner_id(current_user.id)
    if not pharmacy:
        return jsonify({'error': 'No pharmacy associated with this account.'}), 404

    try:
        reqs = RequestService.get_pharmacy_requests(
            pharmacy_id=pharmacy.id,
            owner_id=current_user.id,
        )
        return jsonify({'requests': [r.to_dict() for r in reqs]}), 200
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except Exception:
        logger.exception("Unexpected error fetching pharmacy medicine requests.")
        return jsonify({'error': 'Failed to retrieve medicine requests.'}), 500


# ── Pharmacy: update request status ─────────────────────────────────────────

@request_bp.route('/requests/<int:request_id>/status', methods=['PATCH', 'POST'])
def update_request_status(request_id):
    """Pharmacy owner updates the status of a medicine availability request."""
    if not current_user.is_authenticated or current_user.role != 'pharmacy':
        return jsonify({'error': 'Pharmacy login required.'}), 403

    data = request.get_json() or {}
    new_status = data.get('status')
    pharmacy_response = data.get('pharmacy_response')

    if not new_status:
        return jsonify({'error': 'status is required.'}), 400

    try:
        req = RequestService.update_request_status(
            request_id=request_id,
            owner_id=current_user.id,
            new_status=new_status,
            pharmacy_response=pharmacy_response,
        )
        return jsonify({
            'message': f'Request status updated to {new_status}.',
            'request': req.to_dict(),
        }), 200
    except (ValueError, PermissionError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        logger.exception("Unexpected error updating medicine request %s.", request_id)
        return jsonify({'error': 'Failed to update medicine request.'}), 500

