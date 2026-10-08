import os
from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
from backend.services.notification_service import NotificationService
from backend.services.prescription_service import PrescriptionService
from backend.models import Prescription
from backend.config import Config

common_bp = Blueprint('common', __name__, url_prefix='/api')

@common_bp.route('/notifications', methods=['GET'])
def get_notifications():
    if not current_user.is_authenticated:
        return jsonify({'notifications': []}), 200

    unread_only = request.args.get('unread', 'false').lower() == 'true'
    notifications = NotificationService.get_user_notifications(current_user.id, unread_only=unread_only)
    return jsonify({'notifications': notifications}), 200


@common_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
def mark_notification_read(notification_id):
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized.'}), 401

    success = NotificationService.mark_as_read(notification_id, current_user.id)
    return jsonify({'success': success}), 200


@common_bp.route('/prescriptions/upload', methods=['POST'])
def upload_prescription():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Please login to upload a prescription.'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded.'}), 400

    file = request.files['file']
    pharmacy_id = request.form.get('pharmacy_id', type=int)

    try:
        prescription = PrescriptionService.save_prescription(
            customer_id=current_user.id,
            file_storage=file,
            pharmacy_id=pharmacy_id
        )
        return jsonify({
            'message': 'Prescription uploaded successfully.',
            'prescription': prescription.to_dict()
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to save prescription file.'}), 500


@common_bp.route('/prescriptions/<int:prescription_id>/file', methods=['GET'])
def get_prescription_file(prescription_id):
    """
    Secure file retrieval: Authorization required.
    Ensures prescription files are NOT publicly accessible.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized.'}), 401

    prescription = Prescription.query.get(prescription_id)
    if not prescription:
        return jsonify({'error': 'Prescription not found.'}), 404

    if not PrescriptionService.check_access_permission(prescription, current_user):
        return jsonify({'error': 'Access denied to this prescription file.'}), 403

    if not os.path.exists(prescription.file_path):
        return jsonify({'error': 'File not found on server.'}), 404

    return send_file(prescription.file_path, download_name=prescription.original_filename)
