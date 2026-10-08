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

        # Check if already seeded
        if User.query.filter_by(email='admin@medifind.com').first():
            print("Database already contains seed data.")
            return

        print("Seeding database with realistic data...")

        # 1. Admin User
        admin = User(
            email='admin@medifind.com',
            full_name='System Administrator',
            phone='9876543210',
            role='admin'
        )
        admin.set_password('admin123')
        db.session.add(admin)

        # 2. Customer User
        customer = User(
            email='customer@example.com',
            full_name='Aditya Sharma',
            phone='9876543211',
            role='customer'
        )
        customer.set_password('customer123')
        db.session.add(customer)

        # 3. Pharmacy Owners & Verified Pharmacies
        # Pharmacy 1: Apollo HealthCare & Pharmacy
        owner_apollo = User(
            email='apollo@pharmacy.com',
            full_name='Dr. Rajesh Kumar',
            phone='9876543220',
            role='pharmacy'
        )
        owner_apollo.set_password('pharmacy123')
        db.session.add(owner_apollo)
        db.session.flush()

        apollo = Pharmacy(
            owner_id=owner_apollo.id,
            name='Apollo HealthCare & Pharmacy',
            license_number='DL-KA-2024-00142',
            phone='080-25589000',
            email='contact@apollopharmacy.com',
            address='12 MG Road, Near Metro Station',
            city='Bangalore',
            state='Karnataka',
            pincode='560001',
            latitude=12.9716,
            longitude=77.5946,
            supports_pickup=True,
            supports_delivery=True,
            delivery_fee=35.0,
            is_verified=True,
            verification_status='APPROVED',
            is_active=True
        )
        db.session.add(apollo)

        # Pharmacy 2: MedPlus Express Pharmacy
        owner_medplus = User(
            email='medplus@pharmacy.com',
            full_name='Suresh Patel',
            phone='9876543221',
            role='pharmacy'
        )
        owner_medplus.set_password('pharmacy123')
        db.session.add(owner_medplus)
        db.session.flush()

        medplus = Pharmacy(
            owner_id=owner_medplus.id,
            name='MedPlus Express Pharmacy',
            license_number='DL-KA-2024-00891',
            phone='080-25591234',
            email='support@medplusindia.com',
            address='45 Indiranagar 100ft Road',
            city='Bangalore',
            state='Karnataka',
            pincode='560038',
            latitude=12.9784,
            longitude=77.6408,
            supports_pickup=True,
            supports_delivery=True,
            delivery_fee=30.0,
            is_verified=True,
            verification_status='APPROVED',
            is_active=True
        )
        db.session.add(medplus)

        # Pharmacy 3: Guardian Care Pharmacy
        owner_guardian = User(
            email='guardian@pharmacy.com',
            full_name='Priya Nair',
            phone='9876543222',
            role='pharmacy'
        )
        owner_guardian.set_password('pharmacy123')
        db.session.add(owner_guardian)
        db.session.flush()

        guardian = Pharmacy(
            owner_id=owner_guardian.id,
            name='Guardian Care Pharmacy',
            license_number='DL-KA-2024-00563',
            phone='080-26673456',
            email='info@guardiancare.in',
            address='88 Koramangala 4th Block',
            city='Bangalore',
            state='Karnataka',
            pincode='560034',
            latitude=12.9345,
            longitude=77.6265,
            supports_pickup=True,
            supports_delivery=False,
            delivery_fee=0.0,
            is_verified=True,
            verification_status='APPROVED',
            is_active=True
        )
        db.session.add(guardian)

        # Pharmacy 4: City Health Drugstore (PENDING verification for admin workflow test)
        owner_city = User(
            email='cityhealth@pharmacy.com',
            full_name='Vikram Singh',
            phone='9876543223',
            role='pharmacy'
        )
        owner_city.set_password('pharmacy123')
        db.session.add(owner_city)
        db.session.flush()

        city_health = Pharmacy(
            owner_id=owner_city.id,
            name='City Health Drugstore',
            license_number='DL-KA-2026-PENDING-01',
            phone='080-28899112',
            email='care@cityhealth.com',
            address='15 Whitefield Main Road',
            city='Bangalore',
            state='Karnataka',
            pincode='560066',
            latitude=12.9698,
            longitude=77.7499,
            supports_pickup=True,
            supports_delivery=True,
            delivery_fee=45.0,
            is_verified=False,
            verification_status='PENDING',
            is_active=True
        )
        db.session.add(city_health)

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
            med = Medicine(**m_data)
            db.session.add(med)
            medicines.append(med)

        db.session.flush()

        # 5. Inventories across verified pharmacies
        inventory_configs = [
            # Apollo stocks
            (apollo.id, medicines[0].id, 50, 32.0, 'BAT-2024-01', '12/2027'), # Dolo 650
            (apollo.id, medicines[1].id, 35, 28.0, 'BAT-2024-02', '09/2026'), # Calpol 500
            (apollo.id, medicines[2].id, 25, 45.0, 'BAT-2024-03', '11/2026'), # Brufen 400
            (apollo.id, medicines[3].id, 40, 20.0, 'BAT-2024-04', '01/2027'), # Cetzine
            (apollo.id, medicines[4].id, 15, 110.0, 'BAT-2024-05', '06/2026'), # Mox 500
            (apollo.id, medicines[5].id, 20, 140.0, 'BAT-2024-06', '08/2026'), # Azee 500
            (apollo.id, medicines[6].id, 30, 65.0, 'BAT-2024-07', '04/2027'), # Omez 20
            (apollo.id, medicines[7].id, 60, 48.0, 'BAT-2024-08', '10/2027'), # Glycomet 500

            # MedPlus stocks
            (medplus.id, medicines[0].id, 40, 30.0, 'BAT-2024-11', '01/2028'), # Dolo 650
            (medplus.id, medicines[1].id, 20, 26.0, 'BAT-2024-12', '10/2026'), # Calpol 500
            (medplus.id, medicines[2].id, 30, 42.0, 'BAT-2024-13', '12/2026'), # Brufen 400
            (medplus.id, medicines[3].id, 50, 18.0, 'BAT-2024-14', '03/2027'), # Cetzine
            (medplus.id, medicines[4].id, 12, 105.0, 'BAT-2024-15', '05/2026'), # Mox 500
            (medplus.id, medicines[6].id, 25, 62.0, 'BAT-2024-16', '07/2027'), # Omez 20

            # Guardian Care stocks
            (guardian.id, medicines[0].id, 25, 33.0, 'BAT-2024-21', '11/2027'), # Dolo 650
            (guardian.id, medicines[2].id, 15, 46.0, 'BAT-2024-22', '08/2026'), # Brufen 400
            (guardian.id, medicines[3].id, 18, 22.0, 'BAT-2024-23', '04/2027'), # Cetzine
            (guardian.id, medicines[7].id, 30, 50.0, 'BAT-2024-24', '11/2027')  # Glycomet 500
        ]

        for p_id, m_id, qty, pr, bat, exp in inventory_configs:
            inv = PharmacyInventory(
                pharmacy_id=p_id,
                medicine_id=m_id,
                quantity=qty,
                price=pr,
                batch_number=bat,
                expiry_date=exp,
                notes='Standard batch inventory'
            )
            inv.recalculate_stock_status()
            db.session.add(inv)

        db.session.commit()
        print("Database successfully seeded with realistic catalogue, verified pharmacies, and inventory!")

if __name__ == '__main__':
    seed_database()
