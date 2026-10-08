from flask import Blueprint, request, jsonify
from backend.services.medicine_service import MedicineService

medicine_bp = Blueprint('medicines', __name__, url_prefix='/api/medicines')

@medicine_bp.route('/search', methods=['GET'])
def search_medicines():
    """
    Search medicines by name, generic name, brand name, strength, dosage form.
    Fast, case-insensitive, safe against malformed input.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'results': []}), 200

    results = MedicineService.search_medicines(query)
    return jsonify({
        'query': query,
        'count': len(results),
        'results': results
    }), 200


@medicine_bp.route('/suggestions', methods=['GET'])
def get_suggestions():
    """
    Autocomplete suggestions for Home search dropdown.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'suggestions': []}), 200

    suggestions = MedicineService.get_suggestions(query)
    return jsonify({
        'query': query,
        'suggestions': suggestions
    }), 200


@medicine_bp.route('/<int:medicine_id>', methods=['GET'])
def get_medicine_detail(medicine_id):
    medicine = MedicineService.get_medicine_by_id(medicine_id)
    if not medicine:
        return jsonify({'error': 'Medicine not found.'}), 404

    return jsonify({'medicine': medicine.to_dict()}), 200
