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
        quality_reports: list[QualityReport] = []
        for i, image_file in enumerate(images):
            _img_start = time.monotonic()
            try:
                # Read image bytes
                image_bytes = await image_file.read()

                # Validate file size
                if len(image_bytes) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
                    raise ValidationError(f"Image {i + 1} exceeds size limit")

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
        Deregister user's face

        Marks face registration as inactive and rebuilds FAISS index.

        Args:
            user_id: User UUID

        Raises:
            NotFoundError: If no face registration found
        """
        # Deactivate in database
        self.face_repo.deactivate(user_id)

        logger.info(f"Face deregistered for user {user_id}")

        # Rebuild FAISS index
        await self.rebuild_faiss_index()

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
