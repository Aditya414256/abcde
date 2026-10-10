import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from backend.services.order_service import OrderService
from backend.services.medicine_service import MedicineService
from backend.models import Order
from backend.database import db

logger = logging.getLogger(__name__)

order_bp = Blueprint('orders', __name__, url_prefix='/api/orders')

@order_bp.route('/pickup-nearest', methods=['POST'])
def auto_pickup_order():
    """
    DEPRECATED customer path — kept for backward compatibility only.
    The customer-facing Store Pickup flow now uses /pickup-pharmacies + /pickup.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Please login to place an order.', 'require_login': True}), 401

    data = request.get_json() or {}
    medicine_id = data.get('medicine_id')
    user_lat = data.get('latitude')
    user_lon = data.get('longitude')
    quantity = data.get('quantity', 1)
    customer_notes = data.get('customer_notes')
    prescription_id = data.get('prescription_id')

    if not medicine_id:
        return jsonify({'error': 'Medicine ID is required.'}), 400

    if user_lat is None or user_lon is None:
        return jsonify({
            'error': 'Location unavailable. Please allow location access in your browser to find your nearest verified pharmacy.',
            'location_error': True
        }), 400

    try:
        nearest = OrderService.find_nearest_eligible_pickup_pharmacy(
            medicine_id=medicine_id,
            user_lat=user_lat,
            user_lon=user_lon,
            quantity=quantity
        )

        if not nearest:
            return jsonify({
                'error': 'No verified pharmacies nearby currently have this medicine in stock for pickup.'
            }), 404

        pharmacy = nearest['pharmacy']
        order = OrderService.create_order(
            customer_id=current_user.id,
            pharmacy_id=pharmacy.id,
            medicine_id=medicine_id,
            quantity=quantity,
            order_type='PICKUP',
            customer_notes=customer_notes,
            prescription_id=prescription_id
        )

        return jsonify({
            'message': 'Your order has been placed.',
            'order': order.to_dict(),
            'pharmacy': pharmacy.to_dict(),
            'distance_text': nearest['distance_text']
        }), 201

    except ValueError as e:
        logger.warning("Auto pickup order validation error: %s", e)
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("Unexpected error processing auto pickup order: %s", e)
        return jsonify({'error': 'Failed to process pickup order.'}), 500


@order_bp.route('/pickup-pharmacies', methods=['GET'])
def get_pickup_pharmacies():
    """
    Store Pickup — customer pharmacy listing.
    Returns all eligible pickup pharmacies for the requested medicine + quantity.
    Sorted by distance when coordinates are supplied; never auto-selects a pharmacy.
    Does NOT create any order.
    """
    medicine_id = request.args.get('medicine_id', type=int)
    user_lat = request.args.get('latitude', type=float)
    user_lon = request.args.get('longitude', type=float)
    quantity = request.args.get('quantity', 1, type=int)

    if not medicine_id:
        return jsonify({'error': 'Medicine ID is required.'}), 400

    try:
        pharmacies = OrderService.find_eligible_pickup_pharmacies(
            medicine_id=medicine_id,
            user_lat=user_lat,
            user_lon=user_lon,
            quantity=quantity
        )
        return jsonify({
            'medicine_id': medicine_id,
            'count': len(pharmacies),
            'pharmacies': pharmacies
        }), 200
    except ValueError as e:
        logger.warning("Pickup pharmacy search error: %s", e)
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("Unexpected error fetching pickup pharmacies: %s", e)
        return jsonify({'error': 'Failed to retrieve eligible pharmacies.'}), 500


@order_bp.route('/pickup', methods=['POST'])
def create_pickup_order():
    """
    Store Pickup — customer explicit pharmacy selection.
    Creates a PICKUP order for the pharmacy the customer explicitly chose.
    Server independently validates pharmacy eligibility, pickup support,
    inventory, and prescription before creating the order.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Please login to place an order.', 'require_login': True}), 401

    data = request.get_json() or {}
    pharmacy_id = data.get('pharmacy_id')
    medicine_id = data.get('medicine_id')
    quantity = data.get('quantity', 1)
    customer_notes = data.get('customer_notes')
    prescription_id = data.get('prescription_id')
    idempotency_key = data.get('idempotency_key')

    if not pharmacy_id or not medicine_id:
        return jsonify({'error': 'Pharmacy ID and Medicine ID are required.'}), 400

    try:
        order = OrderService.create_order(
            customer_id=current_user.id,
            pharmacy_id=pharmacy_id,
            medicine_id=medicine_id,
            quantity=quantity,
            order_type='PICKUP',
            customer_notes=customer_notes,
            prescription_id=prescription_id,
            idempotency_key=idempotency_key
        )
        return jsonify({
            'message': 'Your order has been placed.',
            'order': order.to_dict()
        }), 201
    except ValueError as e:
        logger.warning("Pickup order validation error: %s", e)
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("Unexpected error creating pickup order: %s", e)
        return jsonify({'error': 'Failed to create pickup order.'}), 500


@order_bp.route('/delivery-pharmacies', methods=['GET'])
def get_delivery_pharmacies():
    """
    Take From Delivery screen:
    Shows active + verified + delivery-enabled pharmacies with medicine in stock.
    Displays: Pharmacy Name + Distance.
    """
    medicine_id = request.args.get('medicine_id', type=int)
    user_lat = request.args.get('latitude', type=float)
    user_lon = request.args.get('longitude', type=float)
    quantity = request.args.get('quantity', 1, type=int)

    if not medicine_id:
        return jsonify({'error': 'Medicine ID is required.'}), 400

    try:
        pharmacies = OrderService.find_eligible_delivery_pharmacies(
            medicine_id=medicine_id,
            user_lat=user_lat,
            user_lon=user_lon,
            quantity=quantity
        )
        return jsonify({
            'medicine_id': medicine_id,
            'count': len(pharmacies),
            'pharmacies': pharmacies
        }), 200
    except ValueError as e:
        logger.warning("Delivery pharmacy search error: %s", e)
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("Unexpected error fetching delivery pharmacies: %s", e)
        return jsonify({'error': 'Failed to retrieve eligible pharmacies.'}), 500


@order_bp.route('/create', methods=['POST'])
def create_delivery_order():
    """
    Delivery Order submission.
    Verifies pharmacy eligibility, delivery support, inventory, quantity.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Please login to place an order.', 'require_login': True}), 401

    data = request.get_json() or {}
    pharmacy_id = data.get('pharmacy_id')
    medicine_id = data.get('medicine_id')
    quantity = data.get('quantity', 1)
    order_type = data.get('order_type', 'DELIVERY')
    delivery_address = data.get('delivery_address')
    contact_phone = data.get('contact_phone')
    customer_notes = data.get('customer_notes')
    prescription_id = data.get('prescription_id')
    idempotency_key = data.get('idempotency_key')

    if not pharmacy_id or not medicine_id:
        return jsonify({'error': 'Pharmacy ID and Medicine ID are required.'}), 400

    if order_type == 'DELIVERY' and not delivery_address:
        return jsonify({'error': 'Delivery address is required.'}), 400

    try:
        order = OrderService.create_order(
            customer_id=current_user.id,
            pharmacy_id=pharmacy_id,
            medicine_id=medicine_id,
            quantity=quantity,
            order_type=order_type,
            delivery_address=delivery_address,
            contact_phone=contact_phone,
            customer_notes=customer_notes,
            prescription_id=prescription_id,
            idempotency_key=idempotency_key
        )

        return jsonify({
            'message': 'Your order has been placed.',
            'order': order.to_dict()
        }), 201

    except ValueError as e:
        logger.warning("Delivery order validation error: %s", e)
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("Unexpected error creating delivery order: %s", e)
        return jsonify({'error': 'Failed to create order.'}), 500


@order_bp.route('/my-orders', methods=['GET'])
def get_my_orders():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized.'}), 401

    orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()
    return jsonify({'orders': [o.to_dict() for o in orders]}), 200


@order_bp.route('/<int:order_id>', methods=['GET'])
def get_order_by_id(order_id):
    """
    Retrieve single order by ID for confirmation verification or refresh restoration.
    Restricted to customer, assigned pharmacy owner, or admin.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized. Please login.'}), 401

    order = db.session.get(Order, order_id)
    if not order:
        return jsonify({'error': 'Order not found.'}), 404

    is_customer = (order.customer_id == current_user.id)
    is_pharmacy_owner = (order.pharmacy and order.pharmacy.owner_id == current_user.id)
    is_admin = (current_user.role == 'admin')

    if not (is_customer or is_pharmacy_owner or is_admin):
        return jsonify({'error': 'Unauthorized to view this order.'}), 403

    return jsonify({'order': order.to_dict()}), 200


@order_bp.route('/by-idempotency/<key>', methods=['GET'])
def get_order_by_idempotency(key):
    """
    Checks if an order with the given idempotency key was already created for current user.
    Used during network retry, timeout recovery, or refresh during pending submission.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized. Please login.'}), 401

    order = Order.query.filter_by(customer_id=current_user.id, idempotency_key=key).first()
    if not order:
        return jsonify({'found': False, 'message': 'No order found for this idempotency key.'}), 404

    return jsonify({
        'found': True,
        'order': order.to_dict()
    }), 200


@order_bp.route('/<int:order_id>/status', methods=['POST', 'PATCH'])
def update_order_status(order_id):
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized.'}), 401

    data = request.get_json() or {}
    new_status = data.get('status')
    reason = data.get('reason')

    if not new_status:
        return jsonify({'error': 'New status is required.'}), 400

    try:
        order = OrderService.update_order_status(
            order_id=order_id,
            user_id=current_user.id,
            user_role=current_user.role,
            new_status=new_status,
            reason=reason
        )
        return jsonify({
            'message': f'Order status updated to {new_status}.',
            'order': order.to_dict()
        }), 200
    except (ValueError, PermissionError) as e:
        logger.warning("Order status update failed for order %s: %s", order_id, e)
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("Unexpected error updating status for order %s: %s", order_id, e)
        return jsonify({'error': 'Failed to update order status.'}), 500
