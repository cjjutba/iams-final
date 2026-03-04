"""
Unit Tests for FaceService

Tests all FaceService methods:
  - register_face (validation, embedding generation, FAISS add, DB save)
  - recognize_face (embedding, FAISS search, match/no-match)
  - recognize_batch (multiple images, partial failures)
  - deregister_face (deactivate + rebuild)
  - reregister_face (delete old + register new)
  - rebuild_faiss_index (active registrations, empty case)
  - get_face_status (registered vs not)
  - get_statistics (counts + FAISS stats)
  - load_faiss_index (index + user_map population)

All ML dependencies (FaceNet, FAISS) are mocked to keep tests fast and isolated.
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import numpy as np
import pytest

from app.services.face_service import FaceService
from app.utils.exceptions import ValidationError, FaceRecognitionError, NotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_embedding():
    """Create a random 512-dim L2-normalised embedding."""
    emb = np.random.randn(512).astype(np.float32)
    return emb / np.linalg.norm(emb)


def _make_mock_upload_file(content=b"fake_image_data", filename="test.jpg"):
    """Create a mock UploadFile with async read()."""
    mock_file = MagicMock()
    mock_file.read = AsyncMock(return_value=content)
    mock_file.filename = filename
    return mock_file


def _make_face_service(db_session):
    """
    Instantiate FaceService and replace ML singletons with mocks.

    Returns (service, mock_facenet, mock_faiss).
    """
    service = FaceService(db_session)

    mock_facenet = MagicMock(spec=['get_embedding', 'get_embeddings_batch', 'app', 'load_model'])
    mock_facenet.get_embedding = MagicMock(return_value=_make_embedding())

    mock_faiss = MagicMock()
    mock_faiss.add = MagicMock(return_value=0)
    # add_batch returns sequential FAISS IDs starting from 0
    mock_faiss.add_batch = MagicMock(side_effect=lambda embs, uids: list(range(len(uids))))
    mock_faiss.save = MagicMock()
    mock_faiss.search = MagicMock(return_value=[])
    mock_faiss.rebuild = MagicMock()
    mock_faiss.load_or_create_index = MagicMock()
    mock_faiss.user_map = {}
    mock_faiss._create_index = MagicMock()
    mock_faiss.get_stats = MagicMock(return_value={
        "initialized": True,
        "total_vectors": 0,
        "dimension": 512,
        "index_type": "IndexFlatIP",
        "user_mappings": 0,
    })

    service.facenet = mock_facenet
    service.faiss = mock_faiss

    return service, mock_facenet, mock_faiss


# ===================================================================
# register_face
# ===================================================================

class TestFaceServiceRegister:
    """Tests for FaceService.register_face"""

    @pytest.mark.asyncio
    async def test_register_face_success_3_images(self, db_session):
        """Registering with exactly 3 images (minimum) should succeed."""
        service, mock_fn, mock_faiss = _make_face_service(db_session)
        user_id = str(uuid.uuid4())
        images = [_make_mock_upload_file() for _ in range(3)]

        faiss_id, msg, quality_reports = await service.register_face(user_id, images)

        assert faiss_id == 0
        assert "successfully" in msg.lower()
        assert mock_fn.get_embedding.call_count == 3
        mock_faiss.add_batch.assert_called_once()
        mock_faiss.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_face_success_5_images(self, db_session):
        """Registering with exactly 5 images (maximum) should succeed."""
        service, mock_fn, mock_faiss = _make_face_service(db_session)
        user_id = str(uuid.uuid4())
        images = [_make_mock_upload_file() for _ in range(5)]

        faiss_id, msg, _ = await service.register_face(user_id, images)

        assert faiss_id == 0
        assert mock_fn.get_embedding.call_count == 5

    @pytest.mark.asyncio
    async def test_register_face_too_few_images(self, db_session):
        """Providing fewer than MIN_FACE_IMAGES should raise ValidationError."""
        service, _, _ = _make_face_service(db_session)
        user_id = str(uuid.uuid4())
        images = [_make_mock_upload_file() for _ in range(2)]

        with pytest.raises(ValidationError, match="Minimum"):
            await service.register_face(user_id, images)

    @pytest.mark.asyncio
    async def test_register_face_too_many_images(self, db_session):
        """Providing more than MAX_FACE_IMAGES should raise ValidationError."""
        service, _, _ = _make_face_service(db_session)
        user_id = str(uuid.uuid4())
        images = [_make_mock_upload_file() for _ in range(6)]

        with pytest.raises(ValidationError, match="Maximum"):
            await service.register_face(user_id, images)

    @pytest.mark.asyncio
    async def test_register_face_duplicate_user(self, db_session, test_face_registration):
        """Registering a user who already has a face should raise ValidationError."""
        service, _, _ = _make_face_service(db_session)
        user_id = str(test_face_registration.user_id)
        images = [_make_mock_upload_file() for _ in range(3)]

        with pytest.raises(ValidationError, match="already has registered face"):
            await service.register_face(user_id, images)

    @pytest.mark.asyncio
    async def test_register_face_embedding_failure(self, db_session):
        """If FaceNet raises ValueError, service should raise FaceRecognitionError."""
        service, mock_fn, _ = _make_face_service(db_session)
        mock_fn.get_embedding.side_effect = ValueError("No face detected")

        user_id = str(uuid.uuid4())
        images = [_make_mock_upload_file() for _ in range(3)]

        with pytest.raises(FaceRecognitionError, match="Image 1"):
            await service.register_face(user_id, images)

    @pytest.mark.asyncio
    async def test_register_face_faiss_add_failure(self, db_session):
        """If FAISS add_batch fails, service should raise FaceRecognitionError."""
        service, _, mock_faiss = _make_face_service(db_session)
        mock_faiss.add_batch.side_effect = RuntimeError("Index not initialized")

        user_id = str(uuid.uuid4())
        images = [_make_mock_upload_file() for _ in range(3)]

        with pytest.raises(FaceRecognitionError, match="Failed to index"):
            await service.register_face(user_id, images)

    @pytest.mark.asyncio
    async def test_register_stores_individual_embeddings(self, db_session):
        """Each embedding passed to FAISS add_batch should be L2-normalised."""
        service, mock_fn, mock_faiss = _make_face_service(db_session)

        emb1 = np.ones(512, dtype=np.float32)
        emb2 = np.ones(512, dtype=np.float32) * 2
        emb3 = np.ones(512, dtype=np.float32) * 3
        mock_fn.get_embedding.side_effect = [emb1, emb2, emb3]

        user_id = str(uuid.uuid4())
        images = [_make_mock_upload_file() for _ in range(3)]

        await service.register_face(user_id, images)

        # add_batch should receive 3 individually L2-normalised embeddings
        mock_faiss.add_batch.assert_called_once()
        call_args = mock_faiss.add_batch.call_args
        batch_embs = call_args[0][0]  # First positional arg: numpy array [3, 512]
        user_ids = call_args[0][1]    # Second positional arg: list of user_ids
        assert batch_embs.shape == (3, 512)
        assert len(user_ids) == 3
        assert all(uid == user_id for uid in user_ids)
        for i in range(3):
            norm = np.linalg.norm(batch_embs[i])
            assert abs(norm - 1.0) < 1e-5, f"Embedding {i} norm should be ~1.0, got {norm}"

    @pytest.mark.asyncio
    async def test_register_face_saves_to_db(self, db_session):
        """After successful registration the DB should contain a FaceRegistration row
        and individual FaceEmbedding rows."""
        from app.models.face_registration import FaceRegistration
        from app.models.face_embedding import FaceEmbedding

        service, _, _ = _make_face_service(db_session)
        user_id = str(uuid.uuid4())
        images = [_make_mock_upload_file() for _ in range(3)]

        faiss_id, _, _ = await service.register_face(user_id, images)

        row = db_session.query(FaceRegistration).filter(
            FaceRegistration.user_id == uuid.UUID(user_id)
        ).first()
        assert row is not None
        assert row.embedding_id == faiss_id
        assert row.is_active is True
        assert row.embedding_vector is not None

        # Verify individual FaceEmbedding rows were created
        emb_rows = db_session.query(FaceEmbedding).filter(
            FaceEmbedding.registration_id == row.id
        ).all()
        assert len(emb_rows) == 3
        assert emb_rows[0].angle_label == "center"
        assert emb_rows[1].angle_label == "left"
        assert emb_rows[2].angle_label == "right"


# ===================================================================
# register_face with quality gating
# ===================================================================

class TestFaceServiceRegisterQuality:
    """Tests for quality gating during registration."""

    @pytest.mark.asyncio
    async def test_register_with_quality_gating_success(self, db_session):
        """When quality checks pass, registration should return quality reports."""
        service = FaceService(db_session)
        user_id = str(uuid.uuid4())

        good_image_bgr = np.random.RandomState(42).randint(
            60, 200, (320, 320, 3), dtype=np.uint8
        )
        mock_facenet = MagicMock()
        mock_facenet.get_face_with_quality = MagicMock(return_value={
            "embedding": _make_embedding(),
            "det_score": 0.95,
            "bbox": (50, 50, 200, 200),
            "image_bgr": good_image_bgr,
        })

        mock_faiss = MagicMock()
        mock_faiss.add_batch = MagicMock(side_effect=lambda embs, uids: list(range(len(uids))))
        mock_faiss.save = MagicMock()

        service.facenet = mock_facenet
        service.faiss = mock_faiss

        images = [_make_mock_upload_file() for _ in range(3)]
        faiss_id, msg, quality_reports = await service.register_face(user_id, images)

        assert faiss_id == 0
        assert quality_reports is not None
        assert len(quality_reports) == 3
        assert all(q.passed for q in quality_reports)

    @pytest.mark.asyncio
    async def test_register_rejects_blurry_image(self, db_session):
        """When an image is too blurry, registration should raise ValidationError."""
        service = FaceService(db_session)
        user_id = str(uuid.uuid4())

        blurry_image = np.ones((320, 320, 3), dtype=np.uint8) * 128
        mock_facenet = MagicMock()
        mock_facenet.get_face_with_quality = MagicMock(return_value={
            "embedding": _make_embedding(),
            "det_score": 0.95,
            "bbox": (50, 50, 200, 200),
            "image_bgr": blurry_image,
        })

        service.facenet = mock_facenet
        service.faiss = MagicMock()

        images = [_make_mock_upload_file() for _ in range(3)]
        with pytest.raises(ValidationError, match="rejected"):
            await service.register_face(user_id, images)


# ===================================================================
# recognize_face
# ===================================================================

class TestFaceServiceRecognize:
    """Tests for FaceService.recognize_face"""

    @pytest.mark.asyncio
    async def test_recognize_face_match(self, db_session):
        """When FAISS returns a match, recognize_face should return (user_id, confidence)."""
        service, _, mock_faiss = _make_face_service(db_session)
        expected_uid = str(uuid.uuid4())
        mock_faiss.search.return_value = [(expected_uid, 0.85)]

        user_id, confidence = await service.recognize_face(b"image_bytes")

        assert user_id == expected_uid
        assert confidence == 0.85

    @pytest.mark.asyncio
    async def test_recognize_face_no_match(self, db_session):
        """When FAISS returns empty results, recognize_face should return (None, None)."""
        service, _, mock_faiss = _make_face_service(db_session)
        mock_faiss.search.return_value = []

        user_id, confidence = await service.recognize_face(b"image_bytes")

        assert user_id is None
        assert confidence is None

    @pytest.mark.asyncio
    async def test_recognize_face_custom_threshold(self, db_session):
        """Custom threshold should be forwarded to FAISS search."""
        service, _, mock_faiss = _make_face_service(db_session)
        mock_faiss.search.return_value = []

        await service.recognize_face(b"image_bytes", threshold=0.8)

        mock_faiss.search.assert_called_once()
        _, kwargs = mock_faiss.search.call_args
        assert kwargs.get("threshold") == 0.8 or mock_faiss.search.call_args[0][2] == 0.8

    @pytest.mark.asyncio
    async def test_recognize_face_embedding_error(self, db_session):
        """If FaceNet fails, recognize_face should raise FaceRecognitionError."""
        service, mock_fn, _ = _make_face_service(db_session)
        mock_fn.get_embedding.side_effect = ValueError("No face detected")

        with pytest.raises(FaceRecognitionError, match="Face recognition failed"):
            await service.recognize_face(b"bad_image")


# ===================================================================
# recognize_batch
# ===================================================================

class TestFaceServiceRecognizeBatch:
    """Tests for FaceService.recognize_batch (batch embedding + batch FAISS search)"""

    @pytest.mark.asyncio
    async def test_recognize_batch_all_matched(self, db_session):
        """Batch recognition should return a result dict for every input image."""
        service, _, _ = _make_face_service(db_session)
        uid1 = str(uuid.uuid4())
        uid2 = str(uuid.uuid4())

        emb_batch = np.stack([_make_embedding(), _make_embedding()])

        with patch("app.services.face_service.Image") as mock_pil, \
             patch("app.services.face_service.insightface_model") as mock_fn, \
             patch("app.services.face_service.faiss_manager") as mock_faiss:
            # Phase 1: decoding returns mock PIL images
            mock_pil.open.return_value.convert.return_value = MagicMock()
            # Phase 2: batch embedding
            mock_fn.get_embeddings_batch.return_value = emb_batch
            # Phase 3: batch FAISS search — one result list per query
            mock_faiss.search_batch.return_value = [
                [(uid1, 0.90)],
                [(uid2, 0.75)],
            ]

            results = await service.recognize_batch([b"img1", b"img2"])

        assert len(results) == 2
        assert results[0]["user_id"] == uid1
        assert results[0]["confidence"] == pytest.approx(0.90)
        assert results[1]["user_id"] == uid2
        assert results[1]["confidence"] == pytest.approx(0.75)

    @pytest.mark.asyncio
    async def test_recognize_batch_partial_failure(self, db_session):
        """If one image fails to decode, the others should still be processed; failed entry gets error key."""
        service, _, _ = _make_face_service(db_session)
        uid = str(uuid.uuid4())

        emb_batch = np.stack([_make_embedding()])

        with patch("app.services.face_service.Image") as mock_pil, \
             patch("app.services.face_service.insightface_model") as mock_fn, \
             patch("app.services.face_service.faiss_manager") as mock_faiss:
            # First image decodes fine, second raises
            good_img = MagicMock()
            mock_convert = MagicMock()

            call_count = 0
            def _open_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise ValueError("Corrupt image")
                return mock_convert

            mock_pil.open.side_effect = _open_side_effect
            mock_convert.convert.return_value = good_img

            mock_fn.get_embeddings_batch.return_value = emb_batch
            mock_faiss.search_batch.return_value = [[(uid, 0.80)]]

            results = await service.recognize_batch([b"good", b"bad"])

        assert len(results) == 2
        # First result (index 0) should be a match
        assert results[0]["user_id"] == uid
        assert results[0]["confidence"] == pytest.approx(0.80)
        # Second result (index 1) should indicate failure
        assert results[1]["user_id"] is None
        assert "error" in results[1]


# ===================================================================
# deregister_face
# ===================================================================

class TestFaceServiceDeregister:
    """Tests for FaceService.deregister_face"""

    @pytest.mark.asyncio
    async def test_deregister_face_success(self, db_session, test_face_registration):
        """Deregistering should deactivate the DB record and trigger FAISS rebuild."""
        service, _, mock_faiss = _make_face_service(db_session)

        user_id = str(test_face_registration.user_id)
        await service.deregister_face(user_id)

        # The registration should now be inactive in the DB
        db_session.refresh(test_face_registration)
        assert test_face_registration.is_active is False

        # rebuild_faiss_index calls faiss.rebuild (or _create_index for empty)
        # Since we deactivated the only registration, get_active_embeddings returns []
        # That triggers the empty-index path which calls faiss._create_index
        assert mock_faiss._create_index.called or mock_faiss.rebuild.called

    @pytest.mark.asyncio
    async def test_deregister_face_not_found(self, db_session):
        """Deregistering a non-existent user should raise NotFoundError."""
        service, _, _ = _make_face_service(db_session)

        with pytest.raises(NotFoundError):
            await service.deregister_face(str(uuid.uuid4()))


# ===================================================================
# reregister_face
# ===================================================================

class TestFaceServiceReregister:
    """Tests for FaceService.reregister_face"""

    @pytest.mark.asyncio
    async def test_reregister_face_replaces_old(self, db_session, test_face_registration):
        """Re-register should delete old registration and create new one."""
        from app.models.face_registration import FaceRegistration

        service, mock_fn, mock_faiss = _make_face_service(db_session)
        user_id = str(test_face_registration.user_id)
        old_id = test_face_registration.id
        images = [_make_mock_upload_file() for _ in range(3)]

        faiss_id, msg, _ = await service.reregister_face(user_id, images)

        assert "re-registered" in msg.lower()
        # Old registration should be gone
        old_row = db_session.query(FaceRegistration).filter(
            FaceRegistration.id == old_id
        ).first()
        assert old_row is None

        # New registration should exist
        new_row = db_session.query(FaceRegistration).filter(
            FaceRegistration.user_id == uuid.UUID(user_id),
            FaceRegistration.is_active == True
        ).first()
        assert new_row is not None

    @pytest.mark.asyncio
    async def test_reregister_face_no_previous(self, db_session):
        """Re-register with no previous registration should still succeed (acts like first register)."""
        service, _, _ = _make_face_service(db_session)
        user_id = str(uuid.uuid4())
        images = [_make_mock_upload_file() for _ in range(3)]

        faiss_id, msg, _ = await service.reregister_face(user_id, images)

        assert "re-registered" in msg.lower()
        assert faiss_id == 0


# ===================================================================
# rebuild_faiss_index
# ===================================================================

class TestFaceServiceRebuildIndex:
    """Tests for FaceService.rebuild_faiss_index"""

    @pytest.mark.asyncio
    async def test_rebuild_with_active_registrations(self, db_session, test_face_registration):
        """Rebuild should pass all active embedding data to faiss.rebuild."""
        service, _, mock_faiss = _make_face_service(db_session)

        await service.rebuild_faiss_index()

        mock_faiss.rebuild.assert_called_once()
        embeddings_data = mock_faiss.rebuild.call_args[0][0]
        assert len(embeddings_data) == 1
        embedding_array, uid = embeddings_data[0]
        assert embedding_array.shape == (512,)
        assert uid == str(test_face_registration.user_id)

    @pytest.mark.asyncio
    async def test_rebuild_with_no_registrations(self, db_session):
        """Rebuild with no active registrations should create an empty index."""
        service, _, mock_faiss = _make_face_service(db_session)

        await service.rebuild_faiss_index()

        # Empty path: creates fresh index, clears user_map, saves
        mock_faiss._create_index.assert_called_once()
        mock_faiss.save.assert_called_once()


# ===================================================================
# get_face_status
# ===================================================================

class TestFaceServiceGetStatus:
    """Tests for FaceService.get_face_status"""

    def test_get_face_status_registered(self, db_session, test_face_registration):
        """Should return registered=True with metadata when a registration exists."""
        service, _, _ = _make_face_service(db_session)
        user_id = str(test_face_registration.user_id)

        status = service.get_face_status(user_id)

        assert status["registered"] is True
        assert status["embedding_id"] == test_face_registration.embedding_id
        assert status["registered_at"] is not None

    def test_get_face_status_not_registered(self, db_session):
        """Should return registered=False when no registration exists."""
        service, _, _ = _make_face_service(db_session)

        status = service.get_face_status(str(uuid.uuid4()))

        assert status["registered"] is False
        assert status["registered_at"] is None
        assert status["embedding_id"] is None


# ===================================================================
# get_statistics
# ===================================================================

class TestFaceServiceGetStatistics:
    """Tests for FaceService.get_statistics"""

    def test_get_statistics_empty(self, db_session):
        """With no registrations, active_registrations should be 0."""
        service, _, mock_faiss = _make_face_service(db_session)

        stats = service.get_statistics()

        assert stats["active_registrations"] == 0
        assert stats["faiss_initialized"] is True
        assert stats["faiss_vectors"] == 0

    def test_get_statistics_with_registration(self, db_session, test_face_registration):
        """With one registration, active_registrations should be 1."""
        service, _, mock_faiss = _make_face_service(db_session)
        mock_faiss.get_stats.return_value = {
            "initialized": True,
            "total_vectors": 1,
            "dimension": 512,
            "index_type": "IndexFlatIP",
            "user_mappings": 1,
        }

        stats = service.get_statistics()

        assert stats["active_registrations"] == 1
        assert stats["faiss_vectors"] == 1


# ===================================================================
# load_faiss_index
# ===================================================================

class TestFaceServiceLoadIndex:
    """Tests for FaceService.load_faiss_index"""

    def test_load_faiss_index_populates_user_map(self, db_session, test_face_registration):
        """load_faiss_index should call load_or_create_index and populate user_map from DB."""
        service, _, mock_faiss = _make_face_service(db_session)

        service.load_faiss_index()

        mock_faiss.load_or_create_index.assert_called_once()
        # user_map should contain the mapping from embedding_id -> user_id
        assert mock_faiss.user_map[test_face_registration.embedding_id] == str(
            test_face_registration.user_id
        )

    def test_load_faiss_index_empty_db(self, db_session):
        """With no registrations, user_map should remain empty after load."""
        service, _, mock_faiss = _make_face_service(db_session)

        service.load_faiss_index()

        mock_faiss.load_or_create_index.assert_called_once()
        assert len(mock_faiss.user_map) == 0


# ===================================================================
# reconcile_faiss_index
# ===================================================================

class TestFaceServiceReconcileIndex:
    """Tests for FaceService.reconcile_faiss_index (startup user_map restoration)"""

    def test_reconcile_always_rebuilds_user_map_when_counts_match(
        self, db_session, test_face_registration
    ):
        """
        Even when FAISS vector count equals active DB registrations,
        reconcile must call faiss_manager.rebuild to populate user_map.

        Regression test: previously the 'counts match' branch did nothing,
        leaving user_map empty after every normal server restart, which
        caused all face matches to be silently dropped.
        """
        with patch("app.services.face_service.faiss_manager") as mock_faiss:
            mock_index = MagicMock()
            mock_index.ntotal = 1  # matches the 1 active DB registration
            mock_faiss.index = mock_index
            mock_faiss.rebuild = MagicMock()

            result = FaceService.reconcile_faiss_index(db_session)

        # No mismatch → should return False
        assert result is False
        # rebuild must still be called to populate user_map
        mock_faiss.rebuild.assert_called_once()
        embeddings_data = mock_faiss.rebuild.call_args[0][0]
        assert len(embeddings_data) == 1
        _, uid = embeddings_data[0]
        assert uid == str(test_face_registration.user_id)

    def test_reconcile_rebuilds_on_mismatch(self, db_session, test_face_registration):
        """When FAISS count differs from DB count, reconcile rebuilds and returns True."""
        with patch("app.services.face_service.faiss_manager") as mock_faiss:
            mock_index = MagicMock()
            mock_index.ntotal = 0  # mismatch: DB has 1, FAISS has 0
            mock_faiss.index = mock_index
            mock_faiss.rebuild = MagicMock()

            result = FaceService.reconcile_faiss_index(db_session)

        assert result is True
        mock_faiss.rebuild.assert_called_once()

    def test_reconcile_skips_rebuild_when_no_registrations(self, db_session):
        """With no active registrations, reconcile should not call rebuild."""
        with patch("app.services.face_service.faiss_manager") as mock_faiss:
            mock_index = MagicMock()
            mock_index.ntotal = 0
            mock_faiss.index = mock_index
            mock_faiss.rebuild = MagicMock()

            result = FaceService.reconcile_faiss_index(db_session)

        assert result is False
        mock_faiss.rebuild.assert_not_called()
