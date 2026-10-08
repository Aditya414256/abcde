import os
from datetime import datetime
from backend.app import create_app
from backend.database import db
from backend.models import User, Pharmacy, Medicine, PharmacyInventory

def seed_database(app=None):
    if app is None:
        app = create_app()
    with app.app_context():
        # Create all database tables
        db.create_all()

        # Check if already seeded with new data
        if Pharmacy.query.filter_by(name='Ram Medical').first():
            print("Database already contains Ram Medical and Shirpur pharmacies.")
            return

        print("Seeding database with Shirpur-Warwade pharmacies and catalogue...")

        # 1. Admin User
        admin = User.query.filter_by(email='admin@medifind.com').first()
        if not admin:
            admin = User(
                email='admin@medifind.com',
                full_name='System Administrator',
                phone='9876543210',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)

        # 2. Customer User
        customer = User.query.filter_by(email='customer@example.com').first()
        if not customer:
            customer = User(
                email='customer@example.com',
                full_name='Pratik Kasar',
                phone='9823863004',
                role='customer'
            )
            customer.set_password('customer123')
            db.session.add(customer)

        # 3. Pharmacy Owners & Real Shirpur-Warwade Pharmacies
        # Pharmacy 1: Ram Medical
        owner_ram = User.query.filter_by(email='ram@pharmacy.com').first()
        if not owner_ram:
            owner_ram = User(
                email='ram@pharmacy.com',
                full_name='Ram Medical Store Manager',
                phone='098238 63004',
                role='pharmacy'
            )
            owner_ram.set_password('pharmacy123')
            db.session.add(owner_ram)
            db.session.flush()

        ram_medical = Pharmacy(
            owner_id=owner_ram.id,
            name='Ram Medical',
            license_number='DL-MH-2024-425401',
            phone='098238 63004',
            email='ram@pharmacy.com',
            address='Pitreshwer Colony, Swami Vivekanand Nagar',
            city='Shirpur-Warwade',
            state='Maharashtra',
            pincode='425405',
            latitude=21.3565,
            longitude=74.8810,
            supports_pickup=True,
            supports_delivery=True,
            delivery_fee=25.0,
            is_verified=True,
            verification_status='APPROVED',
            is_active=True
        )
        db.session.add(ram_medical)

        # Pharmacy 2: Shree Ji Medical
        owner_shreeji = User.query.filter_by(email='shreeji@pharmacy.com').first()
        if not owner_shreeji:
            owner_shreeji = User(
                email='shreeji@pharmacy.com',
                full_name='Shree Ji Medical Store Manager',
                phone='098238 63004',
                role='pharmacy'
            )
            owner_shreeji.set_password('pharmacy123')
            db.session.add(owner_shreeji)
            db.session.flush()

        shreeji_medical = Pharmacy(
            owner_id=owner_shreeji.id,
            name='Shree Ji Medical',
            license_number='DL-MH-2024-425402',
            phone='098238 63004',
            email='shreeji@pharmacy.com',
            address='Shree Ji Medical, Hira Nagar, Swami Vivekanand Nagar',
            city='Shirpur-Warwade',
            state='Maharashtra',
            pincode='425405',
            latitude=21.3572,
            longitude=74.8825,
            supports_pickup=True,
            supports_delivery=True,
            delivery_fee=20.0,
            is_verified=True,
            verification_status='APPROVED',
            is_active=True
        )
        db.session.add(shreeji_medical)

        # Pharmacy 3: Tasir Medical
        owner_tasir = User.query.filter_by(email='tasir@pharmacy.com').first()
        if not owner_tasir:
            owner_tasir = User(
                email='tasir@pharmacy.com',
                full_name='Tasir Medical Store Manager',
                phone='075587 31868',
                role='pharmacy'
            )
            owner_tasir.set_password('pharmacy123')
            db.session.add(owner_tasir)
            db.session.flush()

        tasir_medical = Pharmacy(
            owner_id=owner_tasir.id,
            name='Tasir Medical',
            license_number='DL-MH-2024-425403',
            phone='075587 31868',
            email='tasir@pharmacy.com',
            address='17, behind RC Patel Urdu school, Ganesh Colony, Saraswti Colony',
            city='Shirpur-Warwade',
            state='Maharashtra',
            pincode='425405',
            latitude=21.3540,
            longitude=74.8790,
            supports_pickup=True,
            supports_delivery=True,
            delivery_fee=30.0,
            is_verified=True,
            verification_status='APPROVED',
            is_active=True
        )
        db.session.add(tasir_medical)

        # Pharmacy 4: Shree Gangai Medical
        owner_gangai = User.query.filter_by(email='gangai@pharmacy.com').first()
        if not owner_gangai:
            owner_gangai = User(
                email='gangai@pharmacy.com',
                full_name='Shree Gangai Medical Store Manager',
                phone='077981 04626',
                role='pharmacy'
            )
            owner_gangai.set_password('pharmacy123')
            db.session.add(owner_gangai)
            db.session.flush()

        shree_gangai = Pharmacy(
            owner_id=owner_gangai.id,
            name='Shree Gangai Medical',
            license_number='DL-MH-2024-425404',
            phone='077981 04626',
            email='gangai@pharmacy.com',
            address='Shree Gangai Medical, Shirpur, Swami Vivekanand Nagar',
            city='Shirpur-Warwade',
            state='Maharashtra',
            pincode='425405',
            latitude=21.3585,
            longitude=74.8835,
            supports_pickup=True,
            supports_delivery=True,
            delivery_fee=25.0,
            is_verified=True,
            verification_status='APPROVED',
            is_active=True
        )
        db.session.add(shree_gangai)

        db.session.flush()

        # 4. Medicine Catalogue
        medicines_data = [
            {
                'name': 'Dolo 650',
                'generic_name': 'Paracetamol',
                'brand_name': 'Micro Labs',
                'strength': '650mg',
                'dosage_form': 'Tablet',
                'description': 'Analgesic and antipyretic medicine used for fever and mild to moderate pain relief.',
                'requires_prescription': False
            },
            {
                'name': 'Calpol 500',
                'generic_name': 'Paracetamol',
                'brand_name': 'GSK',
                'strength': '500mg',
                'dosage_form': 'Tablet',
                'description': 'Fast acting pain reliever and temperature reducer for adults and children.',
                'requires_prescription': False
            },
            {
                'name': 'Brufen 400',
                'generic_name': 'Ibuprofen',
                'brand_name': 'Abbott',
                'strength': '400mg',
                'dosage_form': 'Tablet',
                'description': 'Non-steroidal anti-inflammatory drug (NSAID) for pain, inflammation and swelling.',
                'requires_prescription': False
            },
            {
                'name': 'Cetzine',
                'generic_name': 'Cetirizine',
                'brand_name': 'Dr. Reddy',
                'strength': '10mg',
                'dosage_form': 'Tablet',
                'description': 'Antihistamine for allergic rhinitis, runny nose, sneezing, and hives.',
                'requires_prescription': False
            },
            {
                'name': 'Mox 500',
                'generic_name': 'Amoxicillin',
                'brand_name': 'Ranbaxy',
                'strength': '500mg',
                'dosage_form': 'Capsule',
                'description': 'Broad spectrum penicillin antibiotic for bacterial infections.',
                'requires_prescription': True
            },
            {
                'name': 'Azee 500',
                'generic_name': 'Azithromycin',
                'brand_name': 'Cipla',
                'strength': '500mg',
                'dosage_form': 'Tablet',
                'description': 'Macrolide antibiotic used for respiratory tract and soft tissue infections.',
                'requires_prescription': True
            },
            {
                'name': 'Omez 20',
                'generic_name': 'Omeprazole',
                'brand_name': 'Dr. Reddy',
                'strength': '20mg',
                'dosage_form': 'Capsule',
                'description': 'Proton pump inhibitor that decreases stomach acid production for GERD.',
                'requires_prescription': False
            },
            {
                'name': 'Glycomet 500',
                'generic_name': 'Metformin',
                'brand_name': 'USV',
                'strength': '500mg',
                'dosage_form': 'Tablet',
                'description': 'Oral antihyperglycemic medication used in the management of type 2 diabetes.',
                'requires_prescription': True
            }
        ]

        medicines = []
        for m_data in medicines_data:
            existing_med = Medicine.query.filter_by(name=m_data['name']).first()
            if not existing_med:
                med = Medicine(**m_data)
                db.session.add(med)
                medicines.append(med)
            else:
                medicines.append(existing_med)

        db.session.flush()

        # 5. Inventories across all 4 verified pharmacies in Shirpur-Warwade
        pharmacies = [ram_medical, shreeji_medical, tasir_medical, shree_gangai]
        
        for p in pharmacies:
            for idx, med in enumerate(medicines):
                existing_inv = PharmacyInventory.query.filter_by(pharmacy_id=p.id, medicine_id=med.id).first()
                if not existing_inv:
                    base_price = 30.0 + (idx * 12.0)
                    inv = PharmacyInventory(
                        pharmacy_id=p.id,
                        medicine_id=med.id,
                        quantity=45,
                        price=base_price,
                        batch_number=f'BAT-SHR-{p.id}-{idx+1}',
                        expiry_date='12/2027',
                        notes='Fresh batch inventory'
                    )
                    inv.recalculate_stock_status()
                    db.session.add(inv)

        db.session.commit()
        print("Database successfully seeded with Ram Medical, Shree Ji Medical, Tasir Medical, and Shree Gangai Medical!")

if __name__ == '__main__':
    seed_database()
