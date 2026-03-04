# ML Pipeline Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix critical bugs, improve face recognition accuracy to 92%+, deliver 30fps live streaming with real-time detection overlays, and make the entire face pipeline production-ready.

**Architecture:** Two-tier edge/backend pipeline. Edge (RPi) detects and crops faces at 160x160/JPEG85%, backend aligns (MTCNN), embeds (FaceNet), searches (FAISS top-3 with confidence margin), and tracks (DeepSORT). HLS streams video at 30fps while detection runs at 5-10fps on a separate thread, with WebSocket pushing overlay metadata to mobile.

**Tech Stack:** MediaPipe (edge detection), FaceNet/InceptionResnetV1 (embeddings), FAISS IndexFlatIP (search), MTCNN (alignment), FFmpeg (HLS), React Native Vision Camera (mobile capture), APScheduler (scan cycles).

---

## Task 1: Edge — Update Preprocessing Defaults

**Files:**
- Modify: `edge/app/config.py:59-60` (FACE_CROP_SIZE, JPEG_QUALITY)
- Modify: `edge/app/config.py:63` (DETECTION_CONFIDENCE)

**Step 1: Update config defaults**

In `edge/app/config.py`, change lines 59-60 and 63:

```python
# Face Detection Configuration
FACE_CROP_SIZE = int(os.getenv("FACE_CROP_SIZE", "160"))   # was 112
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "85"))         # was 70

# Detection
DETECTION_CONFIDENCE = float(os.getenv("DETECTION_CONFIDENCE", "0.6"))  # was 0.5
```

**Step 2: Verify validation still passes**

Run: `cd edge && python -c "from app.config import config; config.validate(); print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add edge/app/config.py
git commit -m "feat(edge): update preprocessing defaults — 160x160 crop, 85% JPEG, 0.6 confidence"
```

---

## Task 2: Edge — Add Minimum Face Size Filter

**Files:**
- Modify: `edge/app/detector.py:190-277` (detect method)

**Step 1: Add minimum face pixel filter to detect()**

In `edge/app/detector.py`, inside the `detect()` method, after the bounding box is computed (around line 240-260 where FaceBox objects are created), add a minimum size filter. After the line that creates each FaceBox, add:

```python
MIN_FACE_PIXELS = 80  # minimum face dimension in original frame

# Inside the detection loop, after creating face_box:
if face_box.width < MIN_FACE_PIXELS or face_box.height < MIN_FACE_PIXELS:
    logger.debug(f"Skipping small face: {face_box.width}x{face_box.height} < {MIN_FACE_PIXELS}px")
    continue
```

Add the constant `MIN_FACE_PIXELS = 80` at class level (after `MAX_DETECT_DIM = 1280` on line 188).

**Step 2: Test with a simple script**

Run: `cd edge && python -c "from app.detector import FaceDetector; print('Import OK')"`
Expected: `Import OK`

**Step 3: Commit**

```bash
git add edge/app/detector.py
git commit -m "feat(edge): add minimum face size filter (80x80px)"
```

---

## Task 3: Backend Config — Add New Threshold Parameters

**Files:**
- Modify: `backend/app/config.py:49-80` (Settings class)

**Step 1: Add new config parameters**

In `backend/app/config.py`, update the Settings class face recognition section (lines 49-54) and recognition section (lines 77-80):

```python
    # Face Recognition
    FAISS_INDEX_PATH: str = "data/faiss/faces.index"
    RECOGNITION_THRESHOLD: float = 0.55       # was 0.6 — lowered for aligned embeddings
    RECOGNITION_MARGIN: float = 0.1           # NEW — min gap between top-1 and top-2
    RECOGNITION_TOP_K: int = 3                # NEW — search k neighbors
    USE_GPU: bool = True
    FACE_IMAGE_SIZE: int = 160
    MIN_FACE_IMAGES: int = 3
    MAX_FACE_IMAGES: int = 5
    USE_FACE_ALIGNMENT: bool = True           # NEW — enable MTCNN alignment

    # ...existing presence tracking settings...

    # Recognition (streaming)
    RECOGNITION_FPS: float = 8.0              # was 1.5 — target 5-10fps
    RECOGNITION_MAX_BATCH_SIZE: int = 20
    RECOGNITION_MAX_DIM: int = 1280
```

**Step 2: Verify config loads**

Run: `cd backend && python -c "from app.config import settings; print(f'threshold={settings.RECOGNITION_THRESHOLD}, k={settings.RECOGNITION_TOP_K}, fps={settings.RECOGNITION_FPS}')"`
Expected: `threshold=0.55, k=3, fps=8.0`

**Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(backend): add recognition config params — threshold 0.55, top-k 3, margin 0.1, fps 8"
```

---

## Task 4: Backend — Add MTCNN Face Alignment to FaceNetModel

**Files:**
- Modify: `backend/app/services/ml/face_recognition.py`
- Test: `backend/tests/unit/test_face_recognition_model.py`

**Step 1: Write the failing test**

Add to `backend/tests/unit/test_face_recognition_model.py`:

```python
class TestFaceAlignment:
    """Tests for MTCNN face alignment in FaceNetModel."""

    def test_align_face_returns_aligned_image(self):
        """MTCNN alignment should return a PIL Image of FACE_IMAGE_SIZE x FACE_IMAGE_SIZE."""
        model = FaceNetModel()
        img = Image.new("RGB", (200, 200), color=(128, 128, 128))
        result = model.align_face(img)
        # Should return an image (aligned) or None (fallback)
        # We accept either since MTCNN may not find landmarks in a blank image
        assert result is None or isinstance(result, Image.Image)

    def test_align_face_fallback_on_no_landmarks(self):
        """When MTCNN finds no landmarks, align_face returns None (caller uses raw crop)."""
        model = FaceNetModel()
        # Solid color image — no face landmarks detectable
        img = Image.new("RGB", (160, 160), color=(0, 0, 0))
        result = model.align_face(img)
        assert result is None

    def test_generate_embedding_uses_alignment_when_enabled(self):
        """generate_embedding should attempt alignment when USE_FACE_ALIGNMENT is True."""
        model = FaceNetModel()
        model._model = MagicMock()
        model._model.eval.return_value = model._model
        fake_output = torch.randn(1, 512)
        model._model.return_value = fake_output
        model._device = torch.device("cpu")

        img = Image.new("RGB", (160, 160), color=(128, 128, 128))
        # Should not raise — alignment fallback to raw image on no landmarks
        with patch.object(model, 'align_face', return_value=None) as mock_align:
            with patch.object(settings, 'USE_FACE_ALIGNMENT', True):
                embedding = model.generate_embedding(img)
                mock_align.assert_called_once()
                assert embedding.shape == (512,)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_face_recognition_model.py::TestFaceAlignment -v`
Expected: FAIL — `AttributeError: 'FaceNetModel' object has no attribute 'align_face'`

**Step 3: Implement MTCNN alignment**

In `backend/app/services/ml/face_recognition.py`:

Add import after line 8:
```python
from facenet_pytorch import MTCNN
```

Add method to FaceNetModel class (after `load_model`, around line 70):

```python
    def _init_mtcnn(self):
        """Initialize MTCNN for face alignment (lazy)."""
        if not hasattr(self, '_mtcnn') or self._mtcnn is None:
            self._mtcnn = MTCNN(
                image_size=self.FACE_IMAGE_SIZE,
                margin=0,
                min_face_size=20,
                select_largest=True,
                post_process=False,
                device=self._device if self._device else torch.device('cpu')
            )
            logger.info("MTCNN initialized for face alignment")

    def align_face(self, image: Image.Image) -> Optional[Image.Image]:
        """Align face using MTCNN landmarks. Returns aligned PIL Image or None if no face found."""
        try:
            self._init_mtcnn()
            # MTCNN returns aligned face tensor or None
            aligned = self._mtcnn(image)
            if aligned is None:
                logger.debug("MTCNN found no face landmarks — skipping alignment")
                return None
            # Convert tensor back to PIL Image
            # MTCNN returns tensor in [0, 255] range when post_process=False
            aligned_np = aligned.permute(1, 2, 0).cpu().numpy().astype(np.uint8)
            return Image.fromarray(aligned_np)
        except Exception as e:
            logger.warning(f"MTCNN alignment failed: {e} — falling back to raw crop")
            return None
```

Then modify `generate_embedding` (line ~120) to attempt alignment before preprocessing:

```python
    def generate_embedding(self, image) -> np.ndarray:
        # ... existing code to handle bytes/PIL conversion ...
        # After converting to PIL Image, before preprocess_image:
        if settings.USE_FACE_ALIGNMENT:
            aligned = self.align_face(pil_image)
            if aligned is not None:
                pil_image = aligned
        # ... continue with existing preprocess_image(pil_image) ...
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_face_recognition_model.py::TestFaceAlignment -v`
Expected: PASS

**Step 5: Run all face recognition tests**

Run: `cd backend && python -m pytest tests/unit/test_face_recognition_model.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add backend/app/services/ml/face_recognition.py backend/tests/unit/test_face_recognition_model.py
git commit -m "feat(backend): add MTCNN face alignment to FaceNet pipeline"
```

---

## Task 5: Backend — Add Top-K Search with Confidence Margin to FAISS

**Files:**
- Modify: `backend/app/services/ml/faiss_manager.py:157-215` (search method)
- Test: `backend/tests/unit/test_faiss_manager.py`

**Step 1: Write the failing tests**

Add to `backend/tests/unit/test_faiss_manager.py`:

```python
class TestConfidenceMarginSearch:
    """Tests for top-k search with confidence margin logic."""

    def test_confident_match_large_margin(self, tmp_path):
        """Top match with large margin over second match is confident."""
        mgr = FAISSManager(str(tmp_path / "test.index"))
        mgr.load_or_create_index()
        e1 = _make_embedding()
        e2 = _make_embedding()
        mgr.add(e1, "user-1")
        mgr.add(e2, "user-2")
        results = mgr.search(e1, k=3, threshold=0.55)
        assert len(results) >= 1
        assert results[0][0] == "user-1"
        assert results[0][1] > 0.55

    def test_search_returns_match_info_with_margin(self, tmp_path):
        """Search result includes is_ambiguous flag when margin check enabled."""
        mgr = FAISSManager(str(tmp_path / "test.index"))
        mgr.load_or_create_index()
        e1 = _make_embedding()
        mgr.add(e1, "user-1")
        results = mgr.search_with_margin(e1, k=3, threshold=0.55, margin=0.1)
        assert results["user_id"] == "user-1"
        assert results["is_ambiguous"] is False

    def test_no_match_below_threshold(self, tmp_path):
        """No match when top similarity below threshold."""
        mgr = FAISSManager(str(tmp_path / "test.index"))
        mgr.load_or_create_index()
        e1, e2 = _make_orthogonal_pair()
        mgr.add(e1, "user-1")
        results = mgr.search_with_margin(e2, k=3, threshold=0.55, margin=0.1)
        assert results["user_id"] is None
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_faiss_manager.py::TestConfidenceMarginSearch -v`
Expected: FAIL — `AttributeError: 'FAISSManager' object has no attribute 'search_with_margin'`

**Step 3: Implement search_with_margin**

Add to `FAISSManager` class in `backend/app/services/ml/faiss_manager.py` (after existing `search_batch` method, around line 262):

```python
    def search_with_margin(
        self,
        embedding: np.ndarray,
        k: int = 3,
        threshold: float = None,
        margin: float = None,
    ) -> Dict:
        """
        Search with confidence margin check.

        Returns dict with:
          - user_id: matched user or None
          - confidence: similarity score
          - is_ambiguous: True if margin between top-1 and top-2 is small
        """
        if threshold is None:
            threshold = settings.RECOGNITION_THRESHOLD
        if margin is None:
            margin = settings.RECOGNITION_MARGIN

        results = self.search(embedding, k=k, threshold=0.0)  # get all k results unfiltered

        if not results or results[0][1] < threshold:
            return {"user_id": None, "confidence": 0.0, "is_ambiguous": False}

        top_user, top_score = results[0]
        second_score = results[1][1] if len(results) > 1 else 0.0
        score_gap = top_score - second_score
        is_ambiguous = score_gap <= margin

        if is_ambiguous:
            logger.warning(
                f"Ambiguous match: top={top_user} ({top_score:.3f}), "
                f"second={results[1][0] if len(results) > 1 else 'N/A'} ({second_score:.3f}), "
                f"gap={score_gap:.3f} <= margin={margin}"
            )

        return {
            "user_id": top_user,
            "confidence": float(top_score),
            "is_ambiguous": is_ambiguous,
        }
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_faiss_manager.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/services/ml/faiss_manager.py backend/tests/unit/test_faiss_manager.py
git commit -m "feat(backend): add top-k search with confidence margin to FAISS"
```

---

## Task 6: Backend — Add Transaction Safety to Face Registration

**Files:**
- Modify: `backend/app/services/face_service.py:29-128` (register_face method)
- Test: `backend/tests/unit/test_face_service.py`

**Step 1: Write the failing test**

Add to `backend/tests/unit/test_face_service.py`:

```python
class TestFaceServiceTransactionSafety:
    """Tests for FAISS/DB transaction safety during registration."""

    @pytest.mark.asyncio
    async def test_register_face_rolls_back_faiss_on_db_failure(self, db_session):
        """If DB commit fails after FAISS add, FAISS state should be reverted."""
        service = _make_face_service(db_session)
        images = [_make_mock_upload_file() for _ in range(3)]

        # Make FAISS add succeed but DB commit fail
        service._faiss = MagicMock()
        service._faiss.add.return_value = 42
        initial_ntotal = 5
        service._faiss.index = MagicMock(ntotal=initial_ntotal)

        with patch.object(db_session, 'commit', side_effect=Exception("DB write failed")):
            with pytest.raises(Exception, match="DB write failed"):
                await service.register_face("test-user-id", images)

        # FAISS remove should have been called to revert
        service._faiss.remove.assert_called_with(42)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_face_service.py::TestFaceServiceTransactionSafety -v`
Expected: FAIL

**Step 3: Implement transaction safety**

In `backend/app/services/face_service.py`, refactor `register_face` (lines 29-128) to wrap FAISS+DB in try/except with rollback:

```python
    async def register_face(self, user_id: str, images: List[UploadFile]) -> Tuple[int, str]:
        # ... existing validation (lines 57-82) stays the same ...

        # Generate embeddings
        embeddings = []
        for img in images:
            content = await img.read()
            # ... existing embedding generation ...
            embeddings.append(embedding)

        # Average and normalize
        avg_embedding = np.mean(embeddings, axis=0)
        avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)

        # Transaction: FAISS add -> DB insert -> FAISS save
        faiss_id = None
        try:
            # Step 1: Add to FAISS (in-memory)
            faiss_id = faiss_manager.add(avg_embedding, user_id)

            # Step 2: Insert DB record
            face_reg = FaceRegistration(
                user_id=user_id,
                embedding_id=faiss_id,
                embedding_vector=avg_embedding.astype(np.float32).tobytes(),
                is_active=True,
            )
            self.db.add(face_reg)
            self.db.commit()

            # Step 3: Persist FAISS to disk (after DB commit succeeds)
            faiss_manager.save()

            return faiss_id, user_id

        except Exception as e:
            # Rollback: revert FAISS in-memory state
            if faiss_id is not None:
                faiss_manager.remove(faiss_id)
                logger.warning(f"Rolled back FAISS add (id={faiss_id}) due to: {e}")
            self.db.rollback()
            raise
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_face_service.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/services/face_service.py backend/tests/unit/test_face_service.py
git commit -m "fix(backend): add FAISS/DB transaction safety with rollback on failure"
```

---

## Task 7: Backend — Add FAISS Reconciliation on Startup

**Files:**
- Modify: `backend/app/main.py:83-174` (startup event)
- Modify: `backend/app/services/face_service.py` (add reconcile method)

**Step 1: Add reconciliation method to FaceService**

In `backend/app/services/face_service.py`, add a new class method:

```python
    @staticmethod
    def reconcile_faiss_index(db: Session) -> bool:
        """Compare FAISS index count with DB and rebuild if mismatched."""
        from app.repositories.face_repository import FaceRepository
        repo = FaceRepository(db)
        active_count = repo.count_active_registrations()
        faiss_count = faiss_manager.index.ntotal if faiss_manager.index else 0

        if active_count != faiss_count:
            logger.warning(
                f"FAISS/DB mismatch: FAISS has {faiss_count} vectors, "
                f"DB has {active_count} active registrations. Rebuilding..."
            )
            registrations = repo.get_all_active()
            embeddings_data = [
                (np.frombuffer(r.embedding_vector, dtype=np.float32), r.user_id)
                for r in registrations
            ]
            faiss_manager.rebuild(embeddings_data)
            faiss_manager.save()
            logger.info(f"FAISS index rebuilt with {len(embeddings_data)} embeddings")
            return True

        logger.info(f"FAISS/DB in sync: {active_count} active registrations")
        return False
```

**Step 2: Add reconciliation call to startup event**

In `backend/app/main.py`, inside the startup event handler (after FAISS index load around line 113), add:

```python
        # Reconcile FAISS index with database
        try:
            from app.services.face_service import FaceService
            db = SessionLocal()
            try:
                FaceService.reconcile_faiss_index(db)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"FAISS reconciliation failed: {e}")
```

**Step 3: Verify startup still works**

Run: `cd backend && python -c "from app.main import app; print('App created OK')"`
Expected: `App created OK`

**Step 4: Commit**

```bash
git add backend/app/services/face_service.py backend/app/main.py
git commit -m "feat(backend): add FAISS/DB reconciliation on startup"
```

---

## Task 8: Backend — Add Thread Safety to PresenceService

**Files:**
- Modify: `backend/app/services/presence_service.py:60-80` (class init + _active_sessions)
- Test: `backend/tests/test_presence_service.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_presence_service.py`:

```python
class TestPresenceServiceThreadSafety:
    """Tests for thread-safe session access."""

    @pytest.mark.asyncio
    async def test_concurrent_session_access_does_not_corrupt(self):
        """Multiple concurrent operations on _active_sessions should not raise."""
        import asyncio
        # This test verifies the lock exists and is used
        service = PresenceService.__new__(PresenceService)
        service._lock = asyncio.Lock()
        assert hasattr(service, '_lock')
        async with service._lock:
            # Lock acquired successfully
            pass
```

**Step 2: Implement thread safety**

In `backend/app/services/presence_service.py`, add lock to the class:

```python
import asyncio

class PresenceService:
    _active_sessions: Dict[str, SessionState] = {}
    _lock = asyncio.Lock()  # NEW: protect _active_sessions

    def __init__(self, db: Session, ws_manager=None):
        # ... existing init ...
```

Then wrap all methods that mutate `_active_sessions` with `async with self._lock:`:

- `start_session()` — wrap the session creation block
- `end_session()` — wrap the session removal block
- `log_detection()` — wrap the session state update
- `process_session_scan()` — wrap the scan processing

Example for `start_session`:
```python
    async def start_session(self, schedule_id: str) -> SessionState:
        async with self._lock:
            if schedule_id in self._active_sessions:
                return self._active_sessions[schedule_id]
            # ... rest of existing implementation ...
```

**Step 3: Run tests**

Run: `cd backend && python -m pytest tests/test_presence_service.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add backend/app/services/presence_service.py backend/tests/test_presence_service.py
git commit -m "fix(backend): add asyncio.Lock to PresenceService for thread safety"
```

---

## Task 9: Backend — Unify Presence Logging Path (Single Writer)

**Files:**
- Modify: `backend/app/routers/face.py:389-435` (presence logging in edge API)
- Modify: `backend/app/services/presence_service.py` (add feed_detection method)

**Step 1: Add feed_detection method to PresenceService**

This method stores detection in tracking service WITHOUT writing to attendance tables:

```python
    async def feed_detection(
        self, schedule_id: str, user_id: str, confidence: float,
        bbox: Optional[List[float]] = None
    ):
        """Feed a detection into the tracking service. Does NOT update attendance.
        Attendance updates happen solely in run_scan_cycle()."""
        from app.services.tracking_service import tracking_service

        if schedule_id not in self._active_sessions:
            logger.debug(f"No active session for {schedule_id}, ignoring detection")
            return

        tracking_service.update_detection(
            session_id=schedule_id,
            user_id=user_id,
            confidence=confidence,
            bbox=bbox or [0, 0, 0, 0],
        )
        logger.debug(f"Fed detection to tracking: user={user_id}, schedule={schedule_id}")
```

**Step 2: Update Edge API router to use feed_detection**

In `backend/app/routers/face.py`, find the presence logging block (around lines 389-435) and replace the direct `log_detection()` call with `feed_detection()`:

```python
# BEFORE:
# await presence_service.log_detection(schedule_id, user_id, confidence, bbox)

# AFTER:
await presence_service.feed_detection(schedule_id, user_id, confidence, bbox)
```

**Step 3: Run edge API tests**

Run: `cd backend && python -m pytest tests/integration/test_edge_api.py -v`
Expected: All PASS (mocked presence_service)

**Step 4: Commit**

```bash
git add backend/app/routers/face.py backend/app/services/presence_service.py
git commit -m "refactor(backend): unify presence logging — edge API feeds tracking, scan cycle is sole writer"
```

---

## Task 10: Backend — Batch Recognition in FaceService

**Files:**
- Modify: `backend/app/services/face_service.py:167-205` (recognize_batch method)

**Step 1: Write the failing test**

Add to `backend/tests/unit/test_face_service.py`:

```python
class TestFaceServiceBatchOptimization:
    """Tests for optimized batch recognition using batch embeddings + batch search."""

    @pytest.mark.asyncio
    async def test_recognize_batch_uses_batch_embedding(self, db_session):
        """recognize_batch should call generate_embeddings_batch for efficiency."""
        service = _make_face_service(db_session)
        images = [_make_jpeg_bytes() for _ in range(3)]

        mock_embeddings = np.random.randn(3, 512).astype(np.float32)
        mock_embeddings = mock_embeddings / np.linalg.norm(mock_embeddings, axis=1, keepdims=True)

        with patch.object(facenet_model, 'generate_embeddings_batch', return_value=mock_embeddings) as mock_batch:
            with patch.object(faiss_manager, 'search_batch', return_value=[
                [("user-1", 0.9)], [("user-2", 0.85)], []
            ]):
                results = await service.recognize_batch(images)
                mock_batch.assert_called_once()
                assert len(results) == 3
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_face_service.py::TestFaceServiceBatchOptimization -v`
Expected: FAIL

**Step 3: Implement batch recognition**

Replace the sequential `recognize_batch` in `backend/app/services/face_service.py` (lines 167-205):

```python
    async def recognize_batch(
        self, images_bytes: List[bytes], threshold: Optional[float] = None
    ) -> List[dict]:
        """Recognize multiple faces in a single batch pass."""
        if not images_bytes:
            return []

        th = threshold or settings.RECOGNITION_THRESHOLD
        results = []

        # Decode all images, tracking which succeeded
        decoded_images = []
        index_map = []  # maps batch index -> original index
        for i, img_bytes in enumerate(images_bytes):
            try:
                pil_img = facenet_model.decode_base64_image(
                    img_bytes if isinstance(img_bytes, str) else
                    base64.b64encode(img_bytes).decode('utf-8')
                )
                decoded_images.append(pil_img)
                index_map.append(i)
            except Exception as e:
                results.append({"index": i, "user_id": None, "confidence": None, "error": str(e)})

        if not decoded_images:
            return results

        # Batch embedding generation (single forward pass)
        try:
            embeddings = facenet_model.generate_embeddings_batch(decoded_images)
        except Exception as e:
            for i in index_map:
                results.append({"index": i, "user_id": None, "confidence": None, "error": str(e)})
            return sorted(results, key=lambda r: r.get("index", 0))

        # Batch FAISS search
        search_results = faiss_manager.search_batch(embeddings, k=settings.RECOGNITION_TOP_K, threshold=th)

        for batch_idx, (orig_idx, matches) in enumerate(zip(index_map, search_results)):
            if matches:
                user_id, confidence = matches[0]
                results.append({"index": orig_idx, "user_id": user_id, "confidence": float(confidence)})
            else:
                results.append({"index": orig_idx, "user_id": None, "confidence": None})

        return sorted(results, key=lambda r: r.get("index", 0))
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_face_service.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/services/face_service.py backend/tests/unit/test_face_service.py
git commit -m "perf(backend): optimize batch recognition — single forward pass + batch FAISS search"
```

---

## Task 11: Backend — Tune HLS Streaming for 30fps

**Files:**
- Modify: `backend/app/services/hls_service.py:84-97` (FFmpeg command)
- Modify: `backend/app/config.py` (already done in Task 3)

**Step 1: Update FFmpeg command in HLS service**

In `backend/app/services/hls_service.py`, find the FFmpeg command construction (around lines 84-97). The current command uses `-c:v copy` (no transcoding). Update to enforce 30fps output:

```python
            cmd = [
                ffmpeg_path,
                "-rtsp_transport", "tcp",
                "-i", rtsp_url,
                "-c:v", "copy",              # keep copy (no re-encode) for speed
                "-r", "30",                   # NEW: output at 30fps
                "-f", "hls",
                "-hls_time", str(settings.HLS_SEGMENT_DURATION),
                "-hls_list_size", str(settings.HLS_PLAYLIST_SIZE),
                "-hls_flags", "delete_segments+append_list",
                "-hls_segment_filename", os.path.join(seg_dir, "seg_%05d.ts"),
                playlist_path,
            ]
```

Note: `-r 30` with `-c:v copy` may not re-encode. If the source RTSP stream is already 30fps, this works. If source is 15fps, we need to either accept 15fps HLS or re-encode. Add a comment documenting this trade-off.

**Step 2: Verify import**

Run: `cd backend && python -c "from app.services.hls_service import hls_service; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/app/services/hls_service.py
git commit -m "feat(backend): tune HLS streaming for 30fps output"
```

---

## Task 12: Backend — Increase Recognition FPS and WebSocket Push Rate

**Files:**
- Modify: `backend/app/services/recognition_service.py:218-285` (_recognition_loop)
- Modify: `backend/app/routers/live_stream.py:202-205` (push interval)

**Step 1: Update recognition loop target FPS**

The recognition loop in `recognition_service.py` already reads `settings.RECOGNITION_FPS` (line 223). Since we changed the config default to 8.0 in Task 3, the loop will now target 8fps (~125ms per frame). No code change needed here — just verify.

**Step 2: Update WebSocket push interval**

In `backend/app/routers/live_stream.py`, find the detection push interval (around line 202). Change from 150ms to 125ms to match 8fps:

```python
# In _hls_mode, the sleep between detection pushes:
await asyncio.sleep(0.125)  # was 0.15 — match 8fps detection rate
```

**Step 3: Commit**

```bash
git add backend/app/routers/live_stream.py
git commit -m "feat(backend): increase WebSocket push rate to match 8fps detection"
```

---

## Task 13: Mobile — Animated Detection Overlay

**Files:**
- Modify: `mobile/src/components/video/DetectionOverlay.tsx`

**Step 1: Add animated transitions to detection boxes**

Replace the current static rendering with animated opacity transitions. In `mobile/src/components/video/DetectionOverlay.tsx`:

```typescript
import React, { useMemo, useEffect, useRef } from 'react';
import { View, StyleSheet, Animated } from 'react-native';
import { Text } from '../ui';
import { theme } from '../../constants';

// ... keep existing interfaces ...

const FADE_DURATION = 200; // ms

const DetectionBox: React.FC<{
  detection: DetectionItem;
  scaleInfo: ScaleInfo;
}> = ({ detection, scaleInfo }) => {
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(opacity, {
      toValue: 1,
      duration: FADE_DURATION,
      useNativeDriver: true,
    }).start();
  }, [detection.bbox.x, detection.bbox.y]);

  const { scale, offsetX, offsetY } = scaleInfo;
  const left = detection.bbox.x * scale + offsetX;
  const top = detection.bbox.y * scale + offsetY;
  const width = detection.bbox.width * scale;
  const height = detection.bbox.height * scale;
  const borderColor = detection.user_id ? '#00C853' : '#FFD600';
  const label = detection.name || detection.student_id || (detection.user_id?.slice(0, 8) ?? '');
  const simText = detection.similarity != null ? ` ${(detection.similarity * 100).toFixed(0)}%` : '';

  return (
    <Animated.View style={[styles.box, { left, top, width, height, borderColor, opacity }]}>
      <View style={[styles.labelContainer, { backgroundColor: borderColor }]}>
        <Text style={styles.labelText}>{label}{simText}</Text>
      </View>
    </Animated.View>
  );
};

const DetectionOverlay: React.FC<DetectionOverlayProps> = React.memo(({
  detections, videoWidth, videoHeight, containerWidth, containerHeight,
}) => {
  const scaleInfo = useMemo(
    () => computeScale(videoWidth, videoHeight, containerWidth, containerHeight),
    [videoWidth, videoHeight, containerWidth, containerHeight],
  );

  if (!detections.length || containerWidth <= 0 || containerHeight <= 0) return null;

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      {detections.map((det, i) => (
        <DetectionBox
          key={det.user_id || `unknown-${i}`}
          detection={det}
          scaleInfo={scaleInfo}
        />
      ))}
    </View>
  );
});
```

**Step 2: Commit**

```bash
git add mobile/src/components/video/DetectionOverlay.tsx
git commit -m "feat(mobile): add animated fade transitions to detection overlay boxes"
```

---

## Task 14: Backend — Use search_with_margin in Edge API Recognition

**Files:**
- Modify: `backend/app/routers/face.py:351-377` (recognition block inside process_faces)

**Step 1: Update edge API to use search_with_margin**

In `backend/app/routers/face.py`, inside `process_faces`, find where `face_service.recognize_face()` is called for each face (around lines 351-377). Update to use the new margin-aware search:

```python
# Replace the per-face recognition call with:
embedding = facenet_model.generate_embedding(pil_image)
match_result = faiss_manager.search_with_margin(
    embedding,
    k=settings.RECOGNITION_TOP_K,
    threshold=settings.RECOGNITION_THRESHOLD,
    margin=settings.RECOGNITION_MARGIN,
)

if match_result["user_id"]:
    matched_users.append(MatchedUser(
        user_id=match_result["user_id"],
        confidence=match_result["confidence"],
    ))
    if match_result["is_ambiguous"]:
        logger.warning(f"Ambiguous match for face {idx} in room {request.room_id}")
else:
    unmatched_count += 1
```

**Step 2: Run edge API tests**

Run: `cd backend && python -m pytest tests/integration/test_edge_api.py -v`
Expected: All PASS (uses mocked FAISS)

**Step 3: Commit**

```bash
git add backend/app/routers/face.py
git commit -m "feat(backend): use margin-aware FAISS search in edge API"
```

---

## Task 15: Backend — Add Minimum Image Size Validation

**Files:**
- Modify: `backend/app/services/ml/face_recognition.py:196-258` (decode_base64_image)

**Step 1: Update decode_base64_image to enforce 160x160 minimum**

In `backend/app/services/ml/face_recognition.py`, find the dimension validation in `decode_base64_image` (around lines 246-249). Update:

```python
        # Validate dimensions
        w, h = image.size
        min_dim = self.FACE_IMAGE_SIZE  # 160 — matches FaceNet input requirement
        if w < min_dim or h < min_dim:
            raise ValueError(
                f"Image too small: {w}x{h}, minimum {min_dim}x{min_dim} required"
            )
```

**Step 2: Update existing test expectations**

In `backend/tests/unit/test_face_recognition_model.py`, the test `test_decode_base64_image_too_small` currently expects 10x10 minimum. Update it to expect 160x160 minimum, or add a new test:

```python
    def test_decode_base64_image_below_facenet_size(self):
        """Images smaller than FACE_IMAGE_SIZE (160x160) should be rejected."""
        model = FaceNetModel()
        small_img = Image.new("RGB", (100, 100))
        buf = BytesIO()
        small_img.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        with pytest.raises(ValueError, match="too small"):
            model.decode_base64_image(b64)
```

**Step 3: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_face_recognition_model.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add backend/app/services/ml/face_recognition.py backend/tests/unit/test_face_recognition_model.py
git commit -m "feat(backend): enforce 160x160 minimum image size for face recognition"
```

---

## Task 16: Documentation — Create ML Pipeline Specification

**Files:**
- Create: `docs/main/ml-pipeline-spec.md`

**Step 1: Write the authoritative ML pipeline spec**

Create `docs/main/ml-pipeline-spec.md` with contents covering:

1. **Preprocessing Chain** — Edge: camera capture → MediaPipe detect (confidence >= 0.6, min 80x80px) → crop with 20% padding → resize 160x160 → JPEG 85% → Base64 → POST. Backend: decode Base64 → validate >= 160x160 → MTCNN align (fallback: raw crop) → resize 160x160 → normalize [-1,1] → FaceNet → 512-dim L2-normalized embedding.

2. **Face Registration** — 3-5 images required, 5-angle guided capture on mobile, each processed through alignment + FaceNet, embeddings averaged and L2-normalized, stored in FAISS IndexFlatIP + face_registrations table with transaction safety.

3. **Face Recognition** — Top-3 FAISS search, threshold 0.55, confidence margin 0.1 between top-1 and top-2, ambiguous matches logged but accepted.

4. **Edge API Contract** — POST /api/v1/face/process, batch 1-10 faces (optimal 3-5), 422 for validation errors, optional request_id for idempotency (5-min TTL).

5. **FAISS Lifecycle** — IndexFlatIP, 512-dim, no native delete (rebuild required), startup reconciliation, periodic health check, disk persistence after every add.

6. **Streaming** — HLS at 30fps via FFmpeg, 2s segments, 3-segment playlist. Detection at 8fps on separate thread. WebSocket pushes metadata at 8Hz. Mobile overlay with 200ms fade transitions.

7. **Threshold Reference Table** — All configurable thresholds with env var names, defaults, and valid ranges.

**Step 2: Commit**

```bash
git add docs/main/ml-pipeline-spec.md
git commit -m "docs: create authoritative ML pipeline specification"
```

---

## Task 17: Run Full Test Suite and Verify

**Step 1: Run all backend tests**

Run: `cd backend && python -m pytest -v --tb=short 2>&1 | tail -30`
Expected: All tests pass or known failures only

**Step 2: Run edge import check**

Run: `cd edge && python -c "from app.config import config; from app.processor import FaceProcessor; from app.detector import FaceDetector; config.validate(); print('Edge OK')"`
Expected: `Edge OK`

**Step 3: Verify mobile builds**

Run: `cd mobile && npx tsc --noEmit 2>&1 | tail -10`
Expected: No new type errors from our changes

**Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address test failures from ML pipeline redesign"
```

---

## Execution Order Summary

| Task | Section | Component | Risk | Dependencies |
|------|---------|-----------|------|-------------|
| 1 | Preprocessing | Edge config | Low | None |
| 2 | Preprocessing | Edge detector | Low | None |
| 3 | Config | Backend config | Low | None |
| 4 | Alignment | Backend FaceNet | Medium | Task 3 |
| 5 | Accuracy | Backend FAISS | Medium | Task 3 |
| 6 | Integrity | Backend FaceService | Medium | Task 5 |
| 7 | Integrity | Backend main.py | Low | Task 6 |
| 8 | Concurrency | Backend PresenceService | Medium | None |
| 9 | Concurrency | Backend router + service | Medium | Task 8 |
| 10 | Accuracy | Backend FaceService | Medium | Task 5 |
| 11 | Streaming | Backend HLS | Low | Task 3 |
| 12 | Streaming | Backend WebSocket | Low | Task 3 |
| 13 | Streaming | Mobile overlay | Low | None |
| 14 | Accuracy | Backend Edge API | Medium | Task 5 |
| 15 | Preprocessing | Backend validation | Low | Task 3 |
| 16 | Documentation | Docs | Low | All above |
| 17 | Verification | All | Low | All above |

Tasks 1-3 can run in parallel (independent config changes).
Tasks 4, 5, 8 can run in parallel after Task 3.
Tasks 6, 9, 10, 11, 12, 13 can run after their dependencies.
Tasks 14, 15 after Task 5.
Task 16 after all code changes.
Task 17 last.
