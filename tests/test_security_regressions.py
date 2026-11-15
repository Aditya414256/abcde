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
