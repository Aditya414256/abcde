from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from backend.database import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='customer') # 'customer', 'pharmacy', 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    pharmacies = db.relationship('Pharmacy', backref='owner', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='customer', lazy=True)
    prescriptions = db.relationship('Prescription', backref='customer', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'full_name': self.full_name,
            'phone': self.phone,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Pharmacy(db.Model):
    __tablename__ = 'pharmacies'

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False, index=True)
    license_number = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    pincode = db.Column(db.String(20), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    supports_pickup = db.Column(db.Boolean, default=True)
    supports_delivery = db.Column(db.Boolean, default=False)
    delivery_fee = db.Column(db.Float, default=0.0)
    is_verified = db.Column(db.Boolean, default=False) # Only admin can verify
    verification_status = db.Column(db.String(20), default='PENDING') # PENDING, APPROVED, REJECTED
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    inventories = db.relationship('PharmacyInventory', backref='pharmacy', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='pharmacy', lazy=True)

    def to_dict(self, include_owner=False):
        data = {
            'id': self.id,
            'name': self.name,
            'license_number': self.license_number,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'city': self.city,
            'state': self.state,
            'pincode': self.pincode,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'supports_pickup': self.supports_pickup,
            'supports_delivery': self.supports_delivery,
            'delivery_fee': self.delivery_fee,
            'is_verified': self.is_verified,
            'verification_status': self.verification_status,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_owner and self.owner:
            data['owner'] = self.owner.to_dict()
        return data


class Medicine(db.Model):
    __tablename__ = 'medicines'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    generic_name = db.Column(db.String(150), nullable=False, index=True)
    brand_name = db.Column(db.String(150), nullable=True)
    strength = db.Column(db.String(50), nullable=True) # e.g. "500mg"
    dosage_form = db.Column(db.String(50), nullable=True) # e.g. "Tablet", "Syrup"
    description = db.Column(db.Text, nullable=True)
    requires_prescription = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    inventories = db.relationship('PharmacyInventory', backref='medicine', lazy=True)
    orders = db.relationship('Order', backref='medicine', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'generic_name': self.generic_name,
            'brand_name': self.brand_name,
            'strength': self.strength,
            'dosage_form': self.dosage_form,
            'description': self.description,
            'requires_prescription': self.requires_prescription,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class PharmacyInventory(db.Model):
    __tablename__ = 'pharmacy_inventory'
    __table_args__ = (
        db.UniqueConstraint('pharmacy_id', 'medicine_id', name='uq_pharmacy_medicine'),
    )

    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'), nullable=False)
    quantity = db.Column(db.Integer, default=0, nullable=False)
    price = db.Column(db.Float, default=0.0, nullable=False)
    stock_status = db.Column(db.String(20), default='OUT_OF_STOCK') # AVAILABLE, LOW_STOCK, OUT_OF_STOCK, UNKNOWN
    batch_number = db.Column(db.String(50), nullable=True)
    expiry_date = db.Column(db.String(20), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    last_updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def recalculate_stock_status(self):
        if self.quantity <= 0:
            self.stock_status = 'OUT_OF_STOCK'
        elif self.quantity < 10:
            self.stock_status = 'LOW_STOCK'
        else:
            self.stock_status = 'AVAILABLE'

    def to_dict(self):
        return {
            'id': self.id,
            'pharmacy_id': self.pharmacy_id,
            'medicine_id': self.medicine_id,
            'quantity': self.quantity,
            'price': self.price,
            'stock_status': self.stock_status,
            'batch_number': self.batch_number,
            'expiry_date': self.expiry_date,
            'notes': self.notes,
            'last_updated_at': self.last_updated_at.isoformat() if self.last_updated_at else None,
            'medicine': self.medicine.to_dict() if self.medicine else None
        }


class Prescription(db.Model):
    __tablename__ = 'prescriptions'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=True)
    file_path = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='PENDING') # PENDING, APPROVED, REJECTED (Strict manual review, no AI auto-approval)
    review_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='prescription', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'pharmacy_id': self.pharmacy_id,
            'original_filename': self.original_filename,
            'status': self.status,
            'review_notes': self.review_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Order(db.Model):
    __tablename__ = 'orders'

    # State machine values:
    # PENDING -> ACCEPTED -> CONFIRMED -> PREPARING -> READY_FOR_PICKUP / OUT_FOR_DELIVERY -> COMPLETED
    # Cancellations: REJECTED, CANCELLED

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, index=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey('pharmacies.id'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    delivery_fee = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    order_type = db.Column(db.String(20), nullable=False) # 'PICKUP', 'DELIVERY'
    status = db.Column(db.String(30), default='PENDING', index=True)
    delivery_address = db.Column(db.Text, nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)
    customer_notes = db.Column(db.Text, nullable=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id'), nullable=True)
    # For PICKUP orders on prescription-required medicines:
    # True  → customer did NOT upload a digital prescription; pharmacy must verify physical Rx before dispensing.
    # False → no prescription required (OTC), or prescription was uploaded digitally for a delivery order.
    prescription_pending_at_pickup = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'order_number': self.order_number,
            'customer_id': self.customer_id,
            'customer_name': self.customer.full_name if self.customer else None,
            'pharmacy_id': self.pharmacy_id,
            'pharmacy_name': self.pharmacy.name if self.pharmacy else None,
            'medicine_id': self.medicine_id,
            'medicine_name': self.medicine.name if self.medicine else None,
            'medicine_strength': self.medicine.strength if self.medicine else None,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'delivery_fee': self.delivery_fee,
            'total_amount': self.total_amount,
            'order_type': self.order_type,
            'status': self.status,
            'delivery_address': self.delivery_address,
            'contact_phone': self.contact_phone,
            'customer_notes': self.customer_notes,
            'prescription_id': self.prescription_id,
            'prescription_pending_at_pickup': self.prescription_pending_at_pickup,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'is_read': self.is_read,
            'order_id': self.order_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
