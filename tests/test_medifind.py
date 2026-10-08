import pytest
from backend.app import create_app
from backend.database import db
from backend.models import User, Pharmacy, Medicine, PharmacyInventory, Order, Prescription, Notification
from backend.services.location_service import LocationService
from backend.services.medicine_service import MedicineService
from backend.services.pharmacy_service import PharmacyService
from backend.services.inventory_service import InventoryService
from backend.services.order_service import OrderService
from backend.services.prescription_service import PrescriptionService
from backend.services.notification_service import NotificationService
from backend.seed import seed_database

class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret-key'

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        # Seed test data
        seed_database(app)
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

# ==========================================
# 1. Location Service Tests
# ==========================================
def test_haversine_distance():
    # Bangalore MG Road (12.9716, 77.5946) to Indiranagar (12.9784, 77.6408) is ~5.0 km
    dist = LocationService.haversine_distance(12.9716, 77.5946, 12.9784, 77.6408)
    assert dist is not None
    assert 4.0 <= dist <= 6.0
    assert LocationService.format_distance(dist) == f"{dist:.1f} km"
    assert LocationService.format_distance(0.5) == "500 m"
    assert LocationService.haversine_distance(None, None, 12.0, 77.0) is None

# ==========================================
# 2. Medicine Service Tests
# ==========================================
def test_medicine_search_and_suggestions(app):
    with app.app_context():
        # Case insensitive search
        results = MedicineService.search_medicines('dolo')
        assert len(results) >= 1
        assert results[0]['name'] == 'Dolo 650'

        # Generic name search
        generic_results = MedicineService.search_medicines('Paracetamol')
        assert len(generic_results) >= 2

        # Autocomplete suggestions
        sugg = MedicineService.get_suggestions('par')
        assert len(sugg) >= 1
        assert 'name' in sugg[0]
        assert 'generic_name' in sugg[0]

        # Safe against empty or special input
        assert MedicineService.search_medicines('') == []
        assert MedicineService.search_medicines(None) == []

# ==========================================
# 3. Inventory Service & Non-negative constraints
# ==========================================
def test_inventory_business_rules(app):
    with app.app_context():
        ram = Pharmacy.query.filter_by(name='Ram Medical').first()
        med = Medicine.query.filter_by(name='Dolo 650').first()

        # Update to low stock
        inv = InventoryService.update_inventory(ram.id, med.id, quantity=5, price=35.0)
        assert inv.stock_status == 'LOW_STOCK'
        assert inv.quantity == 5

        # Update to out of stock
        inv = InventoryService.update_inventory(ram.id, med.id, quantity=0)
        assert inv.stock_status == 'OUT_OF_STOCK'

        # Negative stock constraint
        with pytest.raises(ValueError):
            InventoryService.update_inventory(ram.id, med.id, quantity=-1)

# ==========================================
# 4. Pharmacy Registration & Admin Verification
# ==========================================
def test_pharmacy_registration_starts_pending(app):
    with app.app_context():
        user = User(email='newstore@test.com', full_name='New Owner', phone='1234567890', role='pharmacy')
        user.set_password('pass123')
        db.session.add(user)
        db.session.commit()

        pharmacy = PharmacyService.register_pharmacy(
            owner_id=user.id,
            name='New Life Pharmacy',
            license_number='DL-NEW-2026-001',
            phone='1234567890',
            email='newstore@test.com',
            address='1st Cross',
            city='Bangalore',
            state='Karnataka',
            pincode='560001'
        )

        assert pharmacy.is_verified is False
        assert pharmacy.verification_status == 'PENDING'

        # Must NOT appear in verified customer list
        verified = PharmacyService.list_verified_pharmacies()
        assert not any(p['name'] == 'New Life Pharmacy' for p in verified)

        # Admin approves verification
        PharmacyService.verify_pharmacy(pharmacy.id, 'APPROVED')
        assert pharmacy.is_verified is True

        # Now appears in verified list
        verified_after = PharmacyService.list_verified_pharmacies()
        assert any(p['name'] == 'New Life Pharmacy' for p in verified_after)

# ==========================================
# 5. Order Service & State Machine
# ==========================================
def test_order_creation_and_stock_decrement(app):
    with app.app_context():
        customer = User.query.filter_by(email='customer@example.com').first()
        ram = Pharmacy.query.filter_by(name='Ram Medical').first()
        dolo = Medicine.query.filter_by(name='Dolo 650').first()

        inv_before = PharmacyInventory.query.filter_by(pharmacy_id=ram.id, medicine_id=dolo.id).first()
        initial_qty = inv_before.quantity

        order = OrderService.create_order(
            customer_id=customer.id,
            pharmacy_id=ram.id,
            medicine_id=dolo.id,
            quantity=2,
            order_type='PICKUP'
        )

        assert order.status == 'PENDING'
        assert order.order_number.startswith('MF-')
        assert order.quantity == 2

        # Verify safe stock decrement
        inv_after = PharmacyInventory.query.filter_by(pharmacy_id=ram.id, medicine_id=dolo.id).first()
        assert inv_after.quantity == initial_qty - 2

        # Test state machine transition: PENDING -> ACCEPTED -> CONFIRMED -> PREPARING -> READY_FOR_PICKUP -> COMPLETED
        OrderService.update_order_status(order.id, ram.owner_id, 'pharmacy', 'ACCEPTED')
        assert order.status == 'ACCEPTED'

        OrderService.update_order_status(order.id, ram.owner_id, 'pharmacy', 'CONFIRMED')
        assert order.status == 'CONFIRMED'

        # Cannot skip state (e.g. directly to COMPLETED from CONFIRMED)
        with pytest.raises(ValueError):
            OrderService.update_order_status(order.id, ram.owner_id, 'pharmacy', 'COMPLETED')

        # Test stock restoration on cancellation
        order_to_cancel = OrderService.create_order(
            customer_id=customer.id,
            pharmacy_id=ram.id,
            medicine_id=dolo.id,
            quantity=3,
            order_type='PICKUP'
        )
        qty_after_order2 = inv_after.quantity
        OrderService.update_order_status(order_to_cancel.id, ram.owner_id, 'pharmacy', 'REJECTED')
        assert inv_after.quantity == qty_after_order2 + 3

# ==========================================
# 6. Store Pickup Auto-Nearest Selection
# ==========================================
def test_auto_nearest_pickup_selection(app):
    with app.app_context():
        dolo = Medicine.query.filter_by(name='Dolo 650').first()
        # Coordinates near Ram Medical in Shirpur (21.3565, 74.8810)
        user_lat = 21.3566
        user_lon = 74.8811

        nearest = OrderService.find_nearest_eligible_pickup_pharmacy(
            medicine_id=dolo.id,
            user_lat=user_lat,
            user_lon=user_lon,
            quantity=1
        )
        assert nearest is not None
        assert nearest['pharmacy'].name == 'Ram Medical'
        assert nearest['distance_km'] < 1.0

# ==========================================
# 7. Delivery Flow & Pharmacy Selection
# ==========================================
def test_delivery_pharmacies_listing(app):
    with app.app_context():
        dolo = Medicine.query.filter_by(name='Dolo 650').first()
        pharmacies = OrderService.find_eligible_delivery_pharmacies(
            medicine_id=dolo.id,
            user_lat=21.3565,
            user_lon=74.8810,
            quantity=1
        )
        assert len(pharmacies) >= 4
        names = [p['pharmacy_name'] for p in pharmacies]
        assert 'Ram Medical' in names
        assert 'Shree Ji Medical' in names
        assert 'Tasir Medical' in names
        assert 'Shree Gangai Medical' in names

# ==========================================
# 8. Full Client API Integration
# ==========================================
def test_client_api_workflow(client):
    # 1. Login as customer
    login_res = client.post('/api/auth/login', json={
        'email': 'customer@example.com',
        'password': 'customer123'
    })
    assert login_res.status_code == 200
    assert login_res.get_json()['redirect_url'] == 'HomePage.html'

    # 2. Check current user
    user_res = client.get('/api/auth/current-user')
    assert user_res.status_code == 200
    assert user_res.get_json()['user']['email'] == 'customer@example.com'

    # 3. Autocomplete API
    sugg_res = client.get('/api/medicines/suggestions?q=dolo')
    assert sugg_res.status_code == 200
    suggestions = sugg_res.get_json()['suggestions']
    assert len(suggestions) > 0
    med_id = suggestions[0]['id']

    # 4. Store Pickup Nearest API (near Shirpur)
    pickup_res = client.post('/api/orders/pickup-nearest', json={
        'medicine_id': med_id,
        'latitude': 21.3566,
        'longitude': 74.8811,
        'quantity': 1
    })
    assert pickup_res.status_code == 201
    assert pickup_res.get_json()['message'] == 'Your order has been placed.'

    # 5. Customer Notifications
    notif_res = client.get('/api/notifications')
    assert notif_res.status_code == 200
    assert len(notif_res.get_json()['notifications']) >= 1
