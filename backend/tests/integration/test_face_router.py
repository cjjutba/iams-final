"""
Integration Tests for Face Recognition Router

Tests all 7 endpoints in app/routers/face.py:
  1. POST /api/v1/face/register      (student auth)
  2. POST /api/v1/face/reregister    (student auth)
  3. GET  /api/v1/face/status        (any auth)
  4. POST /api/v1/face/recognize     (no auth)
  5. POST /api/v1/face/process       (no auth - Edge API)
  6. GET  /api/v1/face/statistics    (any auth)
  7. DELETE /api/v1/face/{user_id}   (auth + ownership check)

Mocking strategy:
  - insightface_model and faiss_manager are module-level singletons imported into
    face_service.py.  We patch them at the *import location* inside FaceService
    so every FaceService(db) instance picks up the mocks.
  - The router's _request_cache dict is cleared between tests via an autouse
    fixture to prevent cross-test deduplication interference.
"""

import base64
import io
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

PREFIX = "/api/v1/face"


def _make_embedding() -> np.ndarray:
    """Return a random L2-normalised 512-dim embedding."""
    emb = np.random.randn(512).astype(np.float32)
    return emb / np.linalg.norm(emb)


def _make_test_image_bytes() -> bytes:
    """Create a minimal JPEG image in memory."""
    img = Image.new("RGB", (160, 160), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_test_image_base64() -> str:
    """Return a base64-encoded JPEG string."""
    return base64.b64encode(_make_test_image_bytes()).decode()


def _make_upload_files(count: int = 3):
    """Build a list of multipart file tuples for the ``images`` field."""
    return [
        ("images", (f"face_{i}.jpg", _make_test_image_bytes(), "image/jpeg"))
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# Autouse fixture -- clear the router dedup cache between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_request_cache():
    """Clear the Edge API deduplication cache so tests are isolated."""
    from app.routers.face import _request_cache
    _request_cache.clear()
    yield
    _request_cache.clear()


# ---------------------------------------------------------------------------
# Convenience context-manager for patching the two ML singletons
# ---------------------------------------------------------------------------

def _patch_ml_singletons(
    *,
    generate_embedding=None,
    decode_base64_image=None,
    faiss_search=None,
    faiss_search_with_margin=None,
    faiss_add_return=0,
):
    """
    Return a combined patch context that replaces insightface_model and
    faiss_manager inside face_service.py.

    Parameters let callers customise per-test behaviour without repeating
    boilerplate.

    ``faiss_search`` controls the legacy ``.search()`` return value.
    ``faiss_search_with_margin`` controls ``.search_with_margin()`` used by
    the Edge API (POST /face/process).  When not supplied it defaults to a
    no-match result ``{"user_id": None, "confidence": None, "is_ambiguous": False}``.
    """
    mock_fn = MagicMock()
    mock_fn.get_embedding = MagicMock(
        side_effect=generate_embedding or (lambda *_a, **_kw: _make_embedding())
    )
    mock_fn.decode_base64_image = MagicMock(
        side_effect=decode_base64_image
        or (lambda *_a, **_kw: Image.new("RGB", (160, 160)))
    )
    mock_fn.app = MagicMock()  # Not None -> model "loaded"

    mock_faiss = MagicMock()
    mock_faiss.index = MagicMock()  # Not None -> index "loaded"
    mock_faiss.add = MagicMock(return_value=faiss_add_return)
    mock_faiss.search = MagicMock(return_value=faiss_search or [])
    mock_faiss.search_with_margin = MagicMock(
        return_value=faiss_search_with_margin
        or {"user_id": None, "confidence": None, "is_ambiguous": False}
    )
    mock_faiss.save = MagicMock()
    mock_faiss.rebuild = MagicMock()
    mock_faiss._create_index = MagicMock()
    mock_faiss.user_map = {}
    mock_faiss.get_stats = MagicMock(return_value={
        "initialized": True,
        "total_vectors": 5,
        "dimension": 512,
        "index_type": "IndexFlatIP",
        "user_mappings": 5,
    })

    return (
        patch("app.services.face_service.insightface_model", mock_fn),
        patch("app.services.face_service.faiss_manager", mock_faiss),
        mock_fn,
        mock_faiss,
    )


# ===================================================================
# 1. POST /api/v1/face/register
# ===================================================================

class TestFaceRegister:
    """Tests for the face registration endpoint (student-only)."""

    def test_register_face_success(self, client, auth_headers_student, test_student):
        """Student uploads 3 face images and gets 201 with embedding_id."""
        p_fn, p_faiss, _, _ = _patch_ml_singletons(faiss_add_return=0)
        with p_fn, p_faiss:
            files = _make_upload_files(3)
            response = client.post(
                f"{PREFIX}/register", files=files, headers=auth_headers_student
            )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["embedding_id"] == 0
        assert data["user_id"] == str(test_student.id)
        assert "message" in data

    def test_register_face_unauthenticated(self, client):
        """Request without token returns 401."""
        files = _make_upload_files(3)
        response = client.post(f"{PREFIX}/register", files=files)
        assert response.status_code in (401, 403)

    def test_register_face_faculty_forbidden(self, client, auth_headers_faculty):
        """Faculty role cannot access student-only endpoint -> 403."""
        files = _make_upload_files(3)
        response = client.post(
            f"{PREFIX}/register", files=files, headers=auth_headers_faculty
        )
        assert response.status_code == 403

    def test_register_face_too_few_images(self, client, auth_headers_student, test_student):
        """Uploading fewer than 3 images raises a validation error."""
        p_fn, p_faiss, _, _ = _patch_ml_singletons()
        with p_fn, p_faiss:
            files = _make_upload_files(1)
            response = client.post(
                f"{PREFIX}/register", files=files, headers=auth_headers_student
            )

        # FaceService.register_face raises ValidationError -> 400
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False

    def test_register_face_too_many_images(self, client, auth_headers_student, test_student):
        """Uploading more than 5 images raises a validation error."""
        p_fn, p_faiss, _, _ = _patch_ml_singletons()
        with p_fn, p_faiss:
            files = _make_upload_files(7)
            response = client.post(
                f"{PREFIX}/register", files=files, headers=auth_headers_student
            )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False

    def test_register_face_duplicate(
        self, client, auth_headers_student, test_student, test_face_registration
    ):
        """Registering when face is already registered returns 400."""
        p_fn, p_faiss, _, _ = _patch_ml_singletons()
        with p_fn, p_faiss:
            files = _make_upload_files(3)
            response = client.post(
                f"{PREFIX}/register", files=files, headers=auth_headers_student
            )

        # FaceService raises ValidationError("User already has registered face...")
        assert response.status_code == 400


# ===================================================================
# 2. POST /api/v1/face/reregister
# ===================================================================

class TestFaceReregister:
    """Tests for face re-registration (replace existing)."""

    def test_reregister_success_with_existing(
        self, client, auth_headers_student, test_student, test_face_registration
    ):
        """Re-register deletes old registration and creates new one."""
        p_fn, p_faiss, _, _ = _patch_ml_singletons(faiss_add_return=1)
        with p_fn, p_faiss:
            files = _make_upload_files(3)
            response = client.post(
                f"{PREFIX}/reregister", files=files, headers=auth_headers_student
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["embedding_id"] == 1

    def test_reregister_without_existing(
        self, client, auth_headers_student, test_student
    ):
        """Re-register when no prior registration exists still works (creates new)."""
        p_fn, p_faiss, _, _ = _patch_ml_singletons(faiss_add_return=0)
        with p_fn, p_faiss:
            files = _make_upload_files(3)
            response = client.post(
                f"{PREFIX}/reregister", files=files, headers=auth_headers_student
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_reregister_unauthenticated(self, client):
        """No token -> 401."""
        files = _make_upload_files(3)
        response = client.post(f"{PREFIX}/reregister", files=files)
        assert response.status_code in (401, 403)


# ===================================================================
# 3. GET /api/v1/face/status
# ===================================================================

class TestFaceStatus:
    """Tests for face registration status endpoint."""

    def test_status_not_registered(self, client, auth_headers_student):
        """User without face registration gets registered=False."""
        response = client.get(f"{PREFIX}/status", headers=auth_headers_student)
        assert response.status_code == 200
        data = response.json()
        assert data["registered"] is False
        assert data["registered_at"] is None
        assert data["embedding_id"] is None

    def test_status_registered(
        self, client, auth_headers_student, test_face_registration
    ):
        """User with face registration gets registered=True plus metadata."""
        response = client.get(f"{PREFIX}/status", headers=auth_headers_student)
        assert response.status_code == 200
        data = response.json()
        assert data["registered"] is True
        assert data["registered_at"] is not None
        assert data["embedding_id"] == test_face_registration.embedding_id

    def test_status_unauthenticated(self, client):
        """No token -> 401."""
        response = client.get(f"{PREFIX}/status")
        assert response.status_code in (401, 403)

    def test_status_faculty_allowed(self, client, auth_headers_faculty):
        """Faculty can check their own status (any auth accepted)."""
        response = client.get(f"{PREFIX}/status", headers=auth_headers_faculty)
        assert response.status_code == 200
        assert response.json()["registered"] is False


# ===================================================================
# 4. POST /api/v1/face/recognize
# ===================================================================

class TestFaceRecognize:
    """Tests for the single-image recognition endpoint (no auth)."""

    def test_recognize_match(self, client):
        """Image that matches a user returns matched=True."""
        user_id = str(uuid.uuid4())
        p_fn, p_faiss, _, _ = _patch_ml_singletons(
            faiss_search=[(user_id, 0.85)]
        )
        with p_fn, p_faiss:
            response = client.post(
                f"{PREFIX}/recognize", json={"image": _make_test_image_base64()}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["matched"] is True
        assert data["user_id"] == user_id
        assert data["confidence"] == pytest.approx(0.85)

    def test_recognize_no_match(self, client):
        """Image that matches nobody returns matched=False."""
        p_fn, p_faiss, _, _ = _patch_ml_singletons(faiss_search=[])
        with p_fn, p_faiss:
            response = client.post(
                f"{PREFIX}/recognize", json={"image": _make_test_image_base64()}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["matched"] is False
        assert data["user_id"] is None
        assert data["confidence"] is None

    def test_recognize_invalid_base64(self, client):
        """Malformed base64 string causes decode_base64_image to raise."""
        def _raise(*_a, **_kw):
            raise ValueError("Invalid Base64")

        p_fn, p_faiss, _, _ = _patch_ml_singletons(decode_base64_image=_raise)
        with p_fn, p_faiss:
            response = client.post(
                f"{PREFIX}/recognize", json={"image": "not_valid!!!"}
            )

        # The router re-raises the exception; the global handler maps
        # generic Exception to 500 or FaceRecognitionError to 422.
        assert response.status_code in (422, 500)


# ===================================================================
# 5. POST /api/v1/face/process  (Edge API)
# ===================================================================

class TestEdgeProcess:
    """Tests for the Edge API endpoint used by Raspberry Pi devices."""

    def _payload(self, *, room_id=None, faces=1, request_id=None):
        """Build a valid EdgeProcessRequest payload."""
        return {
            "room_id": room_id or str(uuid.uuid4()).replace("-", ""),
            "timestamp": datetime.now().isoformat(),
            "faces": [{"image": _make_test_image_base64()} for _ in range(faces)],
            **({"request_id": request_id} if request_id else {}),
        }

    def test_process_single_match(self, client):
        """One face that matches a user returns processed=1, matched=[user]."""
        user_id = str(uuid.uuid4())
        p_fn, p_faiss, _, _ = _patch_ml_singletons(
            faiss_search_with_margin={
                "user_id": user_id, "confidence": 0.88, "is_ambiguous": False,
            }
        )
        with p_fn, p_faiss:
            response = client.post(f"{PREFIX}/process", json=self._payload())

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["processed"] == 1
        assert len(data["data"]["matched"]) == 1
        assert data["data"]["matched"][0]["user_id"] == user_id
        assert data["data"]["unmatched"] == 0

    def test_process_no_match(self, client):
        """Face that doesn't match anyone -> unmatched=1."""
        p_fn, p_faiss, _, _ = _patch_ml_singletons(faiss_search=[])
        with p_fn, p_faiss:
            response = client.post(f"{PREFIX}/process", json=self._payload())

        data = response.json()
        assert data["success"] is True
        assert data["data"]["processed"] == 1
        assert data["data"]["unmatched"] == 1
        assert len(data["data"]["matched"]) == 0

    def test_process_multiple_faces(self, client):
        """Batch with 3 faces, 2 matched, 1 unmatched."""
        uid1 = str(uuid.uuid4())
        uid2 = str(uuid.uuid4())

        # search_with_margin returns different results per call.
        call_count = {"n": 0}
        results_per_call = [
            {"user_id": uid1, "confidence": 0.90, "is_ambiguous": False},
            {"user_id": uid2, "confidence": 0.82, "is_ambiguous": False},
            {"user_id": None, "confidence": None, "is_ambiguous": False},
        ]

        def _search_with_margin(embedding, k=1, threshold=None, margin=None):
            idx = call_count["n"]
            call_count["n"] += 1
            if idx < len(results_per_call):
                return results_per_call[idx]
            return {"user_id": None, "confidence": None, "is_ambiguous": False}

        p_fn, p_faiss, _, mock_faiss = _patch_ml_singletons()
        mock_faiss.search_with_margin = MagicMock(side_effect=_search_with_margin)
        with p_fn, p_faiss:
            response = client.post(
                f"{PREFIX}/process", json=self._payload(faces=3)
            )

        data = response.json()
        assert data["success"] is True
        assert data["data"]["processed"] == 3
        assert len(data["data"]["matched"]) == 2
        assert data["data"]["unmatched"] == 1

    def test_process_dedup_same_request_id(self, client):
        """Second request with same request_id returns processed=0."""
        rid = "dedup-test-001"
        room = str(uuid.uuid4()).replace("-", "")
        p_fn, p_faiss, _, _ = _patch_ml_singletons(faiss_search=[])
        with p_fn, p_faiss:
            payload = self._payload(room_id=room, request_id=rid)
            r1 = client.post(f"{PREFIX}/process", json=payload)
            assert r1.status_code == 200
            assert r1.json()["data"]["processed"] == 1

            # Same payload again -> deduped
            r2 = client.post(f"{PREFIX}/process", json=payload)
            assert r2.status_code == 200
            assert r2.json()["data"]["processed"] == 0

    def test_process_missing_room_id(self, client):
        """Payload without room_id -> 422 validation error."""
        response = client.post(
            f"{PREFIX}/process",
            json={
                "timestamp": datetime.now().isoformat(),
                "faces": [{"image": _make_test_image_base64()}],
            },
        )
        assert response.status_code == 422

    def test_process_empty_faces_list(self, client):
        """Empty faces array violates min_length=1 -> 422."""
        response = client.post(
            f"{PREFIX}/process",
            json={
                "room_id": str(uuid.uuid4()).replace("-", ""),
                "timestamp": datetime.now().isoformat(),
                "faces": [],
            },
        )
        assert response.status_code == 422

    def test_process_invalid_base64_graceful(self, client):
        """Invalid base64 in a face image is handled gracefully (not a 500)."""
        def _raise(*_a, **_kw):
            raise ValueError("Invalid Base64")

        p_fn, p_faiss, mock_fn, _ = _patch_ml_singletons()
        mock_fn.decode_base64_image = MagicMock(side_effect=_raise)
        with p_fn, p_faiss:
            response = client.post(f"{PREFIX}/process", json=self._payload())

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Invalid image is counted as unmatched, not processed
        assert data["data"]["unmatched"] == 1

    def test_process_with_bbox(self, client):
        """Face data with bbox is accepted and processed."""
        p_fn, p_faiss, _, _ = _patch_ml_singletons(faiss_search=[])
        with p_fn, p_faiss:
            payload = {
                "room_id": str(uuid.uuid4()).replace("-", ""),
                "timestamp": datetime.now().isoformat(),
                "faces": [
                    {
                        "image": _make_test_image_base64(),
                        "bbox": [10, 20, 112, 112],
                    }
                ],
            }
            response = client.post(f"{PREFIX}/process", json=payload)

        assert response.status_code == 200
        assert response.json()["success"] is True


# ===================================================================
# 6. GET /api/v1/face/statistics
# ===================================================================

class TestFaceStatistics:
    """Tests for the face recognition statistics endpoint."""

    def test_get_statistics_authenticated(self, client, auth_headers_student):
        """Authenticated user can retrieve statistics."""
        p_fn, p_faiss, _, _ = _patch_ml_singletons()
        with p_fn, p_faiss:
            response = client.get(
                f"{PREFIX}/statistics", headers=auth_headers_student
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "faiss_initialized" in data["data"]

    def test_get_statistics_unauthenticated(self, client):
        """No token -> 401."""
        response = client.get(f"{PREFIX}/statistics")
        assert response.status_code in (401, 403)


# ===================================================================
# 7. DELETE /api/v1/face/{user_id}
# ===================================================================

class TestFaceDeregister:
    """Tests for face deregistration (ownership + admin rules)."""

    def test_deregister_own_face(
        self, client, auth_headers_student, test_student, test_face_registration
    ):
        """Student deregisters their own face -> 200 success."""
        p_fn, p_faiss, _, _ = _patch_ml_singletons()
        with p_fn, p_faiss:
            response = client.delete(
                f"{PREFIX}/{test_student.id}", headers=auth_headers_student
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data

    def test_deregister_other_student_forbidden(
        self, client, auth_headers_student
    ):
        """Student cannot deregister another user's face -> 403."""
        other_id = str(uuid.uuid4())
        response = client.delete(
            f"{PREFIX}/{other_id}", headers=auth_headers_student
        )
        assert response.status_code == 403

    def test_deregister_admin_can_delete_any(
        self, client, auth_headers_admin, test_student, test_face_registration
    ):
        """Admin can deregister any user's face."""
        p_fn, p_faiss, _, _ = _patch_ml_singletons()
        with p_fn, p_faiss:
            response = client.delete(
                f"{PREFIX}/{test_student.id}", headers=auth_headers_admin
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_deregister_no_registration_404(
        self, client, auth_headers_student, test_student
    ):
        """Deregistering when no face is registered raises NotFoundError -> 404."""
        p_fn, p_faiss, _, _ = _patch_ml_singletons()
        with p_fn, p_faiss:
            response = client.delete(
                f"{PREFIX}/{test_student.id}", headers=auth_headers_student
            )

        # face_repo.deactivate raises NotFoundError -> 404
        assert response.status_code == 404

    def test_deregister_unauthenticated(self, client):
        """No token -> 401."""
        response = client.delete(f"{PREFIX}/{uuid.uuid4()}")
        assert response.status_code in (401, 403)
