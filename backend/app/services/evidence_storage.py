"""
Recognition-evidence storage abstraction.

Two implementations selectable via ``settings.RECOGNITION_EVIDENCE_BACKEND``:

- ``FilesystemStorage`` (default): crops live under
  ``settings.RECOGNITION_EVIDENCE_CROP_ROOT`` on a host-mounted Docker
  volume. The router returns bytes directly (FileResponse).

- ``MinioStorage`` (Phase 5): crops live in an S3-compatible object store.
  The router returns a 302 redirect to a time-limited presigned URL so the
  API never proxies bytes.

Consumers call the module-level ``evidence_storage`` singleton. It picks
the backend at import time. Swap the env var + redeploy to change.

Design choice — filesystem refs remain relative paths like
``2026-04-24/<uuid>-live.jpg`` and MinIO refs are the same shape — they
*are* the object key. This keeps the DB column format identical across
backends, so you can mix filesystem + MinIO rows during the migration
window without schema churn.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger("iams")


class EvidenceStorage(ABC):
    """Storage driver contract."""

    # Signals to the router: if False, the router returns bytes inline
    # (FileResponse). If True, the router issues a 302 to ``presigned_get``.
    supports_presigned: bool = False

    @abstractmethod
    def put(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def get_bytes(self, key: str) -> Optional[bytes]: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def local_path(self, key: str) -> Optional[Path]:
        """Return a filesystem path if the backend physically stores the
        blob on disk, else None. Used only by the router's FileResponse
        fast path for filesystem mode; MinIO mode never calls this."""

    def presigned_get(self, key: str, ttl_seconds: int) -> Optional[str]:
        """Time-limited URL. Only implemented by MinIO."""
        return None

    # -- helpers shared by both --

    @staticmethod
    def make_key(event_id: str, kind: str, *, today: Optional[datetime] = None) -> str:
        """Filename layout: ``<yyyy-mm-dd>/<event_id>-<kind>.jpg``.

        Shared across backends so the ref column format is stable through
        a filesystem → MinIO migration.
        """
        d = today or datetime.now()
        return f"{d:%Y-%m-%d}/{event_id}-{kind}.jpg"


class FilesystemStorage(EvidenceStorage):
    """Flat-directory store under ``RECOGNITION_EVIDENCE_CROP_ROOT``.

    Used by Phases 1–4. Zero external dependencies; survives if MinIO is
    broken.
    """

    supports_presigned = False

    def __init__(self, root: Path):
        self._root = root
        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except Exception:
            logger.exception(
                "FilesystemStorage: could not create %s — writes will fail",
                self._root,
            )

    def _resolve(self, key: str) -> Optional[Path]:
        """Harden against path traversal via a crafted key."""
        if not key:
            return None
        candidate = (self._root / key).resolve()
        try:
            candidate.relative_to(self._root.resolve())
        except ValueError:
            return None
        return candidate

    def put(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        if not path:
            raise ValueError(f"Rejecting traversal key {key!r}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_bytes(self, key: str) -> Optional[bytes]:
        path = self._resolve(key)
        if not path or not path.is_file():
            return None
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if not path:
            return
        try:
            path.unlink()
        except FileNotFoundError:
            return

    def exists(self, key: str) -> bool:
        path = self._resolve(key)
        return bool(path and path.is_file())

    def local_path(self, key: str) -> Optional[Path]:
        path = self._resolve(key)
        if path and path.is_file():
            return path
        return None


class MinioStorage(EvidenceStorage):
    """S3-compatible object store. Used by Phase 5.

    Creates the bucket on first init. Every ``get`` call yields a
    presigned URL so the API layer can 302-redirect the browser — the API
    container never proxies JPEG bytes, which keeps the FastAPI worker
    responsive under load.

    Lazily imports ``minio`` so an environment without the package can
    still run in filesystem mode.
    """

    supports_presigned = True

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool,
        bucket: str,
        region: str,
    ):
        try:
            from minio import Minio
        except ImportError as exc:  # pragma: no cover — covered at import time
            raise RuntimeError(
                "MinioStorage requires the 'minio' package. Add it to "
                "requirements.txt and rebuild the image."
            ) from exc

        self._bucket = bucket
        self._region = region
        self._client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket, location=self._region)
                logger.info("MinIO bucket created: %s", self._bucket)
        except Exception:
            logger.exception(
                "MinIO: could not ensure bucket %s — subsequent writes may fail",
                self._bucket,
            )

    def put(self, key: str, data: bytes) -> None:
        import io

        stream = io.BytesIO(data)
        self._client.put_object(
            self._bucket,
            key,
            stream,
            length=len(data),
            content_type="image/jpeg",
        )

    def get_bytes(self, key: str) -> Optional[bytes]:
        """Used by the migration script + right-to-delete cascade. The
        router uses presigned_get instead to avoid proxying bytes.
        """
        try:
            resp = self._client.get_object(self._bucket, key)
            try:
                return resp.read()
            finally:
                resp.close()
                resp.release_conn()
        except Exception:
            return None

    def delete(self, key: str) -> None:
        try:
            self._client.remove_object(self._bucket, key)
        except Exception:
            logger.debug("MinIO delete failed for %s", key, exc_info=True)

    def exists(self, key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, key)
            return True
        except Exception:
            return False

    def local_path(self, key: str) -> Optional[Path]:
        return None

    def presigned_get(self, key: str, ttl_seconds: int) -> Optional[str]:
        from datetime import timedelta

        try:
            return self._client.presigned_get_object(
                self._bucket,
                key,
                expires=timedelta(seconds=max(1, int(ttl_seconds))),
            )
        except Exception:
            logger.debug("MinIO presigned_get failed for %s", key, exc_info=True)
            return None


def _build_storage() -> EvidenceStorage:
    backend = (settings.RECOGNITION_EVIDENCE_BACKEND or "filesystem").strip().lower()
    if backend == "minio":
        try:
            return MinioStorage(
                endpoint=settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
                bucket=settings.MINIO_BUCKET,
                region=settings.MINIO_REGION,
            )
        except Exception:
            logger.exception(
                "MinioStorage init failed — falling back to filesystem. "
                "Fix MINIO_* settings or flip RECOGNITION_EVIDENCE_BACKEND back to 'filesystem'."
            )
            # Fall through to filesystem — safer than refusing to serve.
    return FilesystemStorage(Path(settings.RECOGNITION_EVIDENCE_CROP_ROOT))


# Module-level singleton. Router + writer + retention + migration all use this.
evidence_storage: EvidenceStorage = _build_storage()
