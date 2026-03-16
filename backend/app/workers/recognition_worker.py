# backend/app/workers/recognition_worker.py
"""
Recognition Worker -- Standalone container process.

Consumes: stream:recognition_req  (face crops from detection worker)
Publishes: stream:recognitions  (identity matches from FAISS)

Uses ArcFace (InsightFace) for embedding + FAISS for nearest neighbor search.
Event-driven: only processes new/unidentified tracks, not every frame.
"""
import base64
import logging
import time

import cv2
import numpy as np

from app.config import settings
from app.database import SessionLocal
from app.repositories.user_repository import UserRepository
from app.services.ml.faiss_manager import faiss_manager
from app.services.ml.insightface_model import insightface_model
from app.services.stream_bus import STREAM_RECOGNITION_REQ
from app.workers.base_worker import BaseWorker, run_worker

logger = logging.getLogger(__name__)


class RecognitionWorker(BaseWorker):
    def __init__(self):
        super().__init__(
            name="recognition-worker",
            group=settings.RECOGNITION_GROUP,
        )
        # Cache: user_id -> {name, student_id} (TTL managed manually)
        self._user_cache: dict[str, dict] = {}

    async def setup(self):
        await super().setup()

        # Load InsightFace ArcFace model (SCRFD + ArcFace from buffalo_l)
        logger.info(f"[{self.name}] Loading InsightFace model...")
        insightface_model.load_model()
        logger.info(f"[{self.name}] InsightFace model loaded")

        # Load FAISS index
        logger.info(f"[{self.name}] Loading FAISS index...")
        faiss_manager.load_or_create_index()
        logger.info(
            f"[{self.name}] Ready -- FAISS has {faiss_manager.index.ntotal} vectors"
        )

    async def get_streams(self) -> dict[str, str]:
        return {STREAM_RECOGNITION_REQ: ">"}

    async def process_message(self, stream: str, msg_id: str, data: dict):
        room_id = data.get("room_id", "unknown")
        track_id = data.get("track_id", -1)
        t_start = time.time()

        # ---- Decode face crop from base64 JPEG ----
        crop_b64 = data.get("face_crop_b64", "")
        if not crop_b64:
            return

        crop_bytes = base64.b64decode(crop_b64)
        nparr = np.frombuffer(crop_bytes, np.uint8)
        face_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if face_img is None:
            logger.warning(
                f"[{self.name}] Failed to decode face crop for track {track_id}"
            )
            return

        # ---- Generate ArcFace embedding ----
        try:
            embedding = insightface_model.get_embedding(face_img)
        except ValueError:
            # No face detected in the crop (e.g. partial occlusion)
            logger.debug(
                f"[{self.name}] No face found in crop for track {track_id}"
            )
            return

        # ---- FAISS search with margin check ----
        # search_with_margin handles threshold + top-1 vs top-2 margin + solo ceiling
        result = faiss_manager.search_with_margin(embedding)

        user_id = result.get("user_id")
        confidence = result.get("confidence", 0.0)
        is_ambiguous = result.get("is_ambiguous", False)

        if user_id is None:
            logger.debug(
                f"[{self.name}] No match for track {track_id} "
                f"(confidence={confidence:.3f})"
            )
            return

        if is_ambiguous:
            logger.debug(
                f"[{self.name}] Ambiguous match for track {track_id} "
                f"(user={user_id}, confidence={confidence:.3f}) -- skipping"
            )
            return

        # ---- Lookup user info (cached) ----
        user_info = self._get_user_info(user_id)

        # ---- Publish recognition result ----
        recognition = {
            "room_id": room_id,
            "track_id": track_id,
            "user_id": user_id,
            "name": user_info.get("name", "Unknown"),
            "student_id": user_info.get("student_id", ""),
            "similarity": round(confidence, 4),
            "timestamp": data.get("timestamp", ""),
        }
        await self.bus.publish_recognition_result(recognition)

        latency_ms = (time.time() - t_start) * 1000
        logger.info(
            f"[{self.name}] track={track_id} -> {user_info.get('name', '?')} "
            f"sim={confidence:.3f} latency={latency_ms:.0f}ms"
        )

    def _get_user_info(self, user_id: str) -> dict:
        """Get user name and student_id, with in-memory cache."""
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        info = {"name": "Unknown", "student_id": ""}
        try:
            db = SessionLocal()
            try:
                user_repo = UserRepository(db)
                user = user_repo.get_by_id(user_id)
                if user:
                    info = {
                        "name": user.full_name or user.email,
                        "student_id": user.student_id or "",
                    }
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[{self.name}] DB lookup failed for {user_id}: {e}")

        self._user_cache[user_id] = info
        return info


# -- Entry point --

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    worker = RecognitionWorker()
    run_worker(worker)
