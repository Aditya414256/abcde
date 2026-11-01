import io
import logging
import mimetypes
import os
import uuid
from werkzeug.utils import secure_filename
from backend.models import Prescription, Order
from backend.database import db
from backend.config import Config
from backend.services.supabase_storage_service import SupabaseStorageService

logger = logging.getLogger(__name__)


class PrescriptionService:
    @classmethod
    def save_prescription(cls, customer_id, file_storage, pharmacy_id=None):
        """
        Saves uploaded prescription safely.
        - If Supabase Storage is configured: uploads to the private 'prescriptions' bucket.
        - If not configured (local dev fallback): saves to protected local storage folder.
        Prescription starts in 'PENDING' status for manual human review.
        """
        if not file_storage or not file_storage.filename:
            raise ValueError("No file provided.")

        filename = secure_filename(file_storage.filename)
        extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if extension not in Config.ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Invalid file extension. Allowed: {', '.join(sorted(Config.ALLOWED_EXTENSIONS))}"
            )

        unique_filename = f"{uuid.uuid4().hex}_{filename}"

        if SupabaseStorageService.is_configured():
            bucket = getattr(Config, 'SUPABASE_PRESCRIPTIONS_BUCKET', 'prescriptions')
            stored_path = SupabaseStorageService.upload_file(
                bucket=bucket,
                file_storage=file_storage,
                dest_filename=unique_filename
            )
        else:
            os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
            stored_path = os.path.join(Config.UPLOAD_FOLDER, unique_filename)
            file_storage.save(stored_path)

        prescription = Prescription(
            customer_id=customer_id,
            pharmacy_id=pharmacy_id,
            file_path=stored_path,
            original_filename=filename,
            status='PENDING',
            review_notes=None,
        )
        db.session.add(prescription)
        db.session.commit()
        return prescription

    @classmethod
    def get_prescription_file_stream(cls, prescription) -> Tuple[io.BytesIO, str, str]:
        """
        Retrieves file bytes stream for authenticated download.
        Returns tuple: (BytesIO_stream, content_type, filename).
        Handles both Supabase storage paths ('supabase://prescriptions/...')
        and local filesystem paths.
        """
        if not prescription or not prescription.file_path:
            raise FileNotFoundError("Prescription has no file attached.")

        path = prescription.file_path
        filename = prescription.original_filename or 'prescription'

        # Case 1: Stored in Supabase
        if path.startswith('supabase://'):
            without_prefix = path[len('supabase://'):]
            parts = without_prefix.split('/', 1)
            bucket = parts[0]
            dest_filename = parts[1] if len(parts) > 1 else ''
            stream, content_type = SupabaseStorageService.download_file(bucket, dest_filename)
            return stream, content_type, filename

        # Case 2: Stored on local filesystem
        if os.path.exists(path):
            with open(path, 'rb') as f:
                data = f.read()
            content_type, _ = mimetypes.guess_type(path)
            content_type = content_type or 'application/octet-stream'
            return io.BytesIO(data), content_type, filename

        raise FileNotFoundError("Prescription file not found on storage or server.")

    @classmethod
    def check_access_permission(cls, prescription, user):
        """
        Ensures prescription files are not publicly accessible.
        Access is granted to:
        - The customer who uploaded the prescription.
        - The pharmacy owner associated with the prescription or any order linked to it.
        - Any admin.
        """
        if not user or not user.is_authenticated:
            return False

        if user.role == 'admin':
            return True

        if user.id == prescription.customer_id:
            return True

        if user.role == 'pharmacy':
            pharmacy_ids = {p.id for p in user.pharmacies}
            if prescription.pharmacy_id in pharmacy_ids:
                return True
            # Also grant access if any order linked to this prescription belongs to this pharmacy
            for order in prescription.orders:
                if order.pharmacy_id in pharmacy_ids:
                    return True

        return False

    @classmethod
    def review_prescription(cls, prescription_id, reviewer_user, status, notes=None):
        """
        Manual pharmacy or admin review. Strictly no AI or automated approval.

        When a prescription is REJECTED:
        - The rejection reason is recorded.
        - Any linked PENDING orders for Home Delivery that have not yet been
          confirmed are automatically rejected and the customer is notified.
        - Approval is separate from order acceptance; approving a prescription
          does not automatically accept the related order.
        """
        from backend.services.notification_service import NotificationService
        from backend.services.order_service import OrderService

        prescription = db.session.get(Prescription, prescription_id)
        if not prescription:
            raise ValueError("Prescription not found.")

        if not cls.check_access_permission(prescription, reviewer_user):
            raise PermissionError("Unauthorized to review this prescription.")

        if status not in ('APPROVED', 'REJECTED'):
            raise ValueError("Status must be either APPROVED or REJECTED.")

        if status == 'REJECTED' and not notes:
            raise ValueError("A reason is required when rejecting a prescription.")

        prescription.status = status
        prescription.review_notes = notes
        db.session.commit()

        # On rejection: reject related PENDING delivery orders and notify the customer
        if status == 'REJECTED':
            related_orders = Order.query.filter_by(
                prescription_id=prescription.id
            ).filter(Order.status == 'PENDING').all()

            for order in related_orders:
                try:
                    # Only auto-reject delivery orders waiting on this prescription
                    if order.order_type == 'DELIVERY':
                        allowed = OrderService.ALLOWED_TRANSITIONS.get(order.status, [])
                        if 'REJECTED' in allowed:
                            order.status = 'REJECTED'
                            db.session.commit()
                            NotificationService.create_notification(
                                user_id=order.customer_id,
                                title="Order Update: Your order was not taken.",
                                message=(
                                    f"Your order #{order.order_number}: Your order was not taken. "
                                    f"Reason: Prescription rejected. {notes or ''}"
                                ),
                                order_id=order.id,
                            )
                except Exception as err:
                    logger.exception(
                        "Failed to reject order %s after prescription rejection: %s",
                        order.id, err,
                    )

        return prescription
