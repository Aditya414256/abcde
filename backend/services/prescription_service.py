import os
import uuid
from werkzeug.utils import secure_filename
from backend.models import Prescription, Order
from backend.database import db
from backend.config import Config

class PrescriptionService:
    @classmethod
    def save_prescription(cls, customer_id, file_storage, pharmacy_id=None):
        """
        Saves uploaded prescription safely in protected storage.
        Prescription starts in 'PENDING' status for manual human review by the pharmacy.
        """
        if not file_storage or not file_storage.filename:
            raise ValueError("No file provided.")

        filename = secure_filename(file_storage.filename)
        extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if extension not in Config.ALLOWED_EXTENSIONS:
            raise ValueError(f"Invalid file extension. Allowed: {', '.join(Config.ALLOWED_EXTENSIONS)}")

        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        full_path = os.path.join(Config.UPLOAD_FOLDER, unique_filename)
        file_storage.save(full_path)

        prescription = Prescription(
            customer_id=customer_id,
            pharmacy_id=pharmacy_id,
            file_path=full_path,
            original_filename=filename,
            status='PENDING',
            review_notes=None
        )
        db.session.add(prescription)
        db.session.commit()
        return prescription

    @classmethod
    def check_access_permission(cls, prescription, user):
        """
        Ensures prescription files are not publicly accessible.
        Only the customer who uploaded, the pharmacy associated with the order/pharmacy_id,
        or an admin may access.
        """
        if not user or not user.is_authenticated:
            return False

        if user.role == 'admin':
            return True

        if user.id == prescription.customer_id:
            return True

        if user.role == 'pharmacy':
            # Check if user owns the pharmacy
            pharmacy_ids = [p.id for p in user.pharmacies]
            if prescription.pharmacy_id in pharmacy_ids:
                return True
            # Also check if any order linked to this prescription belongs to user's pharmacy
            for order in prescription.orders:
                if order.pharmacy_id in pharmacy_ids:
                    return True

        return False

    @classmethod
    def review_prescription(cls, prescription_id, reviewer_user, status, notes=None):
        """
        Manual pharmacy review. Strictly no AI or automated approval.
        """
        prescription = Prescription.query.get(prescription_id)
        if not prescription:
            raise ValueError("Prescription not found.")

        if not cls.check_access_permission(prescription, reviewer_user):
            raise PermissionError("Unauthorized to review this prescription.")

        if status not in ['APPROVED', 'REJECTED']:
            raise ValueError("Status must be either APPROVED or REJECTED.")

        prescription.status = status
        prescription.review_notes = notes
        db.session.commit()
        return prescription
