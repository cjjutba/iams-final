"""
FAISS Index Manager

Manages FAISS vector index for fast face similarity search.
Uses IndexFlatIP for exact nearest neighbor search with inner product (cosine similarity).

The index is memory-mapped (IO_FLAG_MMAP) so that multiple Uvicorn workers
share the same physical RAM pages for the read-only vector data.  When any
worker mutates the index it saves to disk and publishes a Redis notification;
other workers pick up the notification and re-mmap the updated file.
"""

import asyncio
import os
import threading
from pathlib import Path

import faiss
import numpy as np

from app.config import logger, settings


class FAISSManager:
    """
    FAISS index manager for face embeddings

    Uses IndexFlatIP for exact nearest neighbor search.
    Maintains mapping between FAISS IDs and user IDs.
    """

    def __init__(self, index_path: str = None):
        """
        Initialize FAISS manager

        Args:
            index_path: Path to FAISS index file (default from settings)
        """
        self.index_path = index_path or settings.FAISS_INDEX_PATH
        self.dimension = 512  # ArcFace embedding dimension
        self.index: faiss.Index | None = None
        self.user_map: dict[int, str] = {}  # faiss_id → user_id mapping
        self._lock = threading.RLock()  # Thread safety for concurrent access
        self._adaptive_ids: list[int] = []  # Session-scoped adaptive embeddings (volatile, RAM only)

        # Ensure directory exists
        Path(self.index_path).parent.mkdir(parents=True, exist_ok=True)

    def load_or_create_index(self) -> faiss.Index:
        """
        Load existing FAISS index or create new one

        Returns:
            FAISS index

        Raises:
            RuntimeError: If index loading fails
        """
        with self._lock:
            if os.path.exists(self.index_path):
                try:
                    self.index = faiss.read_index(self.index_path, faiss.IO_FLAG_MMAP)
                    logger.info(f"Loaded FAISS index (mmap) from {self.index_path} ({self.index.ntotal} vectors)")
                    return self.index
                except Exception as e:
                    logger.error(f"Failed to load FAISS index: {e}")
                    raise RuntimeError(f"FAISS index loading failed: {e}") from e
            else:
                logger.info("Creating new FAISS index (IndexFlatIP)")
                self.index = self._create_index()
                self.save()
                return self.index

    def _create_index(self) -> faiss.Index:
        """
        Create new FAISS index

        Uses IndexFlatIP for exact inner product search (cosine similarity).

        Returns:
            New FAISS index
        """
        # IndexFlatIP: Exact search using inner product (for normalized vectors = cosine similarity)
        index = faiss.IndexFlatIP(self.dimension)
        return index

    def add(self, embedding: np.ndarray, user_id: str) -> int:
        """
        Add embedding to index

        Args:
            embedding: 512-dim face embedding (should be L2-normalized)
            user_id: User UUID

        Returns:
            FAISS ID (index position)

        Raises:
            RuntimeError: If index not initialized
            ValueError: If embedding dimension is incorrect
        """
        with self._lock:
            if self.index is None:
                raise RuntimeError("Index not initialized. Call load_or_create_index() first.")

            # Validate embedding dimension
            if embedding.shape[0] != self.dimension:
                raise ValueError(f"Expected embedding dimension {self.dimension}, got {embedding.shape[0]}")

            # Ensure 2D array [1, 512]
            if len(embedding.shape) == 1:
                embedding = embedding.reshape(1, -1)

            # Ensure float32
            embedding = embedding.astype(np.float32)

            # Get FAISS ID (current index size)
            faiss_id = self.index.ntotal

            # Add to index
            self.index.add(embedding)

            # Update user mapping
            self.user_map[faiss_id] = user_id

            logger.debug(f"Added embedding for user {user_id} at FAISS ID {faiss_id}")

            return faiss_id

    def add_batch(self, embeddings: np.ndarray, user_ids: list[str]) -> list[int]:
        """
        Add multiple embeddings to index

        Args:
            embeddings: Array of embeddings [N, 512]
            user_ids: List of user IDs (must match embeddings length)

        Returns:
            List of FAISS IDs

        Raises:
            ValueError: If lengths don't match or dimensions are wrong
        """
        with self._lock:
            if len(embeddings) != len(user_ids):
                raise ValueError("Embeddings and user_ids must have same length")

            if embeddings.shape[1] != self.dimension:
                raise ValueError(f"Expected embedding dimension {self.dimension}, got {embeddings.shape[1]}")

            # Ensure float32
            embeddings = embeddings.astype(np.float32)

            # Get starting FAISS ID
            start_id = self.index.ntotal

            # Add to index
            self.index.add(embeddings)

            # Update user mappings
            faiss_ids = list(range(start_id, start_id + len(user_ids)))
            for faiss_id, user_id in zip(faiss_ids, user_ids):
                self.user_map[faiss_id] = user_id

            logger.info(f"Added {len(embeddings)} embeddings to FAISS index")

            return faiss_ids

    def add_adaptive(self, embedding: np.ndarray, user_id: str) -> int:
        """Add a session-scoped adaptive embedding (volatile, RAM only).

        When a student is recognized with high confidence from the real CCTV
        camera, that embedding is added to FAISS for the duration of the
        session. On rebuild() or server restart, these are discarded
        (the index is rebuilt from DB which doesn't include them).

        This closes the phone→CCTV domain gap within the first session.
        """
        with self._lock:
            if self.index is None:
                raise RuntimeError("FAISS index not initialized")

            emb = embedding.reshape(1, -1).astype(np.float32)
            faiss_id = self.index.ntotal
            self.index.add(emb)
            self.user_map[faiss_id] = user_id
            self._adaptive_ids.append(faiss_id)
            logger.info(
                "Adaptive embedding added: faiss_id=%d user=%s total_adaptive=%d",
                faiss_id,
                user_id[:8],
                len(self._adaptive_ids),
            )
            return faiss_id

    @staticmethod
    def _deduplicate_by_user(
        raw: list[tuple[str, float]],
    ) -> list[tuple[str, float]]:
        """Keep only the best similarity per user_id, sorted descending."""
        best: dict[str, float] = {}
        for user_id, sim in raw:
            if user_id not in best or sim > best[user_id]:
                best[user_id] = sim
        return sorted(best.items(), key=lambda x: x[1], reverse=True)

    def search(self, embedding: np.ndarray, k: int = 1, threshold: float | None = None) -> list[tuple[str, float]]:
        """
        Search for similar faces (deduplicated by user_id).

        With multi-embedding storage, one user can have multiple vectors in
        the index. This method returns at most one result per user, keeping
        the highest similarity.

        Args:
            embedding: Query embedding (512-dim, L2-normalized)
            k: Number of unique users to return
            threshold: Optional similarity threshold (default from settings)

        Returns:
            List of (user_id, similarity) tuples, sorted by similarity (descending)
        """
        with self._lock:
            if self.index is None:
                raise RuntimeError("Index not initialized")

            if self.index.ntotal == 0:
                return []

            # Ensure 2D array [1, 512]
            if len(embedding.shape) == 1:
                embedding = embedding.reshape(1, -1)

            # Ensure float32
            embedding = embedding.astype(np.float32)

            # Fetch more results than requested to account for multi-embedding
            # duplicates. 15× covers up to 10 embeddings/user (5 phone + 5 CCTV-sim)
            # with headroom for k unique users.
            raw_k = min(k * 15, self.index.ntotal)
            similarities, indices = self.index.search(embedding, raw_k)

            # Collect raw results above threshold
            threshold = threshold or settings.RECOGNITION_THRESHOLD
            raw: list[tuple[str, float]] = []

            for i in range(raw_k):
                faiss_id = int(indices[0][i])
                similarity = float(similarities[0][i])

                if faiss_id == -1 or similarity < threshold:
                    continue

                user_id = self.user_map.get(faiss_id)
                if user_id:
                    raw.append((user_id, similarity))

            # Deduplicate: keep best similarity per user
            deduped = self._deduplicate_by_user(raw)
            return deduped[:k]

    def search_batch(
        self, embeddings: np.ndarray, k: int = 1, threshold: float | None = None
    ) -> list[list[tuple[str, float]]]:
        """
        Search for multiple faces (deduplicated by user_id per query).

        Args:
            embeddings: Array of query embeddings [N, 512]
            k: Number of unique users per query
            threshold: Optional similarity threshold

        Returns:
            List of result lists (one per query, deduplicated)
        """
        with self._lock:
            if self.index is None or self.index.ntotal == 0:
                return [[] for _ in range(len(embeddings))]

            # Ensure float32
            embeddings = embeddings.astype(np.float32)

            # Fetch more results to account for multi-embedding duplicates
            # 15× covers up to 10 embeddings/user (5 phone + 5 CCTV-sim)
            raw_k = min(k * 15, self.index.ntotal)
            similarities, indices = self.index.search(embeddings, raw_k)

            # Extract and deduplicate results per query
            threshold = threshold or settings.RECOGNITION_THRESHOLD
            batch_results = []

            for i in range(len(embeddings)):
                raw: list[tuple[str, float]] = []
                for j in range(raw_k):
                    faiss_id = int(indices[i][j])
                    similarity = float(similarities[i][j])

                    if faiss_id == -1 or similarity < threshold:
                        continue

                    user_id = self.user_map.get(faiss_id)
                    if user_id:
                        raw.append((user_id, similarity))

                deduped = self._deduplicate_by_user(raw)
                batch_results.append(deduped[:k])

            return batch_results

    def search_with_margin(
        self,
        embedding: np.ndarray,
        k: int = None,
        threshold: float = None,
        margin: float = None,
    ) -> dict:
        """
        Search with confidence margin check between top-1 and top-2.

        Returns dict:
          user_id: matched user or None
          confidence: similarity score
          is_ambiguous: True if gap between top-1 and top-2 is <= margin
        """
        if k is None:
            k = settings.RECOGNITION_TOP_K
        if threshold is None:
            threshold = settings.RECOGNITION_THRESHOLD
        if margin is None:
            margin = settings.RECOGNITION_MARGIN

        # Note: self.search() already acquires _lock (RLock allows re-entry)
        results = self.search(embedding, k=k, threshold=0.0)

        # Structured score logging — DEBUG level to avoid flooding logs.
        # Use calibrate_threshold.py for detailed score analysis.
        for rank, (uid, sim) in enumerate(results):
            logger.debug(
                "[FAISS-SCORE] rank=%d user=%s sim=%.4f threshold=%.4f",
                rank,
                uid[:8],
                sim,
                threshold,
            )
        if not results:
            logger.debug("[FAISS-SCORE] no_candidates index_size=%d", self.index.ntotal if self.index else 0)

        if not results:
            return {"user_id": None, "confidence": 0.0, "is_ambiguous": False}

        top_raw_score = results[0][1]
        if top_raw_score < threshold:
            return {"user_id": None, "confidence": float(top_raw_score), "is_ambiguous": False}

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

        decided_user = top_user if not is_ambiguous else None
        logger.debug(
            "[FAISS-DECISION] user=%s confidence=%.4f ambiguous=%s gap=%.4f threshold=%.4f margin=%.4f",
            decided_user[:8] if decided_user else "REJECTED",
            top_score,
            is_ambiguous,
            score_gap,
            threshold,
            margin,
        )

        return {
            "user_id": top_user,
            "confidence": float(top_score),
            "is_ambiguous": is_ambiguous,
        }

    def search_batch_with_margin(
        self,
        embeddings: np.ndarray,
        k: int = None,
        threshold: float = None,
        margin: float = None,
    ) -> list[dict]:
        """Batch version of search_with_margin — single lock, BLAS-parallelized.

        Args:
            embeddings: [N, 512] query embeddings (L2-normalized).
            k, threshold, margin: same semantics as search_with_margin().

        Returns:
            List of N dicts, each with user_id, confidence, is_ambiguous.
        """
        if k is None:
            k = settings.RECOGNITION_TOP_K
        if threshold is None:
            threshold = settings.RECOGNITION_THRESHOLD
        if margin is None:
            margin = settings.RECOGNITION_MARGIN

        batch_results = self.search_batch(embeddings, k=k, threshold=0.0)

        results = []
        for per_query in batch_results:
            if not per_query:
                results.append({
                    "user_id": None,
                    "confidence": 0.0,
                    "is_ambiguous": False,
                    "top1_user_id": None,
                    "top1_score": 0.0,
                    "top2_user_id": None,
                    "top2_score": 0.0,
                })
                continue

            top_raw_user, top_raw_score = per_query[0]
            # ``top1_*`` is always the unfiltered top-1 — the realtime
            # tracker uses it for the spatial+temporal identity hint
            # rescue path (see RealtimeTracker._recognize_batch). Below
            # threshold matches still surface this so a hint can confirm
            # at the relaxed delta without losing safety: the rescue
            # only applies when top1_user_id == identity.hint_user_id.
            top1_user_id = top_raw_user
            top1_score = float(top_raw_score)
            # ``top2_*`` carries the *second-best deduplicated user* and
            # the realtime tracker uses it as the Hungarian fallback when
            # two tracks collide on the same top-1 user_id (frame-level
            # mutual exclusion — see RealtimeTracker._resolve_frame_mutex).
            # Reported regardless of threshold so the resolver can see
            # the true score gap; the resolver re-applies the threshold
            # before committing.
            if len(per_query) > 1:
                top2_user_id = per_query[1][0]
                top2_score = float(per_query[1][1])
            else:
                top2_user_id = None
                top2_score = 0.0

            if top_raw_score < threshold:
                results.append({
                    "user_id": None,
                    "confidence": float(top_raw_score),
                    "is_ambiguous": False,
                    "top1_user_id": top1_user_id,
                    "top1_score": top1_score,
                    "top2_user_id": top2_user_id,
                    "top2_score": top2_score,
                })
                continue

            top_user, top_score = per_query[0]
            second_score = per_query[1][1] if len(per_query) > 1 else 0.0
            score_gap = top_score - second_score
            is_ambiguous = score_gap <= margin

            if is_ambiguous:
                logger.warning(
                    "Ambiguous match: top=%s (%.3f), second=%s (%.3f), gap=%.3f <= margin=%.3f",
                    top_user,
                    top_score,
                    per_query[1][0] if len(per_query) > 1 else "N/A",
                    second_score,
                    score_gap,
                    margin,
                )

            results.append({
                "user_id": top_user if not is_ambiguous else None,
                "confidence": float(top_score),
                "is_ambiguous": is_ambiguous,
                "top1_user_id": top1_user_id,
                "top1_score": top1_score,
                "top2_user_id": top2_user_id,
                "top2_score": top2_score,
            })

        return results

    def check_health(self) -> dict:
        """Check index health and report inconsistencies."""
        if self.index is None:
            return {"healthy": False, "reason": "index not initialized"}

        ntotal = self.index.ntotal
        map_size = len(self.user_map)
        unique_users = len(set(self.user_map.values()))
        orphaned = ntotal - map_size if ntotal > map_size else 0
        dangling = sum(1 for fid in self.user_map if fid >= ntotal)

        healthy = orphaned == 0 and dangling == 0
        return {
            "healthy": healthy,
            "ntotal": ntotal,
            "user_map_size": map_size,
            "unique_users": unique_users,
            "orphaned_vectors": orphaned,
            "dangling_mappings": dangling,
        }

    def remove(self, faiss_id: int) -> bool:
        """
        Remove embedding from index

        Note: IndexFlatIP does not support native deletion.
        This marks the entry as removed in user_map but doesn't actually remove from index.
        Call rebuild() to create a new index without removed entries.

        Args:
            faiss_id: FAISS ID to remove

        Returns:
            True if removed

        Raises:
            NotImplementedError: IndexFlatIP does not support deletion
        """
        with self._lock:
            # IndexFlatIP doesn't support native deletion
            # Remove from user map instead
            if faiss_id in self.user_map:
                del self.user_map[faiss_id]
                logger.debug(f"Removed FAISS ID {faiss_id} from user map (index rebuild required)")
                return True
            return False

    def rebuild(self, embeddings_data: list[tuple[np.ndarray, str]]) -> dict[int, str]:
        """
        Rebuild index from scratch

        Used when embeddings are removed or updated.

        Args:
            embeddings_data: List of (embedding, user_id) tuples

        Returns:
            New faiss_id -> user_id mapping (callers can use this to update
            face_embeddings.faiss_id in the DB to stay in sync)

        Raises:
            ValueError: If embeddings_data is empty or invalid
        """
        with self._lock:
            # rebuild() always discards volatile adaptive IDs — they
            # referenced positions in the OLD index. Failing to clear here
            # leaves a stale list that later add_adaptive()/save() calls
            # treat as live, leading to confusing "ghost" log lines and a
            # latent bug if any code path ever consults _adaptive_ids
            # directly to decide whether to re-add a vector.
            adaptive_dropped = len(self._adaptive_ids)
            self._adaptive_ids.clear()

            if not embeddings_data:
                logger.warning(
                    "No embeddings provided for rebuild, creating empty index "
                    "(dropped %d adaptive vector(s))",
                    adaptive_dropped,
                )
                self.index = self._create_index()
                self.user_map = {}
                self.save()
                return {}

            logger.info(
                "Rebuilding FAISS index with %d embeddings (dropped %d adaptive)...",
                len(embeddings_data),
                adaptive_dropped,
            )

            # Create new index
            self.index = self._create_index()
            self.user_map = {}

            # Add all embeddings (RLock allows re-entry from add_batch)
            embeddings = np.array([emb for emb, _ in embeddings_data], dtype=np.float32)
            user_ids = [user_id for _, user_id in embeddings_data]

            self.add_batch(embeddings, user_ids)

            # Save rebuilt index
            self.save()

            logger.info("FAISS index rebuilt successfully")

            # Return a copy of the new mapping so callers can sync DB faiss_ids
            return dict(self.user_map)

    def save(self, path: str | None = None):
        """
        Save FAISS index to disk and notify other workers to reload.

        Args:
            path: Optional custom path (default: self.index_path)

        Raises:
            RuntimeError: If index not initialized
        """
        with self._lock:
            if self.index is None:
                raise RuntimeError("Index not initialized")

            save_path = path or self.index_path
            tmp_path = save_path + ".tmp"

            try:
                faiss.write_index(self.index, tmp_path)
                os.replace(tmp_path, save_path)  # atomic on POSIX — prevents partial-write corruption
                logger.info(f"FAISS index saved to {save_path} ({self.index.ntotal} vectors)")
            except Exception as e:
                logger.error(f"Failed to save FAISS index: {e}")
                raise

        # Notify other workers to reload the updated index (outside lock —
        # async I/O should not hold the lock)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.notify_index_changed())
        except RuntimeError:
            # No running event loop (e.g. during tests or CLI scripts) — skip notification
            pass

    # ------------------------------------------------------------------
    # Redis pub/sub for multi-worker index synchronisation
    # ------------------------------------------------------------------

    async def notify_index_changed(self):
        """Publish index-change event so other workers reload."""
        try:
            from app.redis_client import get_redis

            r = await get_redis()
            await r.publish("faiss_reload", b"reload")
            logger.debug("Published FAISS reload notification")
        except Exception as e:
            logger.warning(f"Failed to publish FAISS reload notification: {e}")

    def rebuild_user_map_from_db(self):
        """Rebuild user_map from database so FAISS IDs map to user_ids.

        Must be called after load_or_create_index() to keep user_map in sync.
        Without this, FAISS search returns vector matches but cannot resolve
        them to user_ids, causing recognized faces to appear as "Unknown".

        IMPORTANT: This only rebuilds the in-memory user_map dict.  It does
        NOT call rebuild()/save() — doing so would publish another Redis
        notification and create an infinite reload loop.
        """
        from app.database import SessionLocal
        from app.repositories.face_repository import FaceRepository

        db = SessionLocal()
        try:
            repo = FaceRepository(db)
            self.user_map = {}

            # Prefer multi-embedding table (face_embeddings)
            multi_embs = repo.get_all_active_embeddings()
            if multi_embs:
                for emb in multi_embs:
                    self.user_map[emb.faiss_id] = str(emb.registration.user_id)
            else:
                # Fallback: legacy single-embedding registrations
                active_regs = repo.get_active_embeddings()
                for reg in active_regs:
                    self.user_map[reg.embedding_id] = str(reg.user_id)

            logger.info(
                "user_map rebuilt from DB: %d mappings, %d vectors",
                len(self.user_map),
                self.index.ntotal if self.index else 0,
            )
        except Exception:
            logger.exception("Failed to rebuild user_map from DB")
        finally:
            db.close()

    async def subscribe_index_changes(self):
        """Listen for index-change events and reload (runs forever as a background task)."""
        import asyncio

        from app.redis_client import get_redis

        while True:
            try:
                r = await get_redis()
                pubsub = r.pubsub()
                await pubsub.subscribe("faiss_reload")
                logger.info("Subscribed to FAISS reload notifications")

                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            self.load_or_create_index()
                            # Rebuild user_map from DB — without this,
                            # FAISS search can't resolve IDs to user_ids
                            self.rebuild_user_map_from_db()
                            logger.info("FAISS index reloaded from disk (notified by another worker)")
                        except Exception as e:
                            logger.error(f"Failed to reload FAISS index after notification: {e}")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("FAISS reload subscriber connection lost, reconnecting...")
                await asyncio.sleep(1)

    def get_stats(self) -> dict:
        """
        Get index statistics

        Returns:
            Dictionary with index stats
        """
        if self.index is None:
            return {"initialized": False, "total_vectors": 0, "dimension": self.dimension, "index_type": None}

        return {
            "initialized": True,
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "index_type": "IndexFlatIP",
            "user_mappings": len(self.user_map),
        }


# Global FAISS manager instance (initialized in startup)
faiss_manager = FAISSManager()
