"""
Medicine availability request service.

Customers submit a request when a medicine they need is out of stock at a
pharmacy.  Pharmacy owners review requests and update their status.
Notifications are sent on creation and on every status change.
"""
import logging
from datetime import datetime, timezone
from backend.models import MedicineRequest, Pharmacy, Medicine
from backend.services.notification_service import NotificationService
from backend.database import db

logger = logging.getLogger(__name__)

_VALID_STATUSES = frozenset({'PENDING', 'ACKNOWLEDGED', 'FULFILLED', 'REJECTED'})
_PHARMACY_UPDATABLE = frozenset({'ACKNOWLEDGED', 'FULFILLED', 'REJECTED'})


class RequestService:

    @classmethod
    def create_request(cls, customer_id, pharmacy_id, quantity_needed=1,
                       medicine_id=None, medicine_name_text=None, customer_notes=None):
        """
        Customer submits a medicine availability request to a specific pharmacy.

        Either medicine_id (for a catalogued medicine) or medicine_name_text
        (free-text name not yet in the catalogue) must be provided.
        """
        if not medicine_id and not (medicine_name_text or '').strip():
            raise ValueError("Either medicine_id or a medicine name is required.")

        try:
            quantity_needed = int(quantity_needed)
        except (TypeError, ValueError):
            raise ValueError("Quantity must be a valid integer.")
        if quantity_needed <= 0:
            raise ValueError("Quantity must be greater than zero.")

        pharmacy = db.session.get(Pharmacy, pharmacy_id)
        if not pharmacy:
            raise ValueError("Pharmacy not found.")
        if not pharmacy.is_active:
            raise ValueError("This pharmacy is currently inactive.")

        if medicine_id:
            medicine = db.session.get(Medicine, medicine_id)
            if not medicine:
                raise ValueError("Medicine not found.")

        req = MedicineRequest(
            customer_id=customer_id,
            pharmacy_id=pharmacy_id,
            medicine_id=medicine_id,
            medicine_name_text=(medicine_name_text or '').strip() or None,
            quantity_needed=quantity_needed,
            customer_notes=customer_notes,
            status='PENDING',
        )
        db.session.add(req)
        db.session.commit()

        # Notify the pharmacy owner
        med_label = (
            db.session.get(Medicine, medicine_id).name if medicine_id
            else medicine_name_text
        )
        try:
            NotificationService.create_notification(
                user_id=pharmacy.owner_id,
                title="New Medicine Request",
                message=(
                    f"A customer is requesting {med_label} "
                    f"(Qty: {quantity_needed}) at your pharmacy."
                ),
            )
        except Exception as err:
            logger.exception("Failed to notify pharmacy of new medicine request %s: %s", req.id, err)

        return req

    @classmethod
    def get_customer_requests(cls, customer_id):
        """Returns all medicine requests submitted by the given customer."""
        return (
            MedicineRequest.query
            .filter_by(customer_id=customer_id)
            .order_by(MedicineRequest.created_at.desc())
            .all()
        )

    @classmethod
    def get_pharmacy_requests(cls, pharmacy_id, owner_id):
        """
        Returns all medicine requests directed at the pharmacy.
        Validates that owner_id is the pharmacy owner.
        """
        pharmacy = db.session.get(Pharmacy, pharmacy_id)
        if not pharmacy or pharmacy.owner_id != owner_id:
            raise PermissionError("Unauthorized to view requests for this pharmacy.")
        return (
            MedicineRequest.query
            .filter_by(pharmacy_id=pharmacy_id)
            .order_by(MedicineRequest.created_at.desc())
            .all()
        )

    @classmethod
    def update_request_status(cls, request_id, owner_id, new_status, pharmacy_response=None):
        """
        Pharmacy owner updates the status of a medicine request.
        Only ACKNOWLEDGED, FULFILLED, and REJECTED are valid updates from pharmacy.
        """
        req = db.session.get(MedicineRequest, request_id)
        if not req:
            raise ValueError("Medicine request not found.")

        pharmacy = db.session.get(Pharmacy, req.pharmacy_id)
        if not pharmacy or pharmacy.owner_id != owner_id:
            raise PermissionError("Unauthorized to update this request.")

        if new_status not in _PHARMACY_UPDATABLE:
            raise ValueError(
                f"Invalid status. Pharmacy may set: {', '.join(sorted(_PHARMACY_UPDATABLE))}."
            )

        req.status = new_status
        req.pharmacy_response = pharmacy_response
        req.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        # Notify the customer
        try:
            status_label = new_status.title()
            med_label = req.medicine.name if req.medicine else req.medicine_name_text
            msg = f"Your request for {med_label} at {pharmacy.name} is now: {status_label}."
            if pharmacy_response:
                msg += f" Note: {pharmacy_response}"
            NotificationService.create_notification(
                user_id=req.customer_id,
                title=f"Medicine Request {status_label}",
                message=msg,
            )
        except Exception as err:
            logger.exception("Failed to notify customer of request update %s: %s", req.id, err)

        return req

    @classmethod
    def cancel_request(cls, request_id, customer_id):
        """Customer cancels their own PENDING request."""
        req = db.session.get(MedicineRequest, request_id)
        if not req:
            raise ValueError("Medicine request not found.")
        if req.customer_id != customer_id:
            raise PermissionError("Unauthorized to cancel this request.")
        if req.status != 'PENDING':
            raise ValueError("Only PENDING requests can be cancelled.")

        db.session.delete(req)
        db.session.commit()

