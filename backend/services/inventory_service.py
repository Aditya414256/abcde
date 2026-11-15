from datetime import datetime, timezone
import math
from backend.models import Medicine
from backend.models import PharmacyInventory
from backend.database import db


class InventoryService:
    @classmethod
    def get_stock(cls, pharmacy_id, medicine_id):
        return PharmacyInventory.query.filter_by(
            pharmacy_id=pharmacy_id,
            medicine_id=medicine_id,
        ).first()

    @classmethod
    def get_pharmacy_inventory(cls, pharmacy_id):
        items = PharmacyInventory.query.filter_by(pharmacy_id=pharmacy_id).all()
        return [item.to_dict() for item in items]

    @classmethod
    def update_inventory(cls, pharmacy_id, medicine_id, quantity, price=None,
                         batch_number=None, expiry_date=None, notes=None):
        """
        Updates pharmacy inventory.
        Enforces non-negative quantity.
        Recalculates stock status.
        Updates last_updated_at.
        """
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            raise ValueError('Quantity must be a valid integer.')
        if quantity < 0:
            raise ValueError("Quantity cannot be negative.")
        if price is not None:
            try:
                price = float(price)
            except (ValueError, TypeError):
                raise ValueError('Price must be a valid number.')
            if not math.isfinite(price) or price < 0:
                raise ValueError('Price must be finite and non-negative.')
        if not db.session.get(Medicine, medicine_id):
            raise ValueError('Medicine not found.')

        item = cls.get_stock(pharmacy_id, medicine_id)
        if not item:
            item = PharmacyInventory(
                pharmacy_id=pharmacy_id,
                medicine_id=medicine_id,
                quantity=quantity,
                price=price if price is not None else 0.0,
                batch_number=batch_number,
                expiry_date=expiry_date,
                notes=notes,
            )
            db.session.add(item)
        else:
            item.quantity = quantity
            if price is not None:
                item.price = price
            if batch_number is not None:
                item.batch_number = batch_number
            if expiry_date is not None:
                item.expiry_date = expiry_date
            if notes is not None:
                item.notes = notes

        item.recalculate_stock_status()
        item.last_updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return item
