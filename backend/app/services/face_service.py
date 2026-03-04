"""
Face Service

Business logic for face registration and recognition.
Orchestrates InsightFace (ArcFace) model, FAISS search, and database operations.
"""

import io
from typing import List, Tuple, Optional
from fastapi import UploadFile
from sqlalchemy.orm import Session
import numpy as np
from PIL import Image

from app.repositories.face_repository import FaceRepository
from app.services.ml.insightface_model import insightface_model
from app.services.ml.faiss_manager import faiss_manager
from app.services.ml.face_quality import assess_quality, QualityReport
from app.utils.exceptions import ValidationError, FaceRecognitionError, NotFoundError
from app.config import settings, logger


class FaceService:
    """Service for face registration and recognition operations"""

    def __init__(self, db: Session):
        self.db = db
        self.face_repo = FaceRepository(db)
        self.facenet = insightface_model
        self.faiss = faiss_manager

    async def register_face(
        self,
        user_id: str,
        images: List[UploadFile]
    ) -> Tuple[int, str, Optional[List[QualityReport]]]:
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
            raise ValidationError(
                f"Minimum {settings.MIN_FACE_IMAGES} images required for registration"
            )

        if len(images) > settings.MAX_FACE_IMAGES:
            raise ValidationError(
                f"Maximum {settings.MAX_FACE_IMAGES} images allowed"
            )

        # Check if user already has registered face
        existing = self.face_repo.get_by_user(user_id)
        if existing:
            raise ValidationError("User already has registered face. Use re-register to update.")

        logger.info(f"Registering face for user {user_id} with {len(images)} images")

        # Generate embeddings for each image
        embeddings = []
        quality_reports: List[QualityReport] = []
        for i, image_file in enumerate(images):
            try:
                # Read image bytes
                image_bytes = await image_file.read()

                # Validate file size
                if len(image_bytes) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
                    raise ValidationError(f"Image {i+1} exceeds size limit")

                # Generate embedding (with quality metadata if available)
                if settings.QUALITY_GATE_ENABLED and hasattr(self.facenet, 'get_face_with_quality'):
                    face_data = self.facenet.get_face_with_quality(image_bytes)
                    embedding = face_data["embedding"]
                    quality = assess_quality(
                        image_bgr=face_data["image_bgr"],
                        det_score=face_data["det_score"],
                        bbox=face_data["bbox"],
                        image_shape=face_data["image_bgr"].shape,
                    )
                    quality_reports.append(quality)
                    if not quality.passed:
                        raise ValidationError(
                            f"Image {i+1} rejected: {', '.join(quality.rejection_reasons)}"
                        )
                else:
                    embedding = self.facenet.get_embedding(image_bytes)

                embeddings.append(embedding)

                logger.debug(f"Generated embedding for image {i+1}/{len(images)}")

            except ValidationError:
                raise
            except ValueError as e:
                raise FaceRecognitionError(f"Image {i+1}: {str(e)}")
            except Exception as e:
                logger.error(f"Failed to process image {i+1}: {e}")
                raise FaceRecognitionError(f"Failed to process image {i+1}")

        if not embeddings:
            raise FaceRecognitionError("No valid face embeddings generated")

        # Average embeddings to get single representative embedding
        avg_embedding = np.mean(embeddings, axis=0)

        # L2 normalize (for cosine similarity)
        avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)

        # Add to FAISS index
        try:
            faiss_id = self.faiss.add(avg_embedding, user_id)
        except Exception as e:
            logger.error(f"Failed to add to FAISS: {e}")
            raise FaceRecognitionError("Failed to index face embedding")

        # Convert embedding to bytes for database storage
        embedding_bytes = avg_embedding.astype(np.float32).tobytes()

        # Transaction: DB insert with FAISS rollback on failure
        try:
            self.face_repo.create(user_id, faiss_id, embedding_bytes)

            # Persist FAISS index to disk only after DB commit succeeds
            self.faiss.save()

            logger.info(f"Face registered successfully for user {user_id} (FAISS ID: {faiss_id})")
        except Exception as e:
            # Rollback DB transaction
            self.db.rollback()

            # Rollback FAISS addition since DB commit failed
            try:
                self.faiss.remove(faiss_id)
                logger.info(f"Rolled back FAISS entry {faiss_id} for user {user_id}")
            except Exception as remove_err:
                logger.error(f"Failed to rollback FAISS entry {faiss_id}: {remove_err}")

            logger.error(f"Failed to save face registration for user {user_id}: {e}")
            raise FaceRecognitionError("Failed to save face registration")

        return faiss_id, "Face registered successfully", quality_reports or None

    async def recognize_face(
        self,
        image_bytes: bytes,
        threshold: Optional[float] = None
    ) -> Tuple[Optional[str], Optional[float]]:
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
            # Generate embedding
            embedding = self.facenet.get_embedding(image_bytes)

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
            raise FaceRecognitionError(f"Face recognition failed: {str(e)}")

    async def recognize_batch(
        self,
        images_bytes: List[bytes],
        threshold: Optional[float] = None
    ) -> List[dict]:
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

        for batch_idx, (orig_idx, matches) in enumerate(zip(index_map, search_results)):
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

    async def reregister_face(
        self,
        user_id: str,
        images: List[UploadFile]
    ) -> Tuple[int, str]:
        """
        Re-register user's face (update)

        Deletes old face registration, registers new one, and rebuilds
        FAISS index to remove orphaned vectors from the old registration.

        Args:
            user_id: User UUID
            images: New face images

        Returns:
            Tuple of (embedding_id, message)
        """
        # Delete old registration (if exists)
        try:
            old_registration = self.face_repo.get_by_user(user_id)
            if old_registration:
                self.face_repo.delete(str(old_registration.id))
                logger.info(f"Deleted old face registration for user {user_id}")
        except NotFoundError:
            logger.info(f"No previous face registration found for user {user_id}")

        # Register new face
        faiss_id, message, quality_reports = await self.register_face(user_id, images)

        # Rebuild FAISS to remove orphaned vectors from old registration
        await self.rebuild_faiss_index()

        return faiss_id, "Face re-registered successfully", quality_reports

    async def rebuild_faiss_index(self):
        """
        Rebuild FAISS index from active face registrations

        This is necessary after deletions since IndexFlatIP doesn't support native deletion.
        """
        logger.info("Rebuilding FAISS index from active registrations...")

        # Get all active face registrations
        active_registrations = self.face_repo.get_active_embeddings()

        if not active_registrations:
            logger.warning("No active face registrations found")
            self.faiss.index = self.faiss._create_index()
            self.faiss.user_map = {}
            self.faiss.save()
            return

        # Prepare embeddings data
        embeddings_data = []
        for reg in active_registrations:
            # Convert bytes back to numpy array
            embedding = np.frombuffer(reg.embedding_vector, dtype=np.float32)
            embeddings_data.append((embedding, str(reg.user_id)))

        # Rebuild FAISS index
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
                "embedding_id": registration.embedding_id
            }
        else:
            return {
                "registered": False,
                "registered_at": None,
                "embedding_id": None
            }

    def get_statistics(self) -> dict:
        """
        Get face recognition statistics

        Returns:
            Dictionary with stats
        """
        active_count = self.face_repo.count_active()
        faiss_stats = self.faiss.get_stats()

        return {
            "active_registrations": active_count,
            "faiss_vectors": faiss_stats["total_vectors"],
            "faiss_initialized": faiss_stats["initialized"]
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

        # Load user mappings from database
        active_registrations = self.face_repo.get_active_embeddings()
        for reg in active_registrations:
            self.faiss.user_map[reg.embedding_id] = str(reg.user_id)

        logger.info(f"Loaded {len(self.faiss.user_map)} user mappings")

    def save_faiss_index(self):
        """
        Save FAISS index (called during shutdown)
        """
        self.faiss.save()

    @staticmethod
    def reconcile_faiss_index(db: Session) -> bool:
        """
        Rebuild FAISS user_map from DB on every startup.

        ``faiss_manager.load_or_create_index()`` restores index vectors from
        disk but cannot restore ``user_map`` (FAISS files store vectors only).
        Without user_map every search returns None even when the correct vector
        is found.  Rebuilding from the DB-stored embedding bytes is the only
        reliable way to keep the in-memory map consistent after restarts,
        deregistrations, or re-registrations.

        Args:
            db: SQLAlchemy database session

        Returns:
            True if a count mismatch was detected (index was stale), False if
            counts were already in sync (normal restart).
        """
        repo = FaceRepository(db)

        active_regs = repo.get_active_embeddings()
        active_count = len(active_regs)
        faiss_count = faiss_manager.index.ntotal if faiss_manager.index else 0
        was_mismatched = active_count != faiss_count

        if was_mismatched:
            logger.warning(
                f"FAISS/DB mismatch: FAISS has {faiss_count} vectors, "
                f"DB has {active_count} active registrations. Rebuilding..."
            )

        if not active_regs:
            # No registrations yet — leave the (possibly empty) index as-is.
            logger.info("FAISS: no active registrations, skipping rebuild")
            return was_mismatched

        # Always rebuild from DB embedding bytes so that user_map is populated
        # correctly regardless of whether a crash or deregistration occurred.
        embeddings_data = [
            (np.frombuffer(r.embedding_vector, dtype=np.float32), str(r.user_id))
            for r in active_regs
        ]
        faiss_manager.rebuild(embeddings_data)
        logger.info(
            f"FAISS index loaded: {len(embeddings_data)} embeddings, "
            f"user_map populated ({'mismatch fixed' if was_mismatched else 'in sync'})"
        )
        return was_mismatched
