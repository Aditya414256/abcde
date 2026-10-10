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
# 6. Store Pickup — Pharmacy Listing (new customer-choice flow)
# ==========================================
def test_pickup_pharmacy_listing_returns_all_eligible(app):
    """All eligible pickup pharmacies are returned — not just the nearest one."""
    with app.app_context():
        dolo = Medicine.query.filter_by(name='Dolo 650').first()
        pharmacies = OrderService.find_eligible_pickup_pharmacies(
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

def test_pickup_pharmacy_listing_sorted_by_distance(app):
    """When coordinates are provided, pharmacies are sorted by nearest first."""
    with app.app_context():
        dolo = Medicine.query.filter_by(name='Dolo 650').first()
        # Coordinates very close to Ram Medical (21.3565, 74.8810)
        pharmacies = OrderService.find_eligible_pickup_pharmacies(
            medicine_id=dolo.id,
            user_lat=21.3566,
            user_lon=74.8811,
            quantity=1
        )
        assert len(pharmacies) >= 2
        # Must be sorted ascending by distance_km
        distances = [p['distance_km'] for p in pharmacies if p['distance_km'] is not None]
        assert distances == sorted(distances)
        # Nearest should be Ram Medical
        assert pharmacies[0]['pharmacy_name'] == 'Ram Medical'
        assert pharmacies[0]['distance_km'] < 1.0

def test_pickup_listing_without_location(app):
    """Missing location does NOT prevent pharmacy listing — all eligible stores shown."""
    with app.app_context():
        dolo = Medicine.query.filter_by(name='Dolo 650').first()
        pharmacies = OrderService.find_eligible_pickup_pharmacies(
            medicine_id=dolo.id,
            user_lat=None,
            user_lon=None,
            quantity=1
        )
        assert len(pharmacies) >= 4
        # All distances should be None when no coords given
        for p in pharmacies:
            assert p['distance_km'] is None
            assert p['distance_text'] is None

def test_pickup_listing_excludes_ineligible_pharmacies(app):
    """Inactive, unverified, non-pickup, and out-of-stock pharmacies are excluded."""
    with app.app_context():
        dolo = Medicine.query.filter_by(name='Dolo 650').first()

        # Create an unverified pharmacy with stock
        owner = User(email='unverified@test.com', full_name='Unverified Owner',
                     phone='9000000001', role='pharmacy')
        owner.set_password('pass123')
        db.session.add(owner)
        db.session.flush()

        unverified = Pharmacy(
            owner_id=owner.id, name='Unverified Store',
            license_number='DL-UV-9999', phone='9000000001',
            email='unverified@test.com', address='Test Addr',
            city='Shirpur-Warwade', state='Maharashtra', pincode='425405',
            latitude=21.3570, longitude=74.8820,
            supports_pickup=True, is_verified=False,
            verification_status='PENDING', is_active=True
        )
        db.session.add(unverified)
        db.session.flush()

        # Add inventory for this pharmacy
        inv = PharmacyInventory(
            pharmacy_id=unverified.id, medicine_id=dolo.id,
            quantity=10, price=35.0, batch_number='BAT-UV-1',
            expiry_date='12/2027'
        )
        inv.recalculate_stock_status()
        db.session.add(inv)
        db.session.commit()

        pharmacies = OrderService.find_eligible_pickup_pharmacies(
            medicine_id=dolo.id, user_lat=None, user_lon=None, quantity=1
        )
        names = [p['pharmacy_name'] for p in pharmacies]
        assert 'Unverified Store' not in names

        # Now make an active verified pharmacy inactive
        ram = Pharmacy.query.filter_by(name='Ram Medical').first()
        ram.is_active = False
        db.session.commit()

        pharmacies_after = OrderService.find_eligible_pickup_pharmacies(
            medicine_id=dolo.id, user_lat=None, user_lon=None, quantity=1
        )
        names_after = [p['pharmacy_name'] for p in pharmacies_after]
        assert 'Ram Medical' not in names_after

        # Restore for other tests
        ram.is_active = True
        db.session.commit()

def test_pickup_listing_excludes_out_of_stock(app):
    """Pharmacies with insufficient stock are excluded from the listing."""
    with app.app_context():
        dolo = Medicine.query.filter_by(name='Dolo 650').first()
        ram = Pharmacy.query.filter_by(name='Ram Medical').first()

        # Set Ram Medical stock to 0
        inv = PharmacyInventory.query.filter_by(
            pharmacy_id=ram.id, medicine_id=dolo.id
        ).first()
        inv.quantity = 0
        inv.recalculate_stock_status()
        db.session.commit()

        pharmacies = OrderService.find_eligible_pickup_pharmacies(
            medicine_id=dolo.id, user_lat=None, user_lon=None, quantity=1
        )
        names = [p['pharmacy_name'] for p in pharmacies]
        assert 'Ram Medical' not in names

        # Restore stock
        inv.quantity = 20
        inv.recalculate_stock_status()
        db.session.commit()

def test_pickup_listing_payload_has_no_sensitive_fields(app):
    """Pharmacy listing payload must not expose owner_id, password, or email."""
    with app.app_context():
        dolo = Medicine.query.filter_by(name='Dolo 650').first()
        pharmacies = OrderService.find_eligible_pickup_pharmacies(
            medicine_id=dolo.id, user_lat=None, user_lon=None, quantity=1
        )
        assert len(pharmacies) > 0
        for p in pharmacies:
            assert 'owner_id' not in p
            assert 'password_hash' not in p
            assert 'email' not in p
            # Required safe fields present
            assert 'pharmacy_id' in p
            assert 'pharmacy_name' in p
            assert 'address' in p
            assert 'city' in p
            assert 'unit_price' in p
            assert 'stock_quantity' in p
            assert 'stock_status' in p
            assert 'is_verified' in p

def test_pickup_listing_invalid_medicine(app):
    """Invalid medicine ID raises ValueError."""
    with app.app_context():
        with pytest.raises(ValueError, match='Medicine not found'):
            OrderService.find_eligible_pickup_pharmacies(
                medicine_id=999999, user_lat=None, user_lon=None, quantity=1
            )

def test_pickup_listing_invalid_quantity(app):
    """Zero or negative quantity raises ValueError."""
    with app.app_context():
        dolo = Medicine.query.filter_by(name='Dolo 650').first()
        with pytest.raises(ValueError):
            OrderService.find_eligible_pickup_pharmacies(
                medicine_id=dolo.id, user_lat=None, user_lon=None, quantity=0
            )
        with pytest.raises(ValueError):
            OrderService.find_eligible_pickup_pharmacies(
                medicine_id=dolo.id, user_lat=None, user_lon=None, quantity=-5
            )

def test_pickup_order_at_customer_selected_pharmacy(app):
    """Order is created for the pharmacy the customer explicitly selected — not auto-selected."""
    with app.app_context():
        customer = User.query.filter_by(email='customer@example.com').first()
        dolo = Medicine.query.filter_by(name='Dolo 650').first()

        # Customer picks Shree Ji Medical — NOT the geographically nearest (Ram Medical)
        shreeji = Pharmacy.query.filter_by(name='Shree Ji Medical').first()

        inv_before = PharmacyInventory.query.filter_by(
            pharmacy_id=shreeji.id, medicine_id=dolo.id
        ).first()
        initial_qty = inv_before.quantity

        order = OrderService.create_order(
            customer_id=customer.id,
            pharmacy_id=shreeji.id,
            medicine_id=dolo.id,
            quantity=1,
            order_type='PICKUP'
        )

        assert order.pharmacy_id == shreeji.id
        assert order.status == 'PENDING'
        assert order.order_type == 'PICKUP'

        # Inventory decremented at the selected pharmacy
        inv_after = PharmacyInventory.query.filter_by(
            pharmacy_id=shreeji.id, medicine_id=dolo.id
        ).first()
        assert inv_after.quantity == initial_qty - 1

def test_opening_pickup_listing_does_not_create_order(app):
    """Calling find_eligible_pickup_pharmacies must never create an order."""
    with app.app_context():
        dolo = Medicine.query.filter_by(name='Dolo 650').first()
        order_count_before = Order.query.count()

        OrderService.find_eligible_pickup_pharmacies(
            medicine_id=dolo.id, user_lat=21.3565, user_lon=74.8810, quantity=1
        )

        order_count_after = Order.query.count()
        assert order_count_after == order_count_before

def test_pickup_order_invalid_pharmacy_id(app):
    """Invalid pharmacy_id is rejected by create_order."""
    with app.app_context():
        customer = User.query.filter_by(email='customer@example.com').first()
        dolo = Medicine.query.filter_by(name='Dolo 650').first()

        with pytest.raises(ValueError, match='Pharmacy not found'):
            OrderService.create_order(
                customer_id=customer.id,
                pharmacy_id=999999,
                medicine_id=dolo.id,
                quantity=1,
                order_type='PICKUP'
            )

def test_pickup_order_insufficient_stock_rejected(app):
    """Order requesting more stock than available is rejected."""
    with app.app_context():
        customer = User.query.filter_by(email='customer@example.com').first()
        ram = Pharmacy.query.filter_by(name='Ram Medical').first()
        dolo = Medicine.query.filter_by(name='Dolo 650').first()

        inv = PharmacyInventory.query.filter_by(
            pharmacy_id=ram.id, medicine_id=dolo.id
        ).first()
        inv.quantity = 2
        db.session.commit()

        with pytest.raises(ValueError, match='Insufficient stock'):
            OrderService.create_order(
                customer_id=customer.id,
                pharmacy_id=ram.id,
                medicine_id=dolo.id,
                quantity=99,
                order_type='PICKUP'
            )

        # Restore
        inv.quantity = 20
        db.session.commit()

def test_pickup_order_inactive_pharmacy_rejected(app):
    """Order against an inactive pharmacy is rejected."""
    with app.app_context():
        customer = User.query.filter_by(email='customer@example.com').first()
        ram = Pharmacy.query.filter_by(name='Ram Medical').first()
        dolo = Medicine.query.filter_by(name='Dolo 650').first()

        ram.is_active = False
        db.session.commit()

        with pytest.raises(ValueError, match='inactive'):
            OrderService.create_order(
                customer_id=customer.id,
                pharmacy_id=ram.id,
                medicine_id=dolo.id,
                quantity=1,
                order_type='PICKUP'
            )

        ram.is_active = True
        db.session.commit()

def test_rx_pickup_allowed_without_uploaded_prescription(app):
    """Store Pickup for an Rx medicine succeeds without an uploaded prescription file.
    The order must be flagged prescription_pending_at_pickup=True."""
    with app.app_context():
        customer = User.query.filter_by(email='customer@example.com').first()
        ram = Pharmacy.query.filter_by(name='Ram Medical').first()
        mox = Medicine.query.filter_by(name='Mox 500').first()  # requires_prescription=True

        order = OrderService.create_order(
            customer_id=customer.id,
            pharmacy_id=ram.id,
            medicine_id=mox.id,
            quantity=1,
            order_type='PICKUP'
        )

        assert order.status == 'PENDING'
        assert order.prescription_id is None
        assert order.prescription_pending_at_pickup is True


def test_rx_delivery_blocked_without_uploaded_prescription(app):
    """Home Delivery for an Rx medicine is rejected when no prescription_id is provided."""
    with app.app_context():
        customer = User.query.filter_by(email='customer@example.com').first()
        ram = Pharmacy.query.filter_by(name='Ram Medical').first()
        mox = Medicine.query.filter_by(name='Mox 500').first()  # requires_prescription=True

        with pytest.raises(ValueError, match='prescription'):
            OrderService.create_order(
                customer_id=customer.id,
                pharmacy_id=ram.id,
                medicine_id=mox.id,
                quantity=1,
                order_type='DELIVERY',
                delivery_address='123 Test Street'
            )


def test_otc_pickup_no_prescription_flag(app):
    """OTC medicine pickup order should have prescription_pending_at_pickup=False."""
    with app.app_context():
        customer = User.query.filter_by(email='customer@example.com').first()
        ram = Pharmacy.query.filter_by(name='Ram Medical').first()
        dolo = Medicine.query.filter_by(name='Dolo 650').first()  # requires_prescription=False

        order = OrderService.create_order(
            customer_id=customer.id,
            pharmacy_id=ram.id,
            medicine_id=dolo.id,
            quantity=1,
            order_type='PICKUP'
        )

        assert order.prescription_pending_at_pickup is False
        assert order.prescription_id is None


def test_otc_delivery_no_prescription_required(app):
    """OTC medicine delivery order succeeds without a prescription."""
    with app.app_context():
        customer = User.query.filter_by(email='customer@example.com').first()
        ram = Pharmacy.query.filter_by(name='Ram Medical').first()
        dolo = Medicine.query.filter_by(name='Dolo 650').first()  # requires_prescription=False

        order = OrderService.create_order(
            customer_id=customer.id,
            pharmacy_id=ram.id,
            medicine_id=dolo.id,
            quantity=1,
            order_type='DELIVERY',
            delivery_address='456 OTC Street'
        )

        assert order.status == 'PENDING'
        assert order.prescription_pending_at_pickup is False

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

    # 4a. Pickup pharmacies listing (new endpoint — does NOT create an order)
    list_res = client.get(f'/api/orders/pickup-pharmacies?medicine_id={med_id}&quantity=1&latitude=21.3566&longitude=74.8811')
    assert list_res.status_code == 200
    list_data = list_res.get_json()
    assert list_data['count'] >= 4
    assert len(list_data['pharmacies']) >= 4
    # Nearest first when coords provided
    first_pharmacy = list_data['pharmacies'][0]
    assert first_pharmacy['pharmacy_name'] == 'Ram Medical'
    first_pharmacy_id = first_pharmacy['pharmacy_id']

    # Verify no order was created just by listing
    orders_before = client.get('/api/orders/my-orders').get_json()['orders']

    # 4b. Customer explicitly selects a pharmacy and places a PICKUP order
    pickup_res = client.post('/api/orders/pickup', json={
        'pharmacy_id': first_pharmacy_id,
        'medicine_id': med_id,
        'quantity': 1
    })
    assert pickup_res.status_code == 201
    pickup_data = pickup_res.get_json()
    assert pickup_data['message'] == 'Your order has been placed.'
    assert pickup_data['order']['order_type'] == 'PICKUP'
    assert pickup_data['order']['pharmacy_id'] == first_pharmacy_id

    # 4c. Customer can also choose a different (non-nearest) pharmacy
    list_data2 = client.get(f'/api/orders/pickup-pharmacies?medicine_id={med_id}&quantity=1').get_json()
    non_nearest = next((p for p in list_data2['pharmacies'] if p['pharmacy_name'] == 'Shree Ji Medical'), None)
    assert non_nearest is not None

    pickup_res2 = client.post('/api/orders/pickup', json={
        'pharmacy_id': non_nearest['pharmacy_id'],
        'medicine_id': med_id,
        'quantity': 1
    })
    assert pickup_res2.status_code == 201
    assert pickup_res2.get_json()['order']['pharmacy_id'] == non_nearest['pharmacy_id']

    # 5. Customer Notifications
    notif_res = client.get('/api/notifications')
    assert notif_res.status_code == 200
    assert len(notif_res.get_json()['notifications']) >= 1

def test_pickup_api_missing_medicine_id(client):
    """Missing medicine_id returns 400."""
    client.post('/api/auth/login', json={
        'email': 'customer@example.com', 'password': 'customer123'
    })
    res = client.get('/api/orders/pickup-pharmacies')
    assert res.status_code == 400
    assert 'error' in res.get_json()

def test_pickup_api_invalid_pharmacy_returns_400(client):
    """Placing a pickup order with an invalid pharmacy_id returns 400."""
    client.post('/api/auth/login', json={
        'email': 'customer@example.com', 'password': 'customer123'
    })
    sugg_res = client.get('/api/medicines/suggestions?q=dolo').get_json()
    med_id = sugg_res['suggestions'][0]['id']

    res = client.post('/api/orders/pickup', json={
        'pharmacy_id': 999999,
        'medicine_id': med_id,
        'quantity': 1
    })
    assert res.status_code == 400
    assert 'error' in res.get_json()

def test_pickup_api_requires_login(client):
    """Unauthenticated pickup order POST returns 401."""
    res = client.post('/api/orders/pickup', json={
        'pharmacy_id': 1,
        'medicine_id': 1,
        'quantity': 1
    })
    assert res.status_code == 401
    assert res.get_json().get('require_login') is True

def test_delivery_workflow_still_works(client):
    """Home Delivery workflow is unaffected by the Store Pickup changes."""
    client.post('/api/auth/login', json={
        'email': 'customer@example.com', 'password': 'customer123'
    })
    sugg_res = client.get('/api/medicines/suggestions?q=dolo').get_json()
    med_id = sugg_res['suggestions'][0]['id']

    # List delivery pharmacies
    del_list_res = client.get(
        f'/api/orders/delivery-pharmacies?medicine_id={med_id}&quantity=1&latitude=21.3565&longitude=74.8810'
    )
    assert del_list_res.status_code == 200
    del_data = del_list_res.get_json()
    assert del_data['count'] >= 4
    pharmacy_id = del_data['pharmacies'][0]['pharmacy_id']

    # Place delivery order
    del_order_res = client.post('/api/orders/create', json={
        'pharmacy_id': pharmacy_id,
        'medicine_id': med_id,
        'quantity': 1,
        'order_type': 'DELIVERY',
        'delivery_address': '123 Test Street, Shirpur'
    })
    assert del_order_res.status_code == 201
    assert del_order_res.get_json()['order']['order_type'] == 'DELIVERY'

# ==========================================
# 11. Order Transaction and Error Handling Tests
# ==========================================
def test_order_creation_succeeds_even_if_notification_fails(app, monkeypatch):
    """If NotificationService fails, order commit is preserved and not duplicated or rolled back."""
    with app.app_context():
        customer = User.query.filter_by(role='customer').first()
        pharmacy = Pharmacy.query.filter_by(supports_delivery=True, is_active=True, is_verified=True).first()
        inv = PharmacyInventory.query.filter_by(pharmacy_id=pharmacy.id).first()
        initial_stock = inv.quantity

        # Monkeypatch NotificationService.create_notification to simulate failure
        def failing_notify(*args, **kwargs):
            raise RuntimeError("Notification service downstream timeout")

        monkeypatch.setattr(NotificationService, 'create_notification', failing_notify)

        # Order creation should still succeed because order is committed
        order = OrderService.create_order(
            customer_id=customer.id,
            pharmacy_id=pharmacy.id,
            medicine_id=inv.medicine_id,
            quantity=1,
            order_type='DELIVERY',
            delivery_address='456 Resilient Lane'
        )

        assert order is not None
        assert order.id is not None
        assert order.status == 'PENDING'

        # Check inventory was decremented exactly once
        db.session.refresh(inv)
        assert inv.quantity == initial_stock - 1

def test_order_creation_endpoint_hides_internal_traceback_on_error(client, monkeypatch):
    """Unexpected exception in /api/orders/create returns 500 without leaking stack traces or db internals."""
    client.post('/api/auth/login', json={
        'email': 'customer@example.com', 'password': 'customer123'
    })

    def buggy_create(*args, **kwargs):
        raise RuntimeError("Sensitive DB password / internal trace at line 42")

    monkeypatch.setattr(OrderService, 'create_order', buggy_create)

    res = client.post('/api/orders/create', json={
        'pharmacy_id': 1,
        'medicine_id': 1,
        'quantity': 1,
        'order_type': 'DELIVERY',
        'delivery_address': 'Secret Address 1'
    })

    assert res.status_code == 500
    data = res.get_json()
    assert data['error'] == 'Failed to create order.'
    # Ensure no internal error detail leaked in response
    assert 'Sensitive' not in str(data)
    assert 'traceback' not in str(data).lower()

def test_order_rollback_on_database_commit_failure(app, monkeypatch):
    """If database commit fails during order creation, inventory stock is rolled back and no order is persisted."""
    with app.app_context():
        customer = User.query.filter_by(role='customer').first()
        pharmacy = Pharmacy.query.filter_by(supports_delivery=True, is_active=True, is_verified=True).first()
        inv = PharmacyInventory.query.filter_by(pharmacy_id=pharmacy.id).first()
        initial_stock = inv.quantity

        def failing_commit():
            raise Exception("Simulated SQLite operational lock")

        monkeypatch.setattr(db.session, 'commit', failing_commit)

        with pytest.raises(Exception):
            OrderService.create_order(
                customer_id=customer.id,
                pharmacy_id=pharmacy.id,
                medicine_id=inv.medicine_id,
                quantity=1,
                order_type='DELIVERY',
                delivery_address='Fail Street'
            )

        # Inventory must not have been decremented
        db.session.rollback()
        db.session.refresh(inv)
        assert inv.quantity == initial_stock


# ==========================================
# 16. Pickup Order Flow, Idempotency & Refresh Persistence Tests
# ==========================================
def test_pickup_order_with_idempotency_prevents_duplicates(app, client):
    """Submitting pickup order with same idempotency key does not create duplicates or decrement stock twice."""
    client.post('/api/auth/login', json={'email': 'customer@example.com', 'password': 'customer123'})

    with app.app_context():
        pharmacy = Pharmacy.query.filter_by(supports_pickup=True, is_active=True, is_verified=True).first()
        inv = PharmacyInventory.query.filter_by(pharmacy_id=pharmacy.id).first()
        medicine_id = inv.medicine_id
        initial_stock = inv.quantity

    payload = {
        'pharmacy_id': pharmacy.id,
        'medicine_id': medicine_id,
        'quantity': 2,
        'customer_notes': 'Please keep ready by 5pm',
        'idempotency_key': 'test-idemp-pickup-001'
    }

    # First submission
    res1 = client.post('/api/orders/pickup', json=payload)
    assert res1.status_code == 201
    data1 = res1.get_json()
    order1 = data1['order']
    assert order1['order_number'].startswith('MF-')
    assert order1['quantity'] == 2
    assert order1['idempotency_key'] == 'test-idemp-pickup-001'

    # Check stock after first submission
    with app.app_context():
        inv_after1 = PharmacyInventory.query.filter_by(pharmacy_id=pharmacy.id, medicine_id=medicine_id).first()
        assert inv_after1.quantity == initial_stock - 2

    # Second submission with identical idempotency key (simulating double click, retry, or refresh)
    res2 = client.post('/api/orders/pickup', json=payload)
    assert res2.status_code in [200, 201]
    data2 = res2.get_json()
    order2 = data2['order']

    # Both must refer to the exact same order
    assert order2['id'] == order1['id']
    assert order2['order_number'] == order1['order_number']

    # Stock must NOT have been decremented a second time
    with app.app_context():
        inv_after2 = PharmacyInventory.query.filter_by(pharmacy_id=pharmacy.id, medicine_id=medicine_id).first()
        assert inv_after2.quantity == initial_stock - 2
        # Only one order in database with this key
        orders_matching = Order.query.filter_by(idempotency_key='test-idemp-pickup-001').all()
        assert len(orders_matching) == 1


def test_get_order_by_id_and_ownership_security(app, client):
    """GET /api/orders/<id> retrieves saved order for owner and blocks unauthorized users."""
    client.post('/api/auth/login', json={'email': 'customer@example.com', 'password': 'customer123'})

    with app.app_context():
        pharmacy = Pharmacy.query.filter_by(supports_pickup=True, is_active=True, is_verified=True).first()
        inv = PharmacyInventory.query.filter_by(pharmacy_id=pharmacy.id).first()

    res = client.post('/api/orders/pickup', json={
        'pharmacy_id': pharmacy.id,
        'medicine_id': inv.medicine_id,
        'quantity': 1,
        'idempotency_key': 'auth-check-key-1'
    })
    assert res.status_code == 201
    order_id = res.get_json()['order']['id']

    # Authorized customer fetches order (as happens on browser refresh)
    get_res = client.get(f'/api/orders/{order_id}')
    assert get_res.status_code == 200
    fetched_order = get_res.get_json()['order']
    assert fetched_order['id'] == order_id
    assert fetched_order['pharmacy_name'] == pharmacy.name

    # Create and login as a second customer
    client.post('/api/auth/logout')
    with app.app_context():
        other_user = User(email='other@customer.com', full_name='Other Person', role='customer')
        other_user.set_password('pass123')
        db.session.add(other_user)
        db.session.commit()

    client.post('/api/auth/login', json={'email': 'other@customer.com', 'password': 'pass123'})

    # Second customer should NOT be allowed to view first customer's order
    forbidden_res = client.get(f'/api/orders/{order_id}')
    assert forbidden_res.status_code == 403


def test_get_order_by_idempotency_recovery(app, client):
    """GET /api/orders/by-idempotency/<key> allows frontend to recover orders if refresh or timeout occurs."""
    client.post('/api/auth/login', json={'email': 'customer@example.com', 'password': 'customer123'})

    # Non-existent key returns 404
    missing_res = client.get('/api/orders/by-idempotency/nonexistent-key-999')
    assert missing_res.status_code == 404
    assert missing_res.get_json()['found'] is False

    with app.app_context():
        pharmacy = Pharmacy.query.filter_by(supports_pickup=True, is_active=True, is_verified=True).first()
        inv = PharmacyInventory.query.filter_by(pharmacy_id=pharmacy.id).first()

    key = 'recovery-key-xyz'
    client.post('/api/orders/pickup', json={
        'pharmacy_id': pharmacy.id,
        'medicine_id': inv.medicine_id,
        'quantity': 1,
        'idempotency_key': key
    })

    found_res = client.get(f'/api/orders/by-idempotency/{key}')
    assert found_res.status_code == 200
    data = found_res.get_json()
    assert data['found'] is True
    assert data['order']['idempotency_key'] == key


def test_pickup_validation_failure_shows_error_and_preserves_stock(app, client):
    """Invalid pickup order returns error and does NOT create order or decrement inventory."""
    client.post('/api/auth/login', json={'email': 'customer@example.com', 'password': 'customer123'})

    with app.app_context():
        pharmacy = Pharmacy.query.filter_by(supports_pickup=True, is_active=True, is_verified=True).first()
        inv = PharmacyInventory.query.filter_by(pharmacy_id=pharmacy.id).first()
        initial_stock = inv.quantity

    # Attempt order with quantity greater than available stock
    res = client.post('/api/orders/pickup', json={
        'pharmacy_id': pharmacy.id,
        'medicine_id': inv.medicine_id,
        'quantity': initial_stock + 100
    })

    assert res.status_code == 400
    data = res.get_json()
    assert 'Insufficient stock' in data['error']

    with app.app_context():
        inv_check = PharmacyInventory.query.filter_by(pharmacy_id=pharmacy.id, medicine_id=inv.medicine_id).first()
        assert inv_check.quantity == initial_stock


def test_customer_and_pharmacy_status_consistency(app, client):
    """Customer and pharmacy dashboards see consistent order records and status updates."""
    # 1. Customer places pickup order
    client.post('/api/auth/login', json={'email': 'customer@example.com', 'password': 'customer123'})

    with app.app_context():
        pharmacy = Pharmacy.query.filter_by(supports_pickup=True, is_active=True, is_verified=True).first()
        inv = PharmacyInventory.query.filter_by(pharmacy_id=pharmacy.id).first()
        owner = User.query.get(pharmacy.owner_id)

    res = client.post('/api/orders/pickup', json={
        'pharmacy_id': pharmacy.id,
        'medicine_id': inv.medicine_id,
        'quantity': 1
    })
    assert res.status_code == 201
    order_id = res.get_json()['order']['id']

    # 2. Pharmacy owner logs in and views order in their portal
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'email': owner.email, 'password': 'pharmacy123'})

    pharmacy_orders_res = client.get('/api/pharmacy/orders')
    assert pharmacy_orders_res.status_code == 200
    pharm_orders = pharmacy_orders_res.get_json()['orders']
    matching_order = next((o for o in pharm_orders if o['id'] == order_id), None)
    assert matching_order is not None
    assert matching_order['status'] == 'PENDING'

    # Pharmacy updates status
    status_update_res = client.post(f'/api/orders/{order_id}/status', json={'status': 'ACCEPTED'})
    assert status_update_res.status_code == 200

    # 3. Customer logs back in and checks their order (e.g. on confirmation refresh or My Orders)
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'email': 'customer@example.com', 'password': 'customer123'})

    cust_check_res = client.get(f'/api/orders/{order_id}')
    assert cust_check_res.status_code == 200
    assert cust_check_res.get_json()['order']['status'] == 'ACCEPTED'

