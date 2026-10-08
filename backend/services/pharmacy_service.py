from backend.models import Pharmacy, User
from backend.services.location_service import LocationService
from backend.database import db

class PharmacyService:
    @classmethod
    def register_pharmacy(cls, owner_id, name, license_number, phone, email, address, city, state, pincode,
                          supports_pickup=True, supports_delivery=False, delivery_fee=0.0,
                          latitude=None, longitude=None):
        """
        Registers a new pharmacy.
        Always starts with is_verified=False and verification_status='PENDING'.
        """
        existing = Pharmacy.query.filter_by(license_number=license_number).first()
        if existing:
            raise ValueError(f"Pharmacy with license number '{license_number}' already registered.")

        pharmacy = Pharmacy(
            owner_id=owner_id,
            name=name,
            license_number=license_number,
            phone=phone,
            email=email,
            address=address,
            city=city,
            state=state,
            pincode=pincode,
            latitude=latitude,
            longitude=longitude,
            supports_pickup=supports_pickup,
            supports_delivery=supports_delivery,
            delivery_fee=delivery_fee,
            is_verified=False,
            verification_status='PENDING',
            is_active=True
        )
        db.session.add(pharmacy)
        db.session.commit()
        return pharmacy

    @classmethod
    def verify_pharmacy(cls, pharmacy_id, status):
        """
        Admin verification action: 'APPROVED' or 'REJECTED'.
        """
        pharmacy = db.session.get(Pharmacy, pharmacy_id)
        if not pharmacy:
            raise ValueError("Pharmacy not found.")

        if status not in ['APPROVED', 'REJECTED', 'PENDING']:
            raise ValueError(f"Invalid verification status: {status}")

        pharmacy.verification_status = status
        pharmacy.is_verified = (status == 'APPROVED')
        db.session.commit()
        return pharmacy

    @classmethod
    def set_active_status(cls, pharmacy_id, is_active):
        pharmacy = db.session.get(Pharmacy, pharmacy_id)
        if not pharmacy:
            raise ValueError("Pharmacy not found.")
        pharmacy.is_active = is_active
        db.session.commit()
        return pharmacy

    @classmethod
    def list_verified_pharmacies(cls, user_lat=None, user_lon=None):
        """
        Returns only active and admin-verified pharmacies.
        Optionally calculates distance from user's coordinates.
        """
        pharmacies = Pharmacy.query.filter_by(is_verified=True, is_active=True).all()
        result = []
        for p in pharmacies:
            data = p.to_dict()
            if user_lat is not None and user_lon is not None and p.latitude and p.longitude:
                dist = LocationService.haversine_distance(user_lat, user_lon, p.latitude, p.longitude)
                data['distance_km'] = dist
                data['distance_text'] = LocationService.format_distance(dist)
            else:
                data['distance_km'] = None
                data['distance_text'] = None
            result.append(data)

        if user_lat is not None and user_lon is not None:
            # Sort by distance (nearest first), placing unknown distances at the end
            result.sort(key=lambda x: (x['distance_km'] is None, x['distance_km']))

        return result

    @classmethod
    def get_pharmacy_by_id(cls, pharmacy_id):
        return db.session.get(Pharmacy, pharmacy_id)

    @classmethod
    def get_pharmacy_by_owner_id(cls, owner_id):
        return Pharmacy.query.filter_by(owner_id=owner_id).first()
