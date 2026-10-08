import uuid
from datetime import datetime
from backend.models import Order, Pharmacy, Medicine, PharmacyInventory, Prescription
from backend.services.location_service import LocationService
from backend.services.notification_service import NotificationService
from backend.database import db

class OrderService:
    # State machine definition
    ALLOWED_TRANSITIONS = {
        'PENDING': ['ACCEPTED', 'REJECTED', 'CANCELLED'],
        'ACCEPTED': ['CONFIRMED', 'CANCELLED'],
        'CONFIRMED': ['PREPARING', 'CANCELLED'],
        'PREPARING': ['READY_FOR_PICKUP', 'OUT_FOR_DELIVERY', 'CANCELLED'],
        'READY_FOR_PICKUP': ['COMPLETED', 'CANCELLED'],
        'OUT_FOR_DELIVERY': ['COMPLETED', 'CANCELLED'],
        'COMPLETED': [],
        'REJECTED': [],
        'CANCELLED': []
    }

    @classmethod
    def generate_order_number(cls):
        date_str = datetime.utcnow().strftime('%Y%m%d')
        random_suffix = uuid.uuid4().hex[:6].upper()
        return f"MF-{date_str}-{random_suffix}"

    @classmethod
    def create_order(cls, customer_id, pharmacy_id, medicine_id, quantity, order_type,
                     delivery_address=None, contact_phone=None, customer_notes=None,
                     prescription_id=None):
        """
        Creates an order with comprehensive server-side validations,
        transactional inventory check & decrement, and in-app notifications.
        """
        # Validate order type
        if order_type not in ['PICKUP', 'DELIVERY']:
            raise ValueError("Invalid order type. Must be PICKUP or DELIVERY.")

        # Validate quantity
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            raise ValueError("Quantity must be a valid integer.")

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        # Validate Pharmacy
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

        if order_type == 'DELIVERY' and not delivery_address:
            raise ValueError("Delivery address is required for home delivery.")

        # Validate Medicine
        medicine = db.session.get(Medicine, medicine_id)
        if not medicine:
            raise ValueError("Medicine not found.")

        if medicine.requires_prescription and not prescription_id:
            raise ValueError("This medicine requires a valid prescription to order.")

        # Verify prescription belongs to this customer if provided
        if prescription_id:
            prescription = db.session.get(Prescription, prescription_id)
            if not prescription or prescription.customer_id != customer_id:
                raise ValueError("Invalid prescription provided.")

        # Transactional Inventory Check & Decrement
        inventory = PharmacyInventory.query.filter_by(
            pharmacy_id=pharmacy_id,
            medicine_id=medicine_id
        ).with_for_update().first()

        if not inventory:
            raise ValueError("This medicine is not in the pharmacy's inventory.")

        if inventory.quantity < quantity:
            raise ValueError(f"Insufficient stock. Available: {inventory.quantity}, Requested: {quantity}.")

        # Safe stock decrement
        inventory.quantity -= quantity
        inventory.recalculate_stock_status()
        inventory.last_updated_at = datetime.utcnow()

        unit_price = inventory.price
        delivery_fee = pharmacy.delivery_fee if order_type == 'DELIVERY' else 0.0
        total_amount = round((unit_price * quantity) + delivery_fee, 2)

        order_number = cls.generate_order_number()

        order = Order(
            order_number=order_number,
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
            prescription_id=prescription_id
        )

        db.session.add(order)
        db.session.commit()

        # In-app notifications
        # 1. Notify pharmacy owner
        NotificationService.create_notification(
            user_id=pharmacy.owner_id,
            title="New Order Received",
            message=f"New {order_type} order #{order.order_number} for {medicine.name} (Qty: {quantity})",
            order_id=order.id
        )

        # 2. Notify customer
        NotificationService.create_notification(
            user_id=customer_id,
            title="Order Placed",
            message=f"Your {order_type.lower()} order #{order.order_number} has been placed at {pharmacy.name}.",
            order_id=order.id
        )

        return order

    @classmethod
    def find_nearest_eligible_pickup_pharmacy(cls, medicine_id, user_lat, user_lon, quantity=1):
        """
        Automatic Store Pickup Pharmacy Selection:
        Medicine
        -> Find pharmacies containing medicine
        -> Filter active pharmacies
        -> Filter admin-approved/verified pharmacies
        -> Filter pickup-enabled pharmacies
        -> Check inventory availability (>= quantity)
        -> Calculate distance using Haversine
        -> Select nearest eligible pharmacy
        """
        if user_lat is None or user_lon is None:
            raise ValueError("Location permission required. Unable to determine nearest pharmacy without coordinates.")

        try:
            user_lat = float(user_lat)
            user_lon = float(user_lon)
        except (ValueError, TypeError):
            raise ValueError("Invalid coordinates provided.")

        medicine = db.session.get(Medicine, medicine_id)
        if not medicine:
            raise ValueError("Medicine not found.")

        # Find all inventory records with sufficient stock
        inventories = PharmacyInventory.query.filter(
            PharmacyInventory.medicine_id == medicine_id,
            PharmacyInventory.quantity >= quantity
        ).all()

        eligible = []
        for inv in inventories:
            pharmacy = inv.pharmacy
            if (pharmacy and pharmacy.is_active and pharmacy.is_verified and 
                pharmacy.supports_pickup and pharmacy.latitude and pharmacy.longitude):
                dist = LocationService.haversine_distance(user_lat, user_lon, pharmacy.latitude, pharmacy.longitude)
                if dist is not None:
                    eligible.append({
                        'pharmacy': pharmacy,
                        'inventory': inv,
                        'distance_km': dist,
                        'distance_text': LocationService.format_distance(dist)
                    })

        if not eligible:
            return None

        # Sort by distance (nearest first)
        eligible.sort(key=lambda x: x['distance_km'])
        return eligible[0]

    @classmethod
    def find_eligible_delivery_pharmacies(cls, medicine_id, user_lat=None, user_lon=None, quantity=1):
        """
        Delivery Pharmacy Selection:
        Returns active, verified, delivery-enabled pharmacies with medicine in stock.
        Includes Pharmacy Name + Distance.
        """
        medicine = db.session.get(Medicine, medicine_id)
        if not medicine:
            raise ValueError("Medicine not found.")

        inventories = PharmacyInventory.query.filter(
            PharmacyInventory.medicine_id == medicine_id,
            PharmacyInventory.quantity >= quantity
        ).all()

        eligible = []
        for inv in inventories:
            pharmacy = inv.pharmacy
            if pharmacy and pharmacy.is_active and pharmacy.is_verified and pharmacy.supports_delivery:
                dist = None
                if user_lat is not None and user_lon is not None and pharmacy.latitude and pharmacy.longitude:
                    dist = LocationService.haversine_distance(user_lat, user_lon, pharmacy.latitude, pharmacy.longitude)

                eligible.append({
                    'pharmacy_id': pharmacy.id,
                    'pharmacy_name': pharmacy.name,
                    'address': pharmacy.address,
                    'city': pharmacy.city,
                    'unit_price': inv.price,
                    'delivery_fee': pharmacy.delivery_fee,
                    'distance_km': dist,
                    'distance_text': LocationService.format_distance(dist) if dist is not None else "Distance unavailable"
                })

        # Sort by distance if location available
        if user_lat is not None and user_lon is not None:
            eligible.sort(key=lambda x: (x['distance_km'] is None, x['distance_km']))

        return eligible

    @classmethod
    def update_order_status(cls, order_id, user_id, user_role, new_status, reason=None):
        """
        Updates order status following the strict state machine.
        Restores inventory stock if order is cancelled or rejected.
        Notifies customer of status updates.
        """
        order = db.session.get(Order, order_id)
        if not order:
            raise ValueError("Order not found.")

        # Authorization check
        if user_role == 'pharmacy':
            if order.pharmacy.owner_id != user_id:
                raise PermissionError("You can only manage orders for your own pharmacy.")
        elif user_role == 'customer':
            if order.customer_id != user_id:
                raise PermissionError("You can only manage your own orders.")
            if new_status != 'CANCELLED':
                raise PermissionError("Customers may only cancel pending orders.")
        elif user_role != 'admin':
            raise PermissionError("Unauthorized role.")

        current_status = order.status
        allowed = cls.ALLOWED_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(f"Cannot transition order from '{current_status}' to '{new_status}'.")

        order.status = new_status
        order.updated_at = datetime.utcnow()

        # If cancelled or rejected, restore stock safely
        if new_status in ['CANCELLED', 'REJECTED']:
            inv = PharmacyInventory.query.filter_by(
                pharmacy_id=order.pharmacy_id,
                medicine_id=order.medicine_id
            ).first()
            if inv:
                inv.quantity += order.quantity
                inv.recalculate_stock_status()
                inv.last_updated_at = datetime.utcnow()

        db.session.commit()

        # Notify customer
        status_readable = new_status.replace('_', ' ').title()
        NotificationService.create_notification(
            user_id=order.customer_id,
            title=f"Order Update: {status_readable}",
            message=f"Your order #{order.order_number} status has been updated to: {status_readable}." + (f" Note: {reason}" if reason else ""),
            order_id=order.id
        )

        return order
