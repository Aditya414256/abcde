"""Reproductions of the audit failures and complete owner/customer API flows."""
import io
import pytest
from backend.app import create_app
from backend.config import Config
from backend.database import db
from backend.models import User, Order, PharmacyInventory


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'UPLOAD_FOLDER', str(tmp_path / 'prescriptions'))
    monkeypatch.setattr(Config, 'SUPABASE_URL', None)
    class C:
        TESTING = True
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SECRET_KEY = 'audit-test-only'
    app = create_app(C)
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def login(client, role='customer'):
    credentials = {'customer': ('customer@example.com', 'customer123'),
                   'pharmacy': ('ram@pharmacy.com', 'pharmacy123'),
                   'admin': ('admin@medifind.com', 'admin123')}
    email, password = credentials[role]
    assert client.post('/api/auth/login', json={'email':email, 'password':password}).status_code == 200


def registration(**changes):
    data = dict(full_name='Audit Owner', email='audit@example.test', password='password123',
                confirm_password='password123', pharmacy_name="Patil's Pharmacy",
                license_number='AUDIT-001', address='Main road', city='Surat',
                state='Gujarat', pincode='395001')
    return dict(data, **changes)


@pytest.mark.parametrize('body', [[], ['bad'], {'full_name':None}, {'full_name':7},
                                  {'email':{}}, {'password':['bad']}])
def test_bad_registration_is_400(app, body):
    r = app.test_client().post('/api/auth/register/customer', json=body)
    assert r.status_code == 400
    assert r.is_json


def test_pharmacy_password_policy_and_partial_coordinates(app):
    c=app.test_client()
    assert c.post('/api/auth/register-pharmacy',json=registration(password='x',confirm_password='x')).status_code==400
    assert c.post('/api/auth/register-pharmacy',json=registration(latitude=21)).status_code==400
    with app.app_context():
        assert User.query.filter_by(email='audit@example.test').first() is None


def test_profile_patch_preserves_phone_and_failed_password_is_atomic(app):
    c=app.test_client();login(c)
    c.patch('/api/auth/profile',json={'phone':'9999999999'})
    r=c.patch('/api/auth/profile',json={'full_name':'Updated Name'})
    assert r.json['user']['phone']=='9999999999'
    assert c.patch('/api/auth/profile',json={'full_name':'Wrong', 'new_password':'password456',
           'current_password':'wrong','confirm_password':'password456'}).status_code==400
    assert c.get('/api/auth/current-user').json['user']['full_name']=='Updated Name'


def test_new_pharmacy_setup_inventory_document_and_admin_review(app):
    owner=app.test_client();admin=app.test_client();customer=app.test_client()
    r=owner.post('/api/auth/register-pharmacy',json=registration())
    assert r.status_code==201
    pid=r.json['pharmacy']['id']
    assert owner.get('/api/pharmacy/inventory').json['inventory']==[]
    r=owner.patch('/api/pharmacy/profile',json={'latitude':0,'longitude':72.83,
         'supports_delivery':True,'delivery_fee':25})
    assert r.status_code==200 and r.json['pharmacy']['latitude']==0
    assert owner.patch('/api/pharmacy/profile',json={'latitude':float('nan'),'longitude':73}).status_code==400
    assert owner.post('/api/pharmacy/inventory',json={'medicine_id':1,'quantity':5,'price':25}).status_code==200
    assert len(owner.get('/api/pharmacy/inventory').json['inventory'])==1
    r=owner.post('/api/pharmacy/verification-doc',data={'file':(io.BytesIO(b'%PDF-1.4 audit'), 'license.pdf')})
    assert r.status_code==200
    assert owner.get('/api/pharmacy/verification-doc').status_code==200
    login(admin,'admin');login(customer)
    assert admin.get(f'/api/pharmacy/verification-doc?pharmacy_id={pid}').status_code==200
    assert customer.get(f'/api/pharmacy/verification-doc?pharmacy_id={pid}').status_code==403
    assert customer.patch('/api/pharmacy/profile',json={'latitude':1,'longitude':1}).status_code==403
    assert admin.post(f'/api/admin/pharmacies/{pid}/verify',json={'action':'approve'}).status_code==200
    listed=customer.get('/api/orders/delivery-pharmacies?medicine_id=1&latitude=0&longitude=72.83').json['pharmacies']
    assert next(p for p in listed if p['pharmacy_id']==pid)['distance_km']==0


def test_delivery_retry_confirmation_and_prescription_review(app):
    customer=app.test_client();owner=app.test_client();login(customer);login(owner,'pharmacy')
    rx=customer.post('/api/prescriptions/upload',data={'pharmacy_id':'1',
        'file':(io.BytesIO(b'%PDF-1.4 test prescription'), 'rx.pdf')})
    assert rx.status_code==201
    rxid=rx.json['prescription']['id']
    payload=dict(pharmacy_id=1,medicine_id=5,quantity=1,order_type='DELIVERY',
                 delivery_address='Test address',contact_phone='9999999999',
                 prescription_id=rxid,idempotency_key='audit-delivery-retry')
    first=customer.post('/api/orders/create',json=payload)
    second=customer.post('/api/orders/create',json=payload)
    assert first.status_code==second.status_code==201
    oid=first.json['order']['id']
    assert second.json['order']['id']==oid
    assert customer.get('/api/orders/by-idempotency/audit-delivery-retry').json['order']['id']==oid
    assert owner.post(f'/api/orders/{oid}/status',json={'status':'ACCEPTED'}).status_code==200
    assert owner.post(f'/api/orders/{oid}/status',json={'status':'CONFIRMED'}).status_code==400
    assert customer.post(f'/api/pharmacy/prescriptions/{rxid}/review',json={'status':'APPROVED'}).status_code==403
    assert owner.post(f'/api/pharmacy/prescriptions/{rxid}/review',json={'status':'APPROVED'}).status_code==200
    assert owner.get('/api/pharmacy/orders').json['orders'][0]['prescription_status']=='APPROVED'
    for status in ('CONFIRMED','PREPARING','OUT_FOR_DELIVERY','COMPLETED'):
        assert owner.post(f'/api/orders/{oid}/status',json={'status':status}).status_code==200
    assert owner.post(f'/api/pharmacy/prescriptions/{rxid}/review',json={'status':'REJECTED','notes':'test'}).status_code==400
    assert customer.get(f'/api/orders/{oid}').json['order']['status']=='COMPLETED'
    with app.app_context(): assert Order.query.count()==1


def test_reject_prescription_closes_accepted_delivery_without_stock_deduction(app):
    c=app.test_client();owner=app.test_client();login(c);login(owner,'pharmacy')
    rx=c.post('/api/prescriptions/upload',data={'pharmacy_id':'1',
        'file':(io.BytesIO(b'%PDF-1.4 test'), 'rx.pdf')}).json['prescription']['id']
    with app.app_context(): initial=PharmacyInventory.query.filter_by(pharmacy_id=1,medicine_id=5).first().quantity
    order=c.post('/api/orders/create',json={'medicine_id':5,'pharmacy_id':1,'quantity':1,
        'delivery_address':'test','prescription_id':rx}).json['order']['id']
    owner.post(f'/api/orders/{order}/status',json={'status':'ACCEPTED'})
    assert owner.post(f'/api/pharmacy/prescriptions/{rx}/review',json={'status':'REJECTED','notes':'Unreadable'}).status_code==200
    assert c.get(f'/api/orders/{order}').json['order']['status']=='REJECTED'
    with app.app_context(): assert PharmacyInventory.query.filter_by(pharmacy_id=1,medicine_id=5).first().quantity==initial


@pytest.mark.parametrize('quantity', [1.5, True, [], -1, 2147483648])
def test_invalid_inventory_quantities_are_rejected(app, quantity):
    c=app.test_client();login(c,'pharmacy')
    assert c.post('/api/pharmacy/inventory',json={'medicine_id':1,'quantity':quantity,'price':20}).status_code==400
