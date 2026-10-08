from sqlalchemy import or_
from backend.models import Medicine
from backend.database import db

class MedicineService:
    @classmethod
    def search_medicines(cls, query, limit=20):
        """
        Search medicines by name, generic_name, brand_name, strength, or dosage form.
        Case-insensitive and safe against malformed input.
        """
        if not query or not isinstance(query, str):
            return []

        search_term = query.strip()
        if not search_term:
            return []

        pattern = f"%{search_term}%"
        medicines = Medicine.query.filter(
            or_(
                Medicine.name.ilike(pattern),
                Medicine.generic_name.ilike(pattern),
                Medicine.brand_name.ilike(pattern),
                Medicine.strength.ilike(pattern),
                Medicine.dosage_form.ilike(pattern)
            )
        ).limit(limit).all()

        return [m.to_dict() for m in medicines]

    @classmethod
    def get_suggestions(cls, query, limit=6):
        """
        Autocomplete suggestions: fast, concise, focused on medicine name & essential info.
        """
        if not query or not isinstance(query, str):
            return []

        search_term = query.strip()
        if len(search_term) < 1:
            return []

        pattern = f"%{search_term}%"
        medicines = Medicine.query.filter(
            or_(
                Medicine.name.ilike(pattern),
                Medicine.generic_name.ilike(pattern)
            )
        ).limit(limit).all()

        return [{
            'id': m.id,
            'name': m.name,
            'generic_name': m.generic_name,
            'strength': m.strength,
            'dosage_form': m.dosage_form,
            'requires_prescription': m.requires_prescription
        } for m in medicines]

    @classmethod
    def get_medicine_by_id(cls, medicine_id):
        return db.session.get(Medicine, medicine_id)
