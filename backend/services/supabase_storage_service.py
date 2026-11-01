"""
Supabase Storage Service for MediFind.

Handles secure server-side interactions with private Supabase Storage buckets:
- 'prescriptions' (customer prescription uploads)
- 'pharmacy-docs' (pharmacy license verification documents)

Security principles:
- Supabase service role key is NEVER exposed to the frontend / client.
- Buckets are private; all uploads and downloads pass through server-side
  permission and authorization checks before serving bytes.
- Direct authenticated streaming ensures the client never sees long-lived storage tokens.
- Graceful fallback to local disk storage if Supabase credentials are not configured
  (for local development / offline testing).
"""
import io
import json
import logging
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional, Tuple
from werkzeug.utils import secure_filename
from backend.config import Config

logger = logging.getLogger(__name__)


class SupabaseStorageService:
    """Service to interact with Supabase Storage REST API."""

    @classmethod
    def is_configured(cls) -> bool:
        """Checks if Supabase Storage is configured via environment variables."""
        url = getattr(Config, 'SUPABASE_URL', None) or os.environ.get('SUPABASE_URL')
        key = getattr(Config, 'SUPABASE_SERVICE_ROLE_KEY', None) or os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
        return bool(url and key and url.strip() and key.strip())

    @classmethod
    def get_base_url(cls) -> str:
        url = getattr(Config, 'SUPABASE_URL', None) or os.environ.get('SUPABASE_URL', '')
        return url.rstrip('/')

    @classmethod
    def get_service_key(cls) -> str:
        return getattr(Config, 'SUPABASE_SERVICE_ROLE_KEY', None) or os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')

    @classmethod
    def _get_headers(cls, content_type: Optional[str] = None) -> dict:
        key = cls.get_service_key()
        headers = {
            'apikey': key,
            'Authorization': f'Bearer {key}',
        }
        if content_type:
            headers['Content-Type'] = content_type
        return headers

    @classmethod
    def upload_file(cls, bucket: str, file_storage, dest_filename: str) -> str:
        """
        Uploads file bytes from Flask FileStorage or bytes-like object to a Supabase bucket.
        Returns the canonical storage path: 'supabase://{bucket}/{dest_filename}'.
        Raises RuntimeError or ValueError on failure.
        """
        if not cls.is_configured():
            raise RuntimeError("Supabase Storage is not configured.")

        # Read file bytes
        if hasattr(file_storage, 'read'):
            file_storage.seek(0)
            data = file_storage.read()
        elif isinstance(file_storage, (bytes, bytearray)):
            data = bytes(file_storage)
        else:
            raise ValueError("Unsupported file_storage object type.")

        if not data:
            raise ValueError("Cannot upload an empty file.")

        content_type = getattr(file_storage, 'content_type', None)
        if not content_type:
            content_type, _ = mimetypes.guess_type(dest_filename)
        if not content_type:
            content_type = 'application/octet-stream'

        clean_dest = urllib.parse.quote(dest_filename.lstrip('/'), safe='/-_.')
        upload_url = f"{cls.get_base_url()}/storage/v1/object/{bucket}/{clean_dest}"
        headers = cls._get_headers(content_type=content_type)
        # Allow overwriting existing file if same destination
        headers['x-upsert'] = 'true'

        req = urllib.request.Request(upload_url, data=data, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status not in (200, 201):
                    raise RuntimeError(f"Supabase upload returned status {resp.status}")
                logger.info("Successfully uploaded %s to Supabase bucket %s", dest_filename, bucket)
                return f"supabase://{bucket}/{dest_filename}"
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            logger.error("Supabase Storage upload error (HTTP %s): %s", e.code, error_body)
            raise RuntimeError(f"Storage upload failed: {error_body}") from e
        except Exception as e:
            logger.exception("Unexpected error uploading to Supabase Storage: %s", e)
            raise RuntimeError(f"Storage upload failed: {str(e)}") from e

    @classmethod
    def download_file(cls, bucket: str, dest_filename: str) -> Tuple[io.BytesIO, str]:
        """
        Downloads file from a private Supabase bucket via authenticated request.
        Returns a tuple: (io.BytesIO stream of file bytes, content_type).
        """
        if not cls.is_configured():
            raise RuntimeError("Supabase Storage is not configured.")

        clean_dest = urllib.parse.quote(dest_filename.lstrip('/'), safe='/-_.')
        download_url = f"{cls.get_base_url()}/storage/v1/object/authenticated/{bucket}/{clean_dest}"
        headers = cls._get_headers()

        req = urllib.request.Request(download_url, headers=headers, method='GET')
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                content_type = resp.headers.get('Content-Type')
                if not content_type:
                    content_type, _ = mimetypes.guess_type(dest_filename)
                content_type = content_type or 'application/octet-stream'
                return io.BytesIO(data), content_type
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            logger.error("Supabase Storage download error (HTTP %s): %s", e.code, error_body)
            raise FileNotFoundError(f"File not found in storage: {error_body}") from e
        except Exception as e:
            logger.exception("Unexpected error downloading from Supabase Storage: %s", e)
            raise RuntimeError(f"Storage download failed: {str(e)}") from e

    @classmethod
    def create_signed_url(cls, bucket: str, dest_filename: str, expires_in: int = 3600) -> str:
        """
        Creates a temporary signed download URL for private bucket objects.
        URL is time-limited (default: 1 hour).
        """
        if not cls.is_configured():
            raise RuntimeError("Supabase Storage is not configured.")

        clean_dest = urllib.parse.quote(dest_filename.lstrip('/'), safe='/-_.')
        sign_url = f"{cls.get_base_url()}/storage/v1/object/sign/{bucket}/{clean_dest}"
        payload = json.dumps({'expiresIn': expires_in}).encode('utf-8')
        headers = cls._get_headers(content_type='application/json')

        req = urllib.request.Request(sign_url, data=payload, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                signed_path = data.get('signedURL')
                if not signed_path:
                    raise RuntimeError("No signedURL returned by Supabase Storage.")
                return f"{cls.get_base_url()}/storage/v1{signed_path}"
        except Exception as e:
            logger.exception("Failed to generate signed URL: %s", e)
            raise RuntimeError(f"Signed URL generation failed: {str(e)}") from e

    @classmethod
    def delete_file(cls, bucket: str, dest_filename: str) -> bool:
        """Deletes an object from a bucket."""
        if not cls.is_configured():
            return False

        del_url = f"{cls.get_base_url()}/storage/v1/object/{bucket}"
        payload = json.dumps({'prefixes': [dest_filename]}).encode('utf-8')
        headers = cls._get_headers(content_type='application/json')

        req = urllib.request.Request(del_url, data=payload, headers=headers, method='DELETE')
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            logger.warning("Failed to delete object %s from bucket %s: %s", dest_filename, bucket, e)
            return False
