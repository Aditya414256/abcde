"""Small shared validators for user-supplied API values."""
import math
from werkzeug.exceptions import BadRequest


def coordinates(latitude, longitude):
    if latitude in ('', None) and longitude in ('', None):
        return None, None
    try:
        if isinstance(latitude, bool) or isinstance(longitude, bool):
            raise ValueError
        lat, lon = float(latitude), float(longitude)
        if not (math.isfinite(lat) and math.isfinite(lon)
                and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError
    except (ValueError, TypeError):
        raise BadRequest('Provide both valid latitude (-90 to 90) and longitude (-180 to 180).')
    return lat, lon


def validate_payload(data):
    if not isinstance(data, dict):
        raise BadRequest('Request body must be a JSON object.')
    # Reject wrong types before route handlers call strip(), lower(), or SQLAlchemy.
    strings = {
        'full_name': 100, 'email': 120, 'password': 1024,
        'confirm_password': 1024, 'current_password': 1024, 'new_password': 1024,
        'phone': 20, 'pharmacy_phone': 20, 'pharmacy_email': 120,
        'pharmacy_name': 150, 'license_number': 100, 'address': 255,
        'city': 100, 'state': 100, 'pincode': 20,
        'delivery_address': 2000, 'contact_phone': 20, 'customer_notes': 4000,
        'notes': 4000, 'reason': 4000, 'pharmacy_response': 4000,
        'medicine_name_text': 150, 'batch_number': 50, 'expiry_date': 20,
        'status': 30, 'action': 30, 'order_type': 20, 'idempotency_key': 100,
    }
    nullable = {'customer_notes', 'notes', 'reason', 'pharmacy_response',
                'batch_number', 'expiry_date', 'idempotency_key', 'contact_phone',
                'delivery_address', 'medicine_name_text'}
    for key, limit in strings.items():
        if key not in data or (data[key] is None and key in nullable):
            continue
        if not isinstance(data[key], str) or len(data[key]) > limit:
            raise BadRequest(f'{key} must be text of at most {limit} characters.')
    for key in ('supports_pickup', 'supports_delivery'):
        if key in data and not isinstance(data[key], bool):
            raise BadRequest(f'{key} must be true or false.')
    for key in ('medicine_id', 'pharmacy_id', 'prescription_id', 'quantity', 'quantity_needed'):
        if key not in data or (data[key] is None and key in ('prescription_id', 'medicine_id')):
            continue
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise BadRequest(f'{key} must be an integer.')
        try:
            number = int(value)
        except (ValueError, TypeError):
            raise BadRequest(f'{key} must be an integer.')
        if not 0 <= number <= 2147483647:
            raise BadRequest(f'{key} is out of range.')
        data[key] = number
    for key in ('price', 'delivery_fee'):
        if key not in data:
            continue
        try:
            if isinstance(data[key], bool):
                raise ValueError
            value = float(data[key])
            if not math.isfinite(value) or value < 0:
                raise ValueError
        except (ValueError, TypeError, OverflowError):
            raise BadRequest(f'{key} must be a finite, non-negative number.')
    return data
