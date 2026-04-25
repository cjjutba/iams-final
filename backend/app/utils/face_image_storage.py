"""
Face Image Storage

Persistent storage for the 3-5 angle JPEGs captured during student face
registration. Writes to the existing ``face_uploads_onprem`` Docker volume
(mounted at ``/app/data/uploads/faces`` — see
``deploy/docker-compose.onprem.yml`` and ``settings.UPLOAD_DIR``).

The admin portal's live-feed face-comparison sheet reads these back through
``backend/app/routers/face.py``'s admin-only ``/face/registrations/{user_id}``
+ image-bytes endpoints.

Safety notes
------------
* All paths are built from the sanitized user UUID + a fixed angle-label
  allowlist. ``..`` is stripped defensively before joining.
* JPEG re-encoded at 640px max edge, quality 85 — phone originals can be
  4-12 MB, which is wasteful for a sheet thumbnail and would bloat the
  volume quickly at scale.
* EXIF rotation is applied so stored JPEGs are visually upright (phone
  captures are frequently sideways in raw bytes).
"""

from __future__ import annotations

import io
import logging
import re
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps

from app.config import settings

logger = logging.getLogger(__name__)

# Phone-captured registration angles. These are the canonical set written
# during the student-facing registration flow.
_ALLOWED_ANGLE_LABELS: frozenset[str] = frozenset(
    {"center", "left", "right", "up", "down"}
)

# CCTV-captured registration crops written by the operator-driven
# scripts/cctv_enroll.py + POST /api/v1/face/cctv-enroll endpoint. These
# augment the phone-captured angles with embeddings drawn from the actual
# CCTV image domain so recognition can close the phone→CCTV cross-domain
# gap. Pattern is `cctv_<positive_int>` — index is per-user and assigned
# by the service when persisting to face_embeddings.
_CCTV_LABEL_RE = re.compile(r"^cctv_\d+$")


def _is_allowed_angle_label(angle_label: str) -> bool:
    """True if angle_label is either a phone-captured angle or a CCTV index."""
    return angle_label in _ALLOWED_ANGLE_LABELS or bool(_CCTV_LABEL_RE.match(angle_label))

_REGISTRATIONS_SUBDIR = "registrations"
_MAX_EDGE_PX = 640
_JPEG_QUALITY = 85


class FaceImageStorage:
    """Filesystem store for per-angle registration JPEGs.

    Singleton-ish: it's cheap to instantiate (just holds a base Path), and
    the on-disk tree is shared across workers.
    """

    def __init__(self, base_dir: Path | str | None = None) -> None:
        root = Path(base_dir) if base_dir is not None else Path(settings.UPLOAD_DIR)
        self.base_dir = root.resolve()

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------
    def save_registration_image(
        self, user_id: str, angle_label: str, image_bytes: bytes
    ) -> str | None:
        """Compress + orient-correct + write a single registration image.

        Returns the relative storage_key to store on FaceEmbedding.image_storage_key,
        or None on any failure (callers keep the DB row with NULL key rather
        than roll back the whole registration).
        """
        if not _is_allowed_angle_label(angle_label):
            logger.warning(
                "Refusing to save registration image: unknown angle_label=%r",
                angle_label,
            )
            return None

        safe_user = self._safe_user_component(user_id)
        if safe_user is None:
            return None

        try:
            with Image.open(io.BytesIO(image_bytes)) as im:
                im = ImageOps.exif_transpose(im)
                if im.mode != "RGB":
                    im = im.convert("RGB")
                im.thumbnail((_MAX_EDGE_PX, _MAX_EDGE_PX), Image.Resampling.LANCZOS)

                out_dir = self.base_dir / _REGISTRATIONS_SUBDIR / safe_user
                out_dir.mkdir(parents=True, exist_ok=True)
                filename = f"{angle_label}_{uuid.uuid4().hex[:12]}.jpg"
                out_path = out_dir / filename

                im.save(out_path, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
        except Exception:  # noqa: BLE001 — intentional catch-all
            logger.warning(
                "Failed to persist registration image for user=%s angle=%s",
                user_id,
                angle_label,
                exc_info=True,
            )
            return None

        # Stored key is relative to base_dir so moves / remounts stay portable.
        storage_key = f"{_REGISTRATIONS_SUBDIR}/{safe_user}/{filename}"
        logger.info(
            "Persisted registration image: user=%s angle=%s key=%s",
            user_id,
            angle_label,
            storage_key,
        )
        return storage_key

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------
    def open_registration_image(self, storage_key: str) -> BinaryIO:
        """Open image bytes for streaming. Raises FileNotFoundError on miss."""
        path = self._resolve_key(storage_key)
        return path.open("rb")

    def resolve_path(self, storage_key: str) -> Path:
        """Return the absolute on-disk path for a storage_key, or raise FileNotFoundError."""
        return self._resolve_key(storage_key)

    def exists(self, storage_key: str) -> bool:
        try:
            return self._resolve_key(storage_key).is_file()
        except FileNotFoundError:
            return False

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def delete_user_images(self, user_id: str) -> int:
        """Best-effort: remove the whole per-user directory. Returns files removed."""
        safe_user = self._safe_user_component(user_id)
        if safe_user is None:
            return 0
        dir_path = self.base_dir / _REGISTRATIONS_SUBDIR / safe_user
        if not dir_path.is_dir():
            return 0
        removed = 0
        try:
            removed = sum(1 for _ in dir_path.iterdir())
            shutil.rmtree(dir_path)
            logger.info("Deleted %d registration images for user=%s", removed, user_id)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to delete registration images for user=%s", user_id, exc_info=True
            )
        return removed

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_user_component(user_id: str) -> str | None:
        """Reject anything that isn't shaped like a UUID-ish opaque id."""
        if not user_id:
            return None
        cleaned = user_id.replace("..", "").replace("/", "").replace("\\", "")
        # Keep it loose: real user ids are uuid4 hex strings, but
        # let dev/test ids through. Just block traversal + separators.
        if cleaned != user_id:
            logger.warning("Refusing unsafe user_id: %r", user_id)
            return None
        return cleaned

    def _resolve_key(self, storage_key: str) -> Path:
        if not storage_key:
            raise FileNotFoundError("empty storage_key")
        # Normalize and confine under base_dir.
        rel = Path(storage_key)
        if rel.is_absolute():
            raise FileNotFoundError(f"storage_key must be relative: {storage_key}")
        resolved = (self.base_dir / rel).resolve()
        try:
            resolved.relative_to(self.base_dir)
        except ValueError:
            # Escape attempt — treat as not found.
            raise FileNotFoundError(f"storage_key escapes base: {storage_key}")
        if not resolved.is_file():
            raise FileNotFoundError(f"missing: {storage_key}")
        return resolved
