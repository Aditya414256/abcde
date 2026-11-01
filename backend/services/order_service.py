import logging
import uuid
from datetime import datetime, timezone
from backend.models import Order, Pharmacy, Medicine, PharmacyInventory, Prescription
from backend.services.location_service import LocationService
from backend.services.notification_service import NotificationService
from backend.database import db

logger = logging.getLogger(__name__)

# States from which a customer may still cancel
_CUSTOMER_CANCELLABLE_STATES = frozenset({'PENDING', 'ACCEPTED'})

# States where stock HAS been deducted (ACCEPTED→CONFIRMED triggers deduction)
# and must be restored on cancel/reject
_STOCK_DEDUCTED_STATES = frozenset({
    'CONFIRMED', 'PREPARING', 'READY_FOR_PICKUP', 'OUT_FOR_DELIVERY'
})


class OrderService:
    # State machine definition
    # Stock deduction: ACCEPTED → CONFIRMED (atomically, with row-level lock)
    # Stock restoration: any _STOCK_DEDUCTED_STATES → CANCELLED/REJECTED
    ALLOWED_TRANSITIONS = {
        'PENDING':            ['ACCEPTED', 'REJECTED', 'CANCELLED'],
        'ACCEPTED':           ['CONFIRMED', 'CANCELLED'],
        'CONFIRMED':          ['PREPARING', 'CANCELLED'],
        'PREPARING':          ['READY_FOR_PICKUP', 'OUT_FOR_DELIVERY'],
        'READY_FOR_PICKUP':   ['COMPLETED'],
        'OUT_FOR_DELIVERY':   ['COMPLETED'],
        'COMPLETED':          [],
        'REJECTED':           [],
        'CANCELLED':          [],
    }

    @classmethod
    def generate_order_number(cls):
        date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
        random_suffix = uuid.uuid4().hex[:6].upper()
        return f"MF-{date_str}-{random_suffix}"

    @classmethod
    def create_order(cls, customer_id, pharmacy_id, medicine_id, quantity, order_type,
                     delivery_address=None, contact_phone=None, customer_notes=None,
                     prescription_id=None, idempotency_key=None):
        """
        Creates an order with comprehensive server-side validations.

        CRITICAL INVARIANT: inventory is NOT deducted here.
        Stock deduction happens exactly once, atomically, when the pharmacy
        transitions the order ACCEPTED → CONFIRMED via update_order_status.

        Idempotency prevents duplicate orders on network retries.
        """
        # Idempotency check — must be the very first thing before any mutation
        if idempotency_key:
            existing_order = Order.query.filter_by(idempotency_key=idempotency_key).first()
            if existing_order:
                logger.info("Returning existing order %s for idempotency key %s",
                            existing_order.order_number, idempotency_key)
                return existing_order

        # Validate order type
        if order_type not in ('PICKUP', 'DELIVERY'):
            raise ValueError("Invalid order type. Must be PICKUP or DELIVERY.")

        # Validate quantity
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            raise ValueError("Quantity must be a valid integer.")
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        # Validate pharmacy
        pharmacy = db.session.get(Pharmacy, pharmacy_id)
        if not pharmacy:
            raise ValueError("Pharmacy not found.")
        if not pharmacy.is_active:
            raise ValueError("This pharmacy is currently inactive.")
        if not pharmacy.is_verified:
            raise ValueError("This pharmacy is not verified for ordering.")
        if order_type == 'PICKUP' and not pharmacy.supports_pickup:
            raise ValueError("This pharmacy does not support store pickup.")
        if order_type == 'DELIVERY' and not pharmacy.supports_delivery:
            raise ValueError("This pharmacy does not support home delivery.")
        if order_type == 'DELIVERY' and not str(delivery_address or '').strip():
            raise ValueError("Delivery address is required for home delivery.")

        # Validate medicine
        medicine = db.session.get(Medicine, medicine_id)
        if not medicine:
            raise ValueError("Medicine not found.")

        # Prescription validation — logic differs by order type
        prescription_pending_at_pickup = False
        if medicine.requires_prescription:
            if order_type == 'DELIVERY':
                if not prescription_id:
                    raise ValueError(
                        "This medicine requires a valid prescription. "
                        "Please upload your prescription before placing a delivery order."
                    )
            else:  # PICKUP — no digital upload required; physical Rx verified at counter
                prescription_pending_at_pickup = True

        # Verify ownership of the provided prescription
        if prescription_id:
            prescription = db.session.get(Prescription, prescription_id)
            if not prescription or prescription.customer_id != customer_id:
                raise ValueError("Invalid prescription provided.")

        # Check that inventory exists for price calculation.
        # NOTE: Stock is NOT deducted here. Deduction occurs on ACCEPTED → CONFIRMED.
        inventory = PharmacyInventory.query.filter_by(
            pharmacy_id=pharmacy_id,
            medicine_id=medicine_id,
        ).first()

        if not inventory:
            raise ValueError("This medicine is not in the pharmacy's inventory.")

        # Advisory pre-check (non-locking). Authoritative check + lock on CONFIRMED.
        if inventory.quantity < quantity:
            raise ValueError(
                f"Insufficient stock. Available: {inventory.quantity}, Requested: {quantity}."
            )

        unit_price = inventory.price
        delivery_fee = pharmacy.delivery_fee if order_type == 'DELIVERY' else 0.0
        total_amount = round((unit_price * quantity) + delivery_fee, 2)

        order = Order(
            order_number=cls.generate_order_number(),
            customer_id=customer_id,
            pharmacy_id=pharmacy_id,
            medicine_id=medicine_id,
            quantity=quantity,
            unit_price=unit_price,
            delivery_fee=delivery_fee,
            total_amount=total_amount,
            order_type=order_type,
            status='PENDING',
            delivery_address=delivery_address,
            contact_phone=contact_phone,
            customer_notes=customer_notes,
            prescription_id=prescription_id,
            prescription_pending_at_pickup=prescription_pending_at_pickup,
            idempotency_key=idempotency_key,
        )

        db.session.add(order)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            # Handle idempotency race: another concurrent request may have committed first
            if idempotency_key:
                existing_order = Order.query.filter_by(idempotency_key=idempotency_key).first()
                if existing_order:
                    return existing_order
            raise

        # Notifications are secondary — failure must not undo the committed order
        try:
            rx_note = (
                " ⚠️ Prescription required — verify physical Rx before dispensing."
                if prescription_pending_at_pickup else ""
            )
            NotificationService.create_notification(
                user_id=pharmacy.owner_id,
                title="New Order Received",
                message=(
                    f"New {order_type} order #{order.order_number} for "
                    f"{medicine.name} (Qty: {quantity}).{rx_note}"
                ),
                order_id=order.id,
            )
        except Exception as notif_err:
            logger.exception("Failed to dispatch pharmacy notification for order %s: %s",
                             order.id, notif_err)

        try:
            customer_rx_note = (
                " Remember to bring your physical prescription when collecting your order."
                if prescription_pending_at_pickup else ""
            )
            NotificationService.create_notification(
                user_id=customer_id,
                title="Order Placed",
                message=(
                    f"Your {order_type.lower()} order #{order.order_number} has been "
                    f"placed at {pharmacy.name}.{customer_rx_note}"
                ),
                order_id=order.id,
            )
        except Exception as notif_err:
            logger.exception("Failed to dispatch customer notification for order %s: %s",
                             order.id, notif_err)

        return order

    @classmethod
    def find_nearest_eligible_pickup_pharmacy(cls, medicine_id, user_lat, user_lon, quantity=1):
        """
        DEPRECATED — kept for backward compatibility only.
        The customer-facing Store Pickup flow uses find_eligible_pickup_pharmacies
        and then the customer explicitly chooses. This method is not called by the
        primary customer flow.
        """
        if user_lat is None or user_lon is None:
            raise ValueError(
                "Location permission required. "
                "Unable to determine nearest pharmacy without coordinates."
            )
        try:
            user_lat = float(user_lat)
            user_lon = float(user_lon)
        except (ValueError, TypeError):
            raise ValueError("Invalid coordinates provided.")

        medicine = db.session.get(Medicine, medicine_id)
        if not medicine:
            raise ValueError("Medicine not found.")

        inventories = PharmacyInventory.query.filter(
            PharmacyInventory.medicine_id == medicine_id,
            PharmacyInventory.quantity >= quantity,
        ).all()

        eligible = []
        for inv in inventories:
            pharmacy = inv.pharmacy
            if (pharmacy and pharmacy.is_active and pharmacy.is_verified
                    and pharmacy.supports_pickup and pharmacy.latitude and pharmacy.longitude):
                dist = LocationService.haversine_distance(
                    user_lat, user_lon, pharmacy.latitude, pharmacy.longitude
                )
                if dist is not None:
                    eligible.append({
                        'pharmacy': pharmacy,
                        'inventory': inv,
                        'distance_km': dist,
                        'distance_text': LocationService.format_distance(dist),
                    })

        if not eligible:
            return None

        eligible.sort(key=lambda x: x['distance_km'])
        return eligible[0]

    @classmethod
    def find_eligible_pickup_pharmacies(cls, medicine_id, user_lat=None, user_lon=None, quantity=1):
        """
        Store Pickup Pharmacy Listing (customer-choice flow).
        Returns all active, verified, pickup-enabled pharmacies that have sufficient
        stock for the requested quantity. Distance is included when coordinates are
        provided, but the customer is free to choose ANY pharmacy from the list.
        Never auto-selects or creates an order.
        """
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            raise ValueError("Quantity must be a valid integer.")
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        medicine = db.session.get(Medicine, medicine_id)
        if not medicine:
            raise ValueError("Medicine not found.")

        inventories = PharmacyInventory.query.filter(
            PharmacyInventory.medicine_id == medicine_id,
            PharmacyInventory.quantity >= quantity,
        ).all()

        eligible = []
        for inv in inventories:
            pharmacy = inv.pharmacy
            if pharmacy and pharmacy.is_active and pharmacy.is_verified and pharmacy.supports_pickup:
                dist = None
                if (user_lat is not None and user_lon is not None
                        and pharmacy.latitude and pharmacy.longitude):
                    dist = LocationService.haversine_distance(
                        float(user_lat), float(user_lon),
                        pharmacy.latitude, pharmacy.longitude,
                    )

                eligible.append({
                    'pharmacy_id': pharmacy.id,
                    'pharmacy_name': pharmacy.name,
                    'address': pharmacy.address,
                    'city': pharmacy.city,
                    'pincode': pharmacy.pincode,
                    'unit_price': inv.price,
                    'stock_quantity': inv.quantity,
                    'stock_status': inv.stock_status,
                    'is_verified': pharmacy.is_verified,
                    'distance_km': dist,
                    'distance_text': LocationService.format_distance(dist) if dist is not None else None,
                })

        # Sort by distance when location available; pharmacies without coords go last
        if user_lat is not None and user_lon is not None:
            eligible.sort(key=lambda x: (x['distance_km'] is None, x['distance_km'] or 0))

        return eligible

    @classmethod
    def find_eligible_delivery_pharmacies(cls, medicine_id, user_lat=None, user_lon=None, quantity=1):
        """
        Delivery Pharmacy Listing.
        Returns active, verified, delivery-enabled pharmacies with medicine in stock.
        """
        medicine = db.session.get(Medicine, medicine_id)
        if not medicine:
            raise ValueError("Medicine not found.")

        inventories = PharmacyInventory.query.filter(
            PharmacyInventory.medicine_id == medicine_id,
            PharmacyInventory.quantity >= quantity,
        ).all()

        eligible = []
        for inv in inventories:
            pharmacy = inv.pharmacy
            if pharmacy and pharmacy.is_active and pharmacy.is_verified and pharmacy.supports_delivery:
                dist = None
                if (user_lat is not None and user_lon is not None
                        and pharmacy.latitude and pharmacy.longitude):
                    dist = LocationService.haversine_distance(
                        user_lat, user_lon, pharmacy.latitude, pharmacy.longitude
                    )

                eligible.append({
                    'pharmacy_id': pharmacy.id,
                    'pharmacy_name': pharmacy.name,
                    'address': pharmacy.address,
                    'city': pharmacy.city,
                    'unit_price': inv.price,
                    'delivery_fee': pharmacy.delivery_fee,
                    'distance_km': dist,
                    'distance_text': (
                        LocationService.format_distance(dist)
                        if dist is not None
                        else "Distance unavailable"
                    ),
                })

        if user_lat is not None and user_lon is not None:
            eligible.sort(key=lambda x: (x['distance_km'] is None, x['distance_km']))

        return eligible

    @classmethod
    def update_order_status(cls, order_id, user_id, user_role, new_status, reason=None):
        """
        Updates order status following the strict state machine.

        STOCK RULES (authoritative):
        - ACCEPTED → CONFIRMED: deduct stock exactly once with row-level lock.
        - Any _STOCK_DEDUCTED_STATES → CANCELLED/REJECTED: restore stock once.
        - PENDING → CANCELLED/REJECTED: no stock change (none was ever deducted).
        - ACCEPTED → CANCELLED: no stock change (deduction had not yet happened).

        CUSTOMER RULES:
        - Customers may only cancel PENDING or ACCEPTED orders.
        - Cancellation from CONFIRMED or later is blocked for customers.

        Notifies the customer of every status change.
        For REJECTED orders, the customer-facing message is always:
        "Your order was not taken." — with the reason shown separately.
        """
        order = db.session.get(Order, order_id)
        if not order:
            raise ValueError("Order not found.")

        # Authorization checks
        if user_role == 'pharmacy':
            if order.pharmacy.owner_id != user_id:
                raise PermissionError("You can only manage orders for your own pharmacy.")
        elif user_role == 'customer':
            if order.customer_id != user_id:
                raise PermissionError("You can only manage your own orders.")
            if new_status != 'CANCELLED':
                raise PermissionError("Customers may only cancel orders.")
            if order.status not in _CUSTOMER_CANCELLABLE_STATES:
                raise ValueError(
                    f"Orders in '{order.status}' status can no longer be cancelled."
                )
        elif user_role != 'admin':
            raise PermissionError("Unauthorized role.")

        current_status = order.status
        allowed = cls.ALLOWED_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition order from '{current_status}' to '{new_status}'."
            )

        # -------------------------------------------------------------------
        # ACCEPTED → CONFIRMED: deduct stock atomically with row-level lock
        # -------------------------------------------------------------------
        if current_status == 'ACCEPTED' and new_status == 'CONFIRMED':
            inv = PharmacyInventory.query.filter_by(
                pharmacy_id=order.pharmacy_id,
                medicine_id=order.medicine_id,
            ).with_for_update().first()

            if not inv:
                raise ValueError("Inventory record not found. Cannot confirm order.")

            if inv.quantity < order.quantity:
                raise ValueError(
                    f"Insufficient stock to confirm order. "
                    f"Available: {inv.quantity}, Required: {order.quantity}."
                )

            inv.quantity -= order.quantity
            # Defensive guard — should never trigger given the check above
            if inv.quantity < 0:
                db.session.rollback()
                raise ValueError("Stock would go negative. Order confirmation rejected.")

            inv.recalculate_stock_status()
            inv.last_updated_at = datetime.now(timezone.utc)

        # -------------------------------------------------------------------
        # CANCELLED or REJECTED: restore stock only if previously deducted
        # Stock is deducted at ACCEPTED→CONFIRMED, so only states at or after
        # CONFIRMED need restoration.
        # -------------------------------------------------------------------
        elif new_status in ('CANCELLED', 'REJECTED'):
            if current_status in _STOCK_DEDUCTED_STATES:
                inv = PharmacyInventory.query.filter_by(
                    pharmacy_id=order.pharmacy_id,
                    medicine_id=order.medicine_id,
                ).with_for_update().first()
                if inv is not None:
                    inv.quantity += order.quantity
                    inv.recalculate_stock_status()
                    inv.last_updated_at = datetime.now(timezone.utc)
                else:
                    logger.error(
                        "Inventory record missing during stock restoration "
                        "for %s of order %s", new_status, order.id,
                    )
            # PENDING or ACCEPTED: no stock was deducted, nothing to restore

        order.status = new_status
        order.updated_at = datetime.now(timezone.utc)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        # Notify the customer — failure here must not undo the committed status change
        try:
            if new_status == 'REJECTED':
                # Required wording per spec
                title = "Order Update: Your order was not taken."
                message = f"Your order #{order.order_number}: Your order was not taken."
                if reason:
                    message += f" Reason: {reason}"
            else:
                status_readable = new_status.replace('_', ' ').title()
                title = f"Order Update: {status_readable}"
                message = (
                    f"Your order #{order.order_number} status has been updated to: "
                    f"{status_readable}."
                )
                if reason:
                    message += f" Note: {reason}"

            NotificationService.create_notification(
                user_id=order.customer_id,
                title=title,
                message=message,
                order_id=order.id,
            )
        except Exception as notif_err:
            logger.exception(
                "Failed to dispatch status update notification for order %s: %s",
                order.id, notif_err,
            )

        return order
