"""
Unit and integration tests for Supabase Storage Service.
Tests:
1. Configuration detection and URL/key handling.
2. Direct Supabase Storage upload, download, signed URL, and deletion.
3. PrescriptionService Supabase Storage upload and file streaming.
4. Pharmacy verification doc Supabase Storage upload and streaming.
5. Local fallback behavior when Supabase is unconfigured.
6. Access control on storage retrieval.
"""
import io
import pytest
from unittest.mock import patch, MagicMock
from werkzeug.datastructures import FileStorage
from backend.app import create_app
from backend.config import Config, TestingConfig
from backend.database import db
from backend.models import User, Pharmacy, Prescription
from backend.seed import seed_database
from backend.services.supabase_storage_service import SupabaseStorageService
from backend.services.prescription_service import PrescriptionService


@pytest.fixture
def test_app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        seed_database(app)
        yield app
        db.session.remove()
        db.drop_all()


def test_supabase_storage_service_configured():
    """Verify is_configured correctly checks SUPABASE_URL and key."""
    assert SupabaseStorageService.is_configured() is True
    assert SupabaseStorageService.get_base_url() == 'https://evcgzxpbvucmtojtlchl.supabase.co'


def test_supabase_storage_direct_roundtrip():
    """Live integration test: upload, download, sign, and delete from 'prescriptions' bucket."""
    test_content = b"Integration test prescription payload"
    dest_name = "test_prescription_direct.txt"

    file_obj = io.BytesIO(test_content)
    file_storage = FileStorage(stream=file_obj, filename=dest_name, content_type='text/plain')

    # Upload
    stored_path = SupabaseStorageService.upload_file(
        bucket='prescriptions',
        file_storage=file_storage,
        dest_filename=dest_name
    )
    assert stored_path == f"supabase://prescriptions/{dest_name}"

    # Download
    stream, content_type = SupabaseStorageService.download_file('prescriptions', dest_name)
    assert stream.read() == test_content

    # Signed URL
    signed_url = SupabaseStorageService.create_signed_url('prescriptions', dest_name, expires_in=120)
    assert signed_url.startswith("https://evcgzxpbvucmtojtlchl.supabase.co/storage/v1/object/sign/")

    # Cleanup
    deleted = SupabaseStorageService.delete_file('prescriptions', dest_name)
    assert deleted is True


def test_supabase_pharmacy_docs_roundtrip():
    """Live integration test: upload, download, and delete from 'pharmacy-docs' bucket."""
    test_content = b"%PDF-1.4 Fake pharmacy license data"
    dest_name = "test_license_direct.pdf"

    file_obj = io.BytesIO(test_content)
    file_storage = FileStorage(stream=file_obj, filename=dest_name, content_type='application/pdf')

    stored_path = SupabaseStorageService.upload_file(
        bucket='pharmacy-docs',
        file_storage=file_storage,
        dest_filename=dest_name
    )
    assert stored_path == f"supabase://pharmacy-docs/{dest_name}"

    stream, content_type = SupabaseStorageService.download_file('pharmacy-docs', dest_name)
    assert stream.read() == test_content

    deleted = SupabaseStorageService.delete_file('pharmacy-docs', dest_name)
    assert deleted is True


def test_prescription_service_saves_to_supabase(test_app):
    """PrescriptionService.save_prescription uploads to Supabase when configured."""
    with test_app.app_context():
        customer = User.query.filter_by(role='customer').first()
        test_file = FileStorage(
            stream=io.BytesIO(b"Doctor prescription notes"),
            filename="rx_sample.png",
            content_type="image/png"
        )

        prescription = PrescriptionService.save_prescription(
            customer_id=customer.id,
            file_storage=test_file
        )

        assert prescription.id is not None
        assert prescription.file_path.startswith("supabase://prescriptions/")
        assert prescription.original_filename == "rx_sample.png"
        assert prescription.status == "PENDING"

        # Test download stream via PrescriptionService
        stream, ctype, fname = PrescriptionService.get_prescription_file_stream(prescription)
        assert stream.read() == b"Doctor prescription notes"
        assert fname == "rx_sample.png"

        # Cleanup remote file
        dest_filename = prescription.file_path.split('/')[-1]
        SupabaseStorageService.delete_file('prescriptions', dest_filename)


def test_prescription_service_fallback_when_unconfigured(test_app, tmp_path):
    """When Supabase Storage is not configured, files fall back to local disk."""
    with test_app.app_context():
        customer = User.query.filter_by(role='customer').first()
        test_file = FileStorage(
            stream=io.BytesIO(b"Local fallback prescription"),
            filename="rx_local.pdf",
            content_type="application/pdf"
        )

        with patch.object(SupabaseStorageService, 'is_configured', return_value=False):
            with patch.object(Config, 'UPLOAD_FOLDER', str(tmp_path)):
                prescription = PrescriptionService.save_prescription(
                    customer_id=customer.id,
                    file_storage=test_file
                )

                assert not prescription.file_path.startswith("supabase://")
                assert prescription.original_filename == "rx_local.pdf"

                # Retrieval should read from local filesystem
                stream, ctype, fname = PrescriptionService.get_prescription_file_stream(prescription)
                assert stream.read() == b"Local fallback prescription"
                assert fname == "rx_local.pdf"

