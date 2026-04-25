"""
Face Service

Business logic for face registration and recognition.
Orchestrates InsightFace (ArcFace) model, FAISS search, and database operations.
"""

import contextlib
import io
import random
import time

import cv2
import numpy as np
from fastapi import UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from app.config import logger, settings
from app.repositories.face_repository import FaceRepository
from app.services.ml.anti_spoof import anti_spoof_detector
from app.services.ml.embedding_pipeline import (
    embed_face,
    validate_registration_embeddings,
)
from app.services.ml.face_quality import QualityReport, assess_quality
from app.services.ml.faiss_manager import faiss_manager
from app.services.ml.insightface_model import insightface_model
from app.utils.exceptions import FaceRecognitionError, ValidationError
from app.utils.face_image_storage import FaceImageStorage


class FaceService:
    """Service for face registration and recognition operations"""

    def __init__(self, db: Session):
        self.db = db
        self.face_repo = FaceRepository(db)
        self.facenet = insightface_model
        self.faiss = faiss_manager

    def _generate_cctv_simulated_embeddings(self, face_crops: list[np.ndarray]) -> list[np.ndarray]:
        """
        Apply CCTV-like degradation to each face crop and re-embed with ArcFace.

        Uses get_embedding_from_crop() which resizes the degraded crop to 112x112
        and runs ArcFace directly — bypassing SCRFD face detection. This is critical
        because SCRFD cannot re-detect a face in a heavily degraded tiny crop.

        Generates domain-matched embeddings so CCTV camera recognition can match
        against phone-registered faces. Each crop produces one simulated embedding.

        Args:
            face_crops: BGR face crops extracted during registration

        Returns:
            List of L2-normalized 512-dim embeddings in the CCTV image domain.
        """
        simulated: list[np.ndarray] = []
        for crop in face_crops:
            try:
                h, w = crop.shape[:2]
                if h < 20 or w < 20:
                    continue

                # Downscale to simulate CCTV sub-stream resolution, then upscale back.
                # This introduces the resolution loss typical of surveillance cameras.
                scale = 0.40 + random.random() * 0.30  # 40–70%
                small = cv2.resize(
                    crop,
                    (max(1, int(w * scale)), max(1, int(h * scale))),
                    interpolation=cv2.INTER_AREA,
                )
                face_sim = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)

                # JPEG compression artifacts (simulates H.264 block noise)
                quality = random.randint(35, 65)
                _, enc = cv2.imencode(".jpg", face_sim, [cv2.IMWRITE_JPEG_QUALITY, quality])
                face_sim = cv2.imdecode(enc, cv2.IMREAD_COLOR)

                # Slight Gaussian blur (camera focus + motion)
                k = random.choice([3, 5])
                face_sim = cv2.GaussianBlur(face_sim, (k, k), 0)

                # Brightness/contrast shift (indoor CCTV lighting variation)
                alpha = 0.80 + random.random() * 0.40  # 0.80–1.20 contrast
                beta = random.randint(-20, 20)  # brightness offset
                face_sim = np.clip(alpha * face_sim.astype(np.float32) + beta, 0, 255).astype(np.uint8)

                # Embed directly via ArcFace (skip SCRFD — crop IS the face)
                emb = self.facenet.get_embedding_from_crop(face_sim)
                simulated.append(emb.astype(np.float32))

            except Exception as e:
                logger.debug(f"CCTV simulation skipped for one crop: {e}")
        return simulated

    async def register_face(
        self, user_id: str, images: list[UploadFile]
    ) -> tuple[int, str, list[QualityReport] | None]:
        """
        Register user's face with multiple images

        Process:
        1. Validate images (3-5 images required)
        2. Generate embeddings for each image
        3. Quality-gate each image (blur, brightness, face size, confidence)
        4. Average embeddings → single 512-dim vector
        5. Normalize vector
        6. Add to FAISS index
        7. Save to database

        Args:
            user_id: User UUID
            images: List of 3-5 face images

        Returns:
            Tuple of (embedding_id, message, quality_reports)

        Raises:
            ValidationError: If validation fails (including quality rejection)
            FaceRecognitionError: If face processing fails
        """
        # Validate number of images
        if len(images) < settings.MIN_FACE_IMAGES:
            raise ValidationError(f"Minimum {settings.MIN_FACE_IMAGES} images required for registration")

        if len(images) > settings.MAX_FACE_IMAGES:
            raise ValidationError(f"Maximum {settings.MAX_FACE_IMAGES} images allowed")

        # Check if user already has registered face
        existing = self.face_repo.get_by_user(user_id)
        if existing:
            raise ValidationError("User already has registered face. Use re-register to update.")

        logger.info(f"Registering face for user {user_id} with {len(images)} images")

        # Generate embeddings for each image
        embeddings = []
        face_crops = []  # Collected for anti-spoof check
        raw_image_bytes: list[bytes] = []  # Kept for post-commit disk persistence
        quality_reports: list[QualityReport] = []
        for i, image_file in enumerate(images):
            _img_start = time.monotonic()
            try:
                # Read image bytes
                image_bytes = await image_file.read()

                # Validate file size
                if len(image_bytes) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
                    raise ValidationError(f"Image {i + 1} exceeds size limit")

                # Stash the raw bytes for post-commit disk persistence so the
                # admin face-comparison sheet can show the original angle later.
                # Storage happens AFTER db.commit() so a rollback doesn't leave
                # orphan JPEGs on disk.
                raw_image_bytes.append(image_bytes)

                # Generate embedding (with quality metadata if available)
                if settings.QUALITY_GATE_ENABLED and hasattr(self.facenet, "get_face_with_quality"):
                    face_data = self.facenet.get_face_with_quality(image_bytes)
                    embedding = face_data["embedding"]
                    # Extract the actual face crop using the bbox for anti-spoof.
                    # Passing the full image causes FFT/LBP to analyze background
                    # pixels, producing false spoof detections on every image.
                    bx, by, bw, bh = face_data["bbox"]
                    face_crop = face_data["image_bgr"][by : by + bh, bx : bx + bw]
                    face_crops.append(face_crop)
                    quality = assess_quality(
                        image_bgr=face_data["image_bgr"],
                        det_score=face_data["det_score"],
                        bbox=face_data["bbox"],
                        image_shape=face_data["image_bgr"].shape,
                        blur_threshold_override=settings.QUALITY_BLUR_THRESHOLD_MOBILE,
                    )
                    quality_reports.append(quality)
                    if not quality.passed:
                        raise ValidationError(f"Image {i + 1} rejected: {', '.join(quality.rejection_reasons)}")
                else:
                    embedding = self.facenet.get_embedding(image_bytes)

                embeddings.append(embedding)

                logger.info(f"Image {i + 1}/{len(images)}: embedding generated in {time.monotonic() - _img_start:.2f}s")

            except ValidationError:
                raise
            except ValueError as e:
                raise FaceRecognitionError(f"Image {i + 1}: {str(e)}") from e
            except Exception as e:
                logger.error(f"Failed to process image {i + 1}: {e}")
                raise FaceRecognitionError(f"Failed to process image {i + 1}") from e

        if not embeddings:
            raise FaceRecognitionError("No valid face embeddings generated")

        # L2 normalize each embedding individually
        normed = []
        for i, emb in enumerate(embeddings):
            norm = np.linalg.norm(emb)
            if norm < 1e-6:
                raise FaceRecognitionError(f"Image {i + 1} produced a degenerate embedding (zero norm)")
            n = emb / norm
            normed.append(n)

        # Cross-capture validation: warn if embeddings seem inconsistent,
        # but don't block registration.  Different angles + mobile compression
        # naturally produce lower pairwise similarity.
        is_valid, validation_msg = validate_registration_embeddings(normed)
        if not is_valid:
            logger.warning(f"Cross-capture validation warning for user {user_id}: {validation_msg}")

        # Anti-spoof check (registration-time, uses embedding variance + texture)
        if settings.ANTISPOOF_ENABLED and settings.ANTISPOOF_REGISTRATION_STRICT:
            spoof_result = anti_spoof_detector.check_registration_set(
                face_crops=face_crops if face_crops else [],
                embeddings=normed,
            )
            if not spoof_result.is_live:
                reasons = spoof_result.details.get("rejection_reasons", ["spoof detected"])
                logger.warning(f"Anti-spoof rejected registration for user {user_id}: {reasons}")
                raise ValidationError(f"Registration rejected: possible presentation attack. {'; '.join(reasons)}")
            logger.debug(f"Anti-spoof passed for user {user_id} (score={spoof_result.spoof_score:.3f})")

        # Generate CCTV-simulated embeddings for cross-domain tolerance
        sim_normed = self._generate_cctv_simulated_embeddings(face_crops)
        if sim_normed:
            logger.info(f"Generated {len(sim_normed)} CCTV-simulated embeddings for user {user_id}")
        else:
            logger.warning(f"No CCTV-simulated embeddings generated for user {user_id} — face crops may be empty")

        # Add phone + simulated embeddings to FAISS (all mapped to same user)
        all_normed = normed + sim_normed
        all_embs = np.stack(all_normed).astype(np.float32)
        try:
            faiss_ids = self.faiss.add_batch(all_embs, [user_id] * len(all_normed))
        except Exception as e:
            logger.error(f"Failed to add to FAISS: {e}")
            raise FaceRecognitionError("Failed to index face embeddings") from e

        # Compute a representative averaged embedding from phone captures only
        # (backward-compatible storage in face_registrations.embedding_vector)
        phone_embs = np.stack(normed).astype(np.float32)
        avg_embedding = np.mean(phone_embs, axis=0)
        avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)
        avg_bytes = avg_embedding.astype(np.float32).tobytes()

        # Angle labels: phone captures + simulated
        angle_labels = ["center", "left", "right", "up", "down"]
        sim_labels = [f"sim_{i}" for i in range(len(sim_normed))]
        all_labels = angle_labels[: len(normed)] + sim_labels

        # Transaction: DB insert with FAISS rollback on failure
        try:
            # Create parent FaceRegistration (embedding_id = first FAISS ID)
            # Use _create_no_commit to delay commit until embeddings are also added
            registration = self.face_repo._create_no_commit(user_id, faiss_ids[0], avg_bytes)

            # Create individual FaceEmbedding rows (phone captures + simulated)
            embedding_entries = []
            for idx, (fid, emb) in enumerate(zip(faiss_ids, all_normed)):
                q_score = None
                if quality_reports and idx < len(quality_reports):
                    q_score = quality_reports[idx].blur_score  # Use blur as overall quality proxy
                embedding_entries.append(
                    {
                        "faiss_id": fid,
                        "embedding_vector": emb.astype(np.float32).tobytes(),
                        "angle_label": all_labels[idx] if idx < len(all_labels) else None,
                        "quality_score": q_score,
                    }
                )
            self.face_repo.create_embeddings_batch(str(registration.id), embedding_entries)
            self.db.commit()

            # Persist FAISS index to disk only after DB commit succeeds
            self.faiss.save()

            # Persist the raw registration JPEGs to the face-uploads volume so
            # the admin live-feed face-comparison sheet can render them. Only
            # the real phone-captured angles are stored — the `sim_*`
            # CCTV-simulated embeddings are algorithmic derivatives with no
            # separate image to save.
            #
            # Failure here is best-effort: a disk-write error leaves
            # image_storage_key=NULL on the affected row(s), the registration
            # still succeeds, and the admin UI falls back to metadata-only
            # tiles (same path as pre-Phase-2 rows).
            try:
                storage = FaceImageStorage()
                keys_by_faiss: dict[int, str] = {}
                for idx, img_bytes in enumerate(raw_image_bytes):
                    if idx >= len(normed):
                        break
                    angle = angle_labels[idx] if idx < len(angle_labels) else None
                    if angle is None:
                        continue
                    key = storage.save_registration_image(user_id, angle, img_bytes)
                    if key:
                        keys_by_faiss[int(faiss_ids[idx])] = key
                if keys_by_faiss:
                    updated = self.face_repo.set_image_storage_keys(
                        str(registration.id), keys_by_faiss
                    )
                    self.db.commit()
                    logger.info(
                        f"Persisted {updated} registration image(s) for user {user_id}"
                    )
            except Exception:
                logger.warning(
                    f"Failed to persist registration images for user {user_id}",
                    exc_info=True,
                )
                # Don't re-raise: registration is already committed.

            logger.info(
                f"Face registered for user {user_id}: "
                f"{len(faiss_ids)} embeddings (FAISS IDs {faiss_ids[0]}-{faiss_ids[-1]})"
            )
        except Exception as e:
            # Rollback DB transaction
            self.db.rollback()

            # Rollback FAISS additions since DB commit failed.
            # Note: faiss.remove() only removes from user_map, NOT from the
            # underlying IndexFlatIP — orphaned vectors remain in the index.
            for fid in faiss_ids:
                with contextlib.suppress(Exception):
                    self.faiss.remove(fid)

            # Rebuild the FAISS index from DB to purge orphaned vectors and
            # ensure full consistency between DB and index.
            try:
                await self.rebuild_faiss_index()
            except Exception:
                logger.error("Failed to rebuild FAISS after rollback", exc_info=True)

            logger.error(f"Failed to save face registration for user {user_id}: {e}")
            raise FaceRecognitionError("Failed to save face registration") from e

        return faiss_ids[0], "Face registered successfully", quality_reports or None

    async def recognize_face(
        self, image_bytes: bytes, threshold: float | None = None
    ) -> tuple[str | None, float | None]:
        """
        Recognize face from image

        Args:
            image_bytes: Image data (JPEG/PNG)
            threshold: Optional similarity threshold (default from settings)

        Returns:
            Tuple of (user_id, confidence) or (None, None) if no match

        Raises:
            FaceRecognitionError: If face processing fails
        """
        try:
            # Generate embedding via shared pipeline
            embedding = await embed_face(image_bytes)
            if embedding is None:
                logger.debug("No face detected in recognition image")
                return None, None

            # Search FAISS
            results = self.faiss.search(embedding, k=1, threshold=threshold)

            if results:
                user_id, confidence = results[0]
                logger.debug(f"Face recognized: user {user_id}, confidence {confidence:.3f}")
                return user_id, confidence
            else:
                logger.debug("No face match found")
                return None, None

        except Exception as e:
            logger.error(f"Face recognition failed: {e}")
            raise FaceRecognitionError(f"Face recognition failed: {str(e)}") from e

    async def recognize_batch(self, images_bytes: list[bytes], threshold: float | None = None) -> list[dict]:
        """Recognize multiple faces using batch embedding + batch FAISS search."""
        if not images_bytes:
            return []

        th = threshold or settings.RECOGNITION_THRESHOLD
        results = []

        # Phase 1: Decode all images
        decoded_images = []
        index_map = []  # maps batch position -> original index
        for i, img_bytes in enumerate(images_bytes):
            try:
                if isinstance(img_bytes, str):
                    pil_img = insightface_model.decode_base64_image(img_bytes)
                else:
                    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                decoded_images.append(pil_img)
                index_map.append(i)
            except Exception as e:
                results.append({"index": i, "user_id": None, "confidence": None, "error": str(e)})

        if not decoded_images:
            return results

        # Phase 2: Batch embedding (single forward pass)
        try:
            embeddings = insightface_model.get_embeddings_batch(decoded_images)
        except Exception as e:
            for idx in index_map:
                results.append({"index": idx, "user_id": None, "confidence": None, "error": str(e)})
            return sorted(results, key=lambda r: r.get("index", 0))

        # Phase 3: Batch FAISS search
        search_results = faiss_manager.search_batch(embeddings, k=settings.RECOGNITION_TOP_K, threshold=th)

        for _batch_idx, (orig_idx, matches) in enumerate(zip(index_map, search_results)):
            if matches:
                user_id, confidence = matches[0]
                results.append({"index": orig_idx, "user_id": user_id, "confidence": float(confidence)})
            else:
                results.append({"index": orig_idx, "user_id": None, "confidence": None})

        return sorted(results, key=lambda r: r.get("index", 0))

    async def deregister_face(self, user_id: str):
        """
        Deregister user's face (right-to-delete)

        Marks face registration as inactive, cleans up all biometric
        evidence on disk, wipes recognition_events for this user, and
        rebuilds the FAISS index.

        "Right to be forgotten" — intentionally destructive on the
        biometric layer. Attendance_records are preserved (they only
        reference user_id, not face data) so the attendance audit trail
        stays intact. See docs/plans/2026-04-22-recognition-evidence/
        DESIGN.md §5.6.

        Args:
            user_id: User UUID

        Raises:
            NotFoundError: If no face registration found
        """
        # Deactivate in database
        self.face_repo.deactivate(user_id)

        # Best-effort disk cleanup so redeploys + re-registrations don't
        # accumulate orphan JPEGs. Deactivate vs. hard-delete intentionally
        # keeps the DB row (audit trail), but the images are no longer
        # reachable from the admin UI.
        try:
            FaceImageStorage().delete_user_images(user_id)
        except Exception:
            logger.warning(
                f"Failed to clean registration images for user {user_id}",
                exc_info=True,
            )

        # Recognition-evidence cascade. Delete every captured crop pair for
        # this user + delete the rows. This is the "right to delete" effect
        # on the CCTV evidence trail. Isolated in a try so a filesystem
        # hiccup doesn't abort the whole deregister flow.
        try:
            self._purge_recognition_evidence_for_user(user_id)
        except Exception:
            logger.warning(
                f"Failed to purge recognition evidence for user {user_id}",
                exc_info=True,
            )

        logger.info(f"Face deregistered for user {user_id}")

        # Rebuild FAISS index
        await self.rebuild_faiss_index()

    def _purge_recognition_evidence_for_user(self, user_id: str) -> None:
        """Delete crop blobs + recognition_events rows for a given user.

        Uses the evidence storage abstraction so it works identically for
        filesystem (Phases 1-4) and MinIO (Phase 5) backends.

        Silent no-op if the feature flag is off or the table is empty.
        Missing blobs are ignored (retention may have pruned them already).
        """
        if not settings.ENABLE_RECOGNITION_EVIDENCE:
            return
        import uuid

        from sqlalchemy import text

        from app.services.evidence_storage import evidence_storage

        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            logger.debug(
                "purge_recognition_evidence called with non-UUID user_id=%s",
                user_id,
            )
            return

        # Collect refs first so we know what to delete from storage — the
        # DB DELETE below wipes them and we lose the ability to walk them.
        rows = (
            self.db.execute(
                text(
                    "SELECT live_crop_ref, registered_crop_ref "
                    "FROM recognition_events WHERE student_id = :uid"
                ),
                {"uid": str(uid)},
            )
            .fetchall()
        )
        blobs_deleted = 0
        for live_ref, reg_ref in rows:
            for ref in (live_ref, reg_ref):
                if not ref:
                    continue
                try:
                    evidence_storage.delete(ref)
                    blobs_deleted += 1
                except Exception:
                    logger.debug(
                        "Could not delete crop %s via storage backend",
                        ref,
                        exc_info=True,
                    )

        # Row delete. FK on recognition_events.student_id is ON DELETE SET
        # NULL so we do an explicit DELETE here — the point is to actually
        # remove the row, not null it out. recognition_access_audit rows
        # CASCADE-delete with the event rows (event_id FK has ON DELETE
        # CASCADE).
        result = self.db.execute(
            text("DELETE FROM recognition_events WHERE student_id = :uid"),
            {"uid": str(uid)},
        )
        self.db.commit()
        logger.info(
            "Purged recognition evidence for user %s: rows=%d blobs=%d backend=%s",
            user_id,
            int(result.rowcount or 0),
            blobs_deleted,
            settings.RECOGNITION_EVIDENCE_BACKEND,
        )

    # ------------------------------------------------------------------
    # CCTV-side enrollment
    # ------------------------------------------------------------------
    #
    # Phone-only registration produces embeddings in a domain (close-up
    # selfie camera, even lighting, sharp focus) that is structurally
    # different from what the CCTV pipeline sees at recognition time
    # (40-60 px wide face, motion blur, mixed lighting, H.264 artefacts).
    # The fixed-quality CCTV simulation in
    # ``_generate_cctv_simulated_embeddings`` helps but is not a substitute
    # for embeddings drawn from the *actual* camera. After the 2026-04-25
    # identity-swap incident (see lessons.md), every freshly-registered
    # student should also be enrolled with 3-5 real CCTV captures via the
    # operator workflow:
    #
    #   docker exec iams-api-gateway-onprem python -m scripts.cctv_enroll \
    #       --user-id <uuid> --room <code> --captures 5
    #
    # or via the REST endpoint POST /api/v1/face/cctv-enroll/{user_id}.

    async def cctv_enroll(
        self,
        user_id: str,
        room_code_or_id: str,
        *,
        num_captures: int = 5,
        capture_interval: float = 1.0,
        min_face_size_px: int = 60,
        min_det_score: float = 0.65,
        max_attempts: int | None = None,
        provided_grabber=None,  # backend.services.frame_grabber.FrameGrabber | None
    ) -> dict:
        """Capture N high-quality CCTV face crops + add as canonical embeddings.

        These embeddings AUGMENT the user's existing phone-captured ones —
        they are written to ``face_embeddings`` with ``angle_label="cctv_<idx>"``
        and the crop bytes go to ``FaceImageStorage`` so the admin sheet can
        verify them visually.

        Preconditions:
          * The user must already have an active FaceRegistration. CCTV-only
            registration is intentionally not supported here — there is no
            user-facing capture flow for it, only operator-driven re-enrolment
            on top of an existing registration.
          * Exactly one face must be visible in each accepted frame. If the
            scene is empty or has multiple faces, that frame is skipped and
            the loop tries the next one until ``max_attempts`` is reached
            (default: ``num_captures * 6``).

        Args:
            user_id: Target student UUID.
            room_code_or_id: Room.code (e.g. "EB226") OR Room.id (UUID). The
                service resolves both so callers don't have to do a lookup.
            num_captures: Number of CCTV embeddings to add (default 5).
            capture_interval: Seconds between successful captures. Set to
                a small value (1.0 s default) so the operator can shift the
                student's pose between captures and produce diverse vectors.
            min_face_size_px: Minimum face short-edge in pixels.
            min_det_score: Minimum SCRFD detection confidence.
            max_attempts: Hard cap on grab attempts. None → ``num_captures * 6``.
            provided_grabber: Optional pre-warmed FrameGrabber. Pass the
                always-on grabber from ``app.state.frame_grabbers[room_id]``
                from the request handler to avoid spinning up a duplicate
                ffmpeg subprocess. CLI callers leave this None.

        Returns:
            Dict with keys:
              * ``added``: count of new embeddings persisted
              * ``faiss_ids``: list of new FAISS IDs
              * ``per_capture``: list of per-capture metadata
              * ``self_similarity_to_phone_mean``: best-effort cosine sim of
                the new CCTV embeddings to the user's averaged phone vector.
                Useful sanity check — if it's < 0.30, the operator likely
                enrolled the wrong person or the camera framing was bad.

        Raises:
            ValidationError: User has no existing registration, room not
                found, or no usable captures collected.
        """
        # Lazy import — keeps face_service.py importable in test contexts
        # where the FrameGrabber's ffmpeg dependency isn't available.
        import uuid as _uuid

        from app.models.room import Room
        from app.services.frame_grabber import FrameGrabber

        # 1. Validate preconditions
        if num_captures < 1:
            raise ValidationError("num_captures must be >= 1")
        if num_captures > 10:
            # Keep the per-user vector cluster bounded — too many CCTV
            # embeddings widens the matching cone and re-introduces
            # cross-identity confusion.
            raise ValidationError("num_captures must be <= 10")

        registration = self.face_repo.get_by_user(user_id)
        if registration is None:
            raise ValidationError(
                f"User {user_id} has no active face registration. "
                "Run phone registration first; CCTV enrolment only augments."
            )

        # Resolve room by code OR id
        room: Room | None = None
        try:
            room = self.db.query(Room).filter(Room.id == _uuid.UUID(room_code_or_id)).first()
        except (ValueError, AttributeError):
            pass
        if room is None:
            room = self.db.query(Room).filter(Room.code == room_code_or_id).first()
        if room is None:
            raise ValidationError(f"Room not found: {room_code_or_id}")
        if not room.camera_endpoint:
            raise ValidationError(f"Room {room.code} has no camera_endpoint configured")

        # 2. Resolve grabber — reuse provided one or spin a fresh one
        grabber = provided_grabber
        owns_grabber = False
        if grabber is None:
            logger.info(
                "cctv_enroll: spinning up dedicated FrameGrabber for room %s (%s)",
                room.code,
                room.camera_endpoint,
            )
            grabber = FrameGrabber(
                rtsp_url=room.camera_endpoint,
                fps=settings.FRAME_GRABBER_FPS,
                width=settings.FRAME_GRABBER_WIDTH,
                height=settings.FRAME_GRABBER_HEIGHT,
            )
            owns_grabber = True
            time.sleep(2.0)  # let ffmpeg deliver the first frames

        # 3. Capture loop
        cap_attempt_cap = max_attempts or (num_captures * 6)
        captures: list[dict] = []  # {emb, crop_bytes, det_score, bbox}
        attempts = 0
        skipped_reasons: dict[str, int] = {}

        try:
            while len(captures) < num_captures and attempts < cap_attempt_cap:
                attempts += 1
                frame = grabber.grab()
                if frame is None:
                    skipped_reasons["no_frame"] = skipped_reasons.get("no_frame", 0) + 1
                    time.sleep(0.5)
                    continue

                dets = self.facenet.detect(frame)
                # Filter to "usable" detections
                usable = []
                for det in dets:
                    if det.get("kps") is None:
                        continue
                    bx1, by1, bx2, by2 = det["bbox"]
                    bw = float(bx2 - bx1)
                    bh = float(by2 - by1)
                    if min(bw, bh) < min_face_size_px:
                        continue
                    if float(det["det_score"]) < min_det_score:
                        continue
                    usable.append(det)

                if len(usable) == 0:
                    skipped_reasons["no_face"] = skipped_reasons.get("no_face", 0) + 1
                    time.sleep(capture_interval / 2)
                    continue
                if len(usable) > 1:
                    # Operator must run enrolment with only ONE student in
                    # frame — otherwise we don't know which face goes to
                    # this user_id.
                    skipped_reasons["multi_face"] = skipped_reasons.get("multi_face", 0) + 1
                    time.sleep(capture_interval / 2)
                    continue

                det = usable[0]
                # 4. Embed via SCRFD-aligned crop (matches recognition path)
                try:
                    embedding = self.facenet.embed_from_kps(frame, det["kps"])
                except Exception as exc:
                    logger.warning("cctv_enroll: embed_from_kps failed: %s", exc)
                    skipped_reasons["embed_fail"] = skipped_reasons.get("embed_fail", 0) + 1
                    time.sleep(capture_interval / 2)
                    continue

                # 5. Crop the face for storage (with margin for context)
                bx1, by1, bx2, by2 = (int(v) for v in det["bbox"])
                fh, fw = frame.shape[:2]
                margin = int(min(bx2 - bx1, by2 - by1) * 0.25)
                cx1 = max(0, bx1 - margin)
                cy1 = max(0, by1 - margin)
                cx2 = min(fw, bx2 + margin)
                cy2 = min(fh, by2 + margin)
                crop_bgr = frame[cy1:cy2, cx1:cx2]

                ok, jpg = cv2.imencode(".jpg", crop_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
                crop_bytes = jpg.tobytes() if ok else b""

                captures.append({
                    "embedding": embedding.astype(np.float32),
                    "crop_bytes": crop_bytes,
                    "det_score": float(det["det_score"]),
                    "bbox": [int(bx1), int(by1), int(bx2 - bx1), int(by2 - by1)],
                })
                logger.info(
                    "cctv_enroll: capture %d/%d (det=%.2f, size=%dx%d)",
                    len(captures), num_captures,
                    float(det["det_score"]), int(bx2 - bx1), int(by2 - by1),
                )
                time.sleep(capture_interval)
        finally:
            if owns_grabber:
                with contextlib.suppress(Exception):
                    grabber.stop()

        if not captures:
            raise ValidationError(
                f"No usable CCTV captures collected after {attempts} attempts. "
                f"Skipped: {skipped_reasons}. "
                "Make sure exactly one student is in frame and the camera framing is reasonable."
            )

        # 6. Sanity check: how do these new embeddings score against the
        #    user's existing phone embeddings? If sims are uniformly low,
        #    the operator probably enrolled the wrong person.
        existing_phone_emb = np.frombuffer(
            registration.embedding_vector, dtype=np.float32
        )
        new_embs = np.stack([c["embedding"] for c in captures])
        sims_to_phone = (new_embs @ existing_phone_emb).tolist()
        mean_sim = float(np.mean(sims_to_phone))
        if mean_sim < 0.20:
            # Refuse to commit obviously-wrong enrolments. 0.20 is
            # well below RECOGNITION_THRESHOLD even at 0.45 — anything
            # in this range means there is no plausible identity match.
            raise ValidationError(
                f"CCTV captures do not resemble user {user_id}'s registered face "
                f"(mean cosine sim to phone embedding = {mean_sim:.3f}). "
                "Stopping to avoid poisoning the index. Verify the right student is in frame."
            )

        # 7. Pick next cctv_<idx> labels
        existing_embs = self.face_repo.get_embeddings_by_registration(str(registration.id))
        existing_cctv_indices = []
        for emb in existing_embs:
            if emb.angle_label and emb.angle_label.startswith("cctv_"):
                try:
                    existing_cctv_indices.append(int(emb.angle_label.split("_", 1)[1]))
                except ValueError:
                    pass
        next_idx = max(existing_cctv_indices, default=-1) + 1
        labels = [f"cctv_{next_idx + i}" for i in range(len(captures))]

        # 8. Add to FAISS in batch
        try:
            faiss_ids = self.faiss.add_batch(
                new_embs, [user_id] * len(new_embs)
            )
        except Exception as exc:
            logger.error("cctv_enroll: FAISS add_batch failed: %s", exc)
            raise FaceRecognitionError("Failed to index CCTV embeddings") from exc

        # 9. Persist to DB + storage in one transaction
        try:
            entries = []
            for fid, cap, label in zip(faiss_ids, captures, labels):
                entries.append({
                    "faiss_id": fid,
                    "embedding_vector": cap["embedding"].astype(np.float32).tobytes(),
                    "angle_label": label,
                    "quality_score": cap["det_score"],
                })
            self.face_repo.create_embeddings_batch(str(registration.id), entries)
            self.db.commit()
            self.faiss.save()

            # Best-effort image persistence (matches register_face pattern)
            storage = FaceImageStorage()
            keys_by_faiss: dict[int, str] = {}
            for fid, cap, label in zip(faiss_ids, captures, labels):
                if not cap["crop_bytes"]:
                    continue
                key = storage.save_registration_image(user_id, label, cap["crop_bytes"])
                if key:
                    keys_by_faiss[int(fid)] = key
            if keys_by_faiss:
                self.face_repo.set_image_storage_keys(
                    str(registration.id), keys_by_faiss
                )
                self.db.commit()

            logger.info(
                "cctv_enroll: committed %d CCTV embeddings for user %s "
                "(FAISS IDs %s, mean sim to phone=%.3f)",
                len(captures), user_id, faiss_ids, mean_sim,
            )
        except Exception as exc:
            self.db.rollback()
            for fid in faiss_ids:
                with contextlib.suppress(Exception):
                    self.faiss.remove(fid)
            try:
                await self.rebuild_faiss_index()
            except Exception:
                logger.error("cctv_enroll: rebuild after rollback failed", exc_info=True)
            logger.error("cctv_enroll: persistence failed for user %s: %s", user_id, exc)
            raise FaceRecognitionError("Failed to persist CCTV embeddings") from exc

        return {
            "added": len(captures),
            "faiss_ids": faiss_ids,
            "labels": labels,
            "attempts": attempts,
            "skipped_reasons": skipped_reasons,
            "self_similarity_to_phone_mean": mean_sim,
            "self_similarity_to_phone_min": float(min(sims_to_phone)),
            "self_similarity_to_phone_max": float(max(sims_to_phone)),
            "per_capture": [
                {"faiss_id": fid, "label": lbl, "det_score": cap["det_score"], "bbox": cap["bbox"]}
                for fid, lbl, cap in zip(faiss_ids, labels, captures)
            ],
        }

    async def reregister_face(self, user_id: str, images: list[UploadFile]) -> tuple[int, str]:
        """
        Re-register user's face (update)

        Hard-deletes old registration first (including related embeddings),
        then registers fresh.  Cross-capture validation is warning-only,
        so the primary failure path (validation block) no longer exists.

        Args:
            user_id: User UUID
            images: New face images

        Returns:
            Tuple of (embedding_id, message, quality_reports)
        """
        # Hard-delete old registration so the unique constraint on user_id
        # won't block the new INSERT.  Embeddings cascade-delete via FK.
        old_registration = self.face_repo.get_by_user(user_id)
        if old_registration:
            self.db.delete(old_registration)
            self.db.commit()
            logger.info(f"Deleted old face registration for user {user_id}")

            # Clean old JPEGs BEFORE the new register writes, or a crash
            # during save would leave the new angle files mixed with old ones.
            try:
                FaceImageStorage().delete_user_images(user_id)
            except Exception:
                logger.warning(
                    f"Failed to clean old registration images for user {user_id}",
                    exc_info=True,
                )

        # Rebuild FAISS BEFORE register_face so the index is clean and
        # index.ntotal-based FAISS IDs assigned during registration match
        # the final index state.  Without this, register_face assigns IDs
        # based on a stale ntotal, then a post-register rebuild reassigns
        # all IDs from scratch — leaving DB faiss_ids out of sync.
        await self.rebuild_faiss_index()

        # Register new face (operates on the freshly rebuilt index)
        faiss_id, message, quality_reports = await self.register_face(user_id, images)

        return faiss_id, "Face re-registered successfully", quality_reports

    async def rebuild_faiss_index(self):
        """
        Rebuild FAISS index from active face embeddings.

        Prefers multi-embedding rows (face_embeddings table). Falls back to
        single averaged embedding in face_registrations for backward compat.
        """
        logger.info("Rebuilding FAISS index from active registrations...")

        embeddings_data = self._collect_embeddings_for_rebuild()

        if not embeddings_data:
            logger.warning("No active face registrations found")
            self.faiss.index = self.faiss._create_index()
            self.faiss.user_map = {}
            self.faiss.save()
            return

        self.faiss.rebuild(embeddings_data)
        logger.info(f"FAISS index rebuilt with {len(embeddings_data)} embeddings")

    def get_face_status(self, user_id: str) -> dict:
        """
        Get face registration status for user

        Args:
            user_id: User UUID

        Returns:
            Dictionary with registration status
        """
        registration = self.face_repo.get_by_user(user_id)

        if registration:
            return {
                "registered": True,
                "registered_at": registration.registered_at,
                "embedding_id": registration.embedding_id,
            }
        else:
            return {"registered": False, "registered_at": None, "embedding_id": None}

    def get_statistics(self) -> dict:
        """
        Get face recognition statistics

        Returns:
            Dictionary with stats
        """
        active_count = self.face_repo.count_active()
        total_count = self.face_repo.count_all()
        inactive_count = self.face_repo.count_inactive()
        faiss_stats = self.faiss.get_stats()

        return {
            "total_registered": total_count,
            "total_active": active_count,
            "total_inactive": inactive_count,
            "active_registrations": active_count,
            "faiss_vectors": faiss_stats["total_vectors"],
            "faiss_initialized": faiss_stats["initialized"],
        }

    def load_model(self):
        """
        Load InsightFace model (called during startup)
        """
        if self.facenet.app is None:
            self.facenet.load_model()

    def load_faiss_index(self):
        """
        Load FAISS index (called during startup)
        """
        self.faiss.load_or_create_index()

        # Load user mappings: prefer multi-embedding table, fallback to legacy
        multi_embs = self.face_repo.get_all_active_embeddings()
        if multi_embs:
            for emb in multi_embs:
                self.faiss.user_map[emb.faiss_id] = str(emb.registration.user_id)
        else:
            active_registrations = self.face_repo.get_active_embeddings()
            for reg in active_registrations:
                self.faiss.user_map[reg.embedding_id] = str(reg.user_id)

        logger.info(f"Loaded {len(self.faiss.user_map)} user mappings")

    def _collect_embeddings_for_rebuild(self) -> list:
        """Collect embedding data for FAISS rebuild, preferring multi-embedding table."""
        return FaceService._collect_embeddings_static(self.face_repo)

    @staticmethod
    def _collect_embeddings_static(repo: FaceRepository) -> list:
        """Collect (embedding, user_id) tuples from DB.

        Prefers face_embeddings table (multi-embedding). Falls back to
        face_registrations.embedding_vector for backward compatibility.
        """
        multi_embs = repo.get_all_active_embeddings()
        if multi_embs:
            return [
                (np.frombuffer(e.embedding_vector, dtype=np.float32), str(e.registration.user_id)) for e in multi_embs
            ]

        # Fallback: legacy single-embedding registrations
        active_regs = repo.get_active_embeddings()
        if active_regs:
            return [(np.frombuffer(r.embedding_vector, dtype=np.float32), str(r.user_id)) for r in active_regs]

        return []

    def save_faiss_index(self):
        """
        Save FAISS index (called during shutdown)
        """
        self.faiss.save()

    @staticmethod
    def reconcile_faiss_index(db: Session) -> bool:
        """
        Rebuild FAISS index and user_map from DB on every startup.

        Prefers multi-embedding rows (face_embeddings table). Falls back to
        single averaged embedding in face_registrations for backward compat.

        Args:
            db: SQLAlchemy database session

        Returns:
            True if a count mismatch was detected (index was stale), False if
            counts were already in sync (normal restart).
        """
        repo = FaceRepository(db)

        embeddings_data = FaceService._collect_embeddings_static(repo)
        db_count = len(embeddings_data)
        faiss_count = faiss_manager.index.ntotal if faiss_manager.index else 0
        was_mismatched = db_count != faiss_count

        if was_mismatched:
            logger.warning(
                f"FAISS/DB mismatch: FAISS has {faiss_count} vectors, "
                f"DB has {db_count} active embeddings. Rebuilding..."
            )

        if not embeddings_data:
            logger.info("FAISS: no active registrations, skipping rebuild")
            return was_mismatched

        faiss_manager.rebuild(embeddings_data)
        logger.info(
            f"FAISS index loaded: {len(embeddings_data)} embeddings, "
            f"user_map populated ({'mismatch fixed' if was_mismatched else 'in sync'})"
        )

        health = faiss_manager.check_health()
        logger.info("[FAISS-HEALTH] %s", health)
        if not health["healthy"]:
            logger.warning(
                "[FAISS-HEALTH] Index unhealthy! orphaned=%d dangling=%d",
                health["orphaned_vectors"],
                health["dangling_mappings"],
            )

        return was_mismatched
