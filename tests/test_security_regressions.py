"""Regression tests for security and order state invariants."""
import pytest

from backend.app import create_app
from backend.database import db
from backend.models import User, Pharmacy, Medicine, Prescription, PharmacyInventory
from backend.seed import seed_database
from backend.services.order_service import OrderService
from backend.services.prescription_service import PrescriptionService


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "test-only-key"
    SQLALCHEMY_ENGINE_OPTIONS = {}


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        seed_database(app)
        yield app
        db.session.remove()
        db.drop_all()


def test_idempotency_key_never_crosses_customers(app):
    with app.app_context():
        customer = User.query.filter_by(email="customer@example.com").first()
        other = User(email="other-regression@example.com", full_name="Other Customer", role="customer")
        other.set_password("testing-pass-123")
        db.session.add(other)
        db.session.commit()
        pharmacy = Pharmacy.query.filter_by(name="Ram Medical").first()
        medicine = Medicine.query.filter_by(name="Dolo 650").first()

        order = OrderService.create_order(customer.id, pharmacy.id, medicine.id, 1, "PICKUP", idempotency_key="regression-key")
        assert OrderService.create_order(customer.id, pharmacy.id, medicine.id, 1, "PICKUP", idempotency_key="regression-key").id == order.id
        with pytest.raises(ValueError, match="different customer"):
            OrderService.create_order(other.id, pharmacy.id, medicine.id, 1, "PICKUP", idempotency_key="regression-key")


def test_customer_cannot_approve_own_prescription(app):
    with app.app_context():
        customer = User.query.filter_by(email="customer@example.com").first()
        pharmacy = Pharmacy.query.filter_by(name="Ram Medical").first()
        rx = Prescription(customer_id=customer.id, pharmacy_id=pharmacy.id, file_path="nonexistent.pdf",
                          original_filename="prescription.pdf", status="PENDING")
        db.session.add(rx)
        db.session.commit()
        with pytest.raises(PermissionError, match="Only pharmacy owners and admins"):
            PrescriptionService.review_prescription(rx.id, customer, "APPROVED")
        db.session.refresh(rx)
        assert rx.status == "PENDING"


def test_rx_delivery_requires_review_before_confirmation(app):
    with app.app_context():
        customer = User.query.filter_by(email="customer@example.com").first()
        pharmacy = Pharmacy.query.filter_by(name="Ram Medical").first()
        medicine = Medicine.query.filter_by(name="Mox 500").first()
        inventory = PharmacyInventory.query.filter_by(pharmacy_id=pharmacy.id, medicine_id=medicine.id).first()
        assert inventory.quantity >= 1
        rx = Prescription(customer_id=customer.id, pharmacy_id=pharmacy.id, file_path="nonexistent.pdf",
                          original_filename="prescription.pdf", status="PENDING")
        db.session.add(rx)
        db.session.commit()
        order = OrderService.create_order(customer.id, pharmacy.id, medicine.id, 1, "DELIVERY",
                                          delivery_address="Test delivery address", prescription_id=rx.id)
        OrderService.update_order_status(order.id, pharmacy.owner_id, "pharmacy", "ACCEPTED")
        with pytest.raises(ValueError, match="Prescription must be approved"):
            OrderService.update_order_status(order.id, pharmacy.owner_id, "pharmacy", "CONFIRMED")
        assert inventory.quantity >= 1
        rx.status = "APPROVED"
        db.session.commit()
        OrderService.update_order_status(order.id, pharmacy.owner_id, "pharmacy", "CONFIRMED")
        assert order.status == "CONFIRMED"


def test_retry_key_rejects_different_order_payload(app):
    with app.app_context():
        customer = User.query.filter_by(email='customer@example.com').first()
        pharmacy = Pharmacy.query.filter_by(name='Ram Medical').first()
        medicine = Medicine.query.filter_by(name='Dolo 650').first()
        OrderService.create_order(customer.id, pharmacy.id, medicine.id, 1, 'PICKUP',
                                  idempotency_key='payload-specific-regression')
        with pytest.raises(ValueError, match='different order'):
            OrderService.create_order(customer.id, pharmacy.id, medicine.id, 2, 'PICKUP',
                                      idempotency_key='payload-specific-regression')


def test_rejected_prescription_cannot_be_reused(app):
    with app.app_context():
        customer = User.query.filter_by(email='customer@example.com').first()
        pharmacy = Pharmacy.query.filter_by(name='Ram Medical').first()
        medicine = Medicine.query.filter_by(name='Mox 500').first()
        rx = Prescription(customer_id=customer.id, pharmacy_id=pharmacy.id,
                          file_path='test.pdf', original_filename='test.pdf', status='REJECTED')
        db.session.add(rx)
        db.session.commit()
        with pytest.raises(ValueError, match='Rejected prescriptions'):
            OrderService.create_order(customer.id, pharmacy.id, medicine.id, 1, 'PICKUP',
                                      prescription_id=rx.id)


def test_pharmacy_registration_without_location_does_not_invent_bangalore(app):
    with app.test_client() as client:
        response = client.post('/api/auth/register-pharmacy', json={
            'full_name': 'New Owner', 'email': 'no-location-owner@example.com',
            'password': 'strongpass123', 'confirm_password': 'strongpass123',
            'pharmacy_name': 'No Location Chemist', 'license_number': 'NL-CHEM-2026',
            'address': 'Main Road', 'city': 'Surat', 'state': 'Gujarat', 'pincode': '395001'
        })
        assert response.status_code == 201, response.get_json()
        pharmacy = Pharmacy.query.filter_by(name='No Location Chemist').first()
        assert pharmacy.latitude is None and pharmacy.longitude is None


def test_pharmacy_registration_rejects_bad_coordinates(app):
    with app.test_client() as client:
        response = client.post('/api/auth/register-pharmacy', json={
            'full_name': 'Invalid Owner', 'email': 'bad-location-owner@example.com',
            'password': 'strongpass123', 'confirm_password': 'strongpass123',
            'pharmacy_name': 'Invalid Location Chemist', 'license_number': 'INVALID-CHEM-2026',
            'address': 'Main Road', 'city': 'Surat', 'state': 'Gujarat', 'pincode': '395001',
            'latitude': 'not-a-number', 'longitude': 72.83
        })
        assert response.status_code == 400


def test_pharmacy_account_cannot_place_customer_order(app):
    with app.app_context():
        pharmacy = Pharmacy.query.filter_by(name='Ram Medical').first()
        owner = db.session.get(User, pharmacy.owner_id)
        medicine = Medicine.query.filter_by(name='Dolo 650').first()
        with app.test_client() as client:
            client.post('/api/auth/login', json={'email': owner.email, 'password': 'pharmacy123'})
            response = client.post('/api/orders/pickup', json={
                'pharmacy_id': pharmacy.id, 'medicine_id': medicine.id, 'quantity': 1
            })
            assert response.status_code == 403


def test_inventory_rejects_negative_or_nonfinite_price(app):
    from backend.services.inventory_service import InventoryService
    with app.app_context():
        pharmacy = Pharmacy.query.filter_by(name='Ram Medical').first()
        medicine = Medicine.query.filter_by(name='Dolo 650').first()
        for price in (-1, float('nan'), float('inf')):
            with pytest.raises(ValueError, match='Price'):
                InventoryService.update_inventory(pharmacy.id, medicine.id, quantity=1, price=price)


def test_delivery_pharmacy_listing_rejects_invalid_quantities(app):
    with app.test_client() as client:
        medicine = Medicine.query.filter_by(name='Dolo 650').first()
        for quantity in ('0', '-1', 'nonsense'):
            response = client.get('/api/orders/delivery-pharmacies', query_string={
                'medicine_id': medicine.id, 'quantity': quantity
            })
            assert response.status_code == 400, (quantity, response.get_json())
