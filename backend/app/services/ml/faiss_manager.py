"""
FAISS Index Manager

Manages FAISS vector index for fast face similarity search.
Uses IndexFlatIP for exact nearest neighbor search with inner product (cosine similarity).
"""

import os
import faiss
import numpy as np
from typing import List, Tuple, Optional, Dict
from pathlib import Path

from app.config import settings, logger


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
        self.index: Optional[faiss.Index] = None
        self.user_map: Dict[int, str] = {}  # faiss_id → user_id mapping

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
        if os.path.exists(self.index_path):
            try:
                self.index = faiss.read_index(self.index_path)
                logger.info(f"Loaded FAISS index from {self.index_path} ({self.index.ntotal} vectors)")
                return self.index
            except Exception as e:
                logger.error(f"Failed to load FAISS index: {e}")
                raise RuntimeError(f"FAISS index loading failed: {e}")
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

    def add_batch(self, embeddings: np.ndarray, user_ids: List[str]) -> List[int]:
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

    def search(
        self,
        embedding: np.ndarray,
        k: int = 1,
        threshold: Optional[float] = None
    ) -> List[Tuple[str, float]]:
        """
        Search for similar faces

        Args:
            embedding: Query embedding (512-dim, L2-normalized)
            k: Number of nearest neighbors to return
            threshold: Optional similarity threshold (default from settings)

        Returns:
            List of (user_id, similarity) tuples, sorted by similarity (descending)

        Raises:
            RuntimeError: If index not initialized or empty
        """
        if self.index is None:
            raise RuntimeError("Index not initialized")

        if self.index.ntotal == 0:
            return []

        # Ensure 2D array [1, 512]
        if len(embedding.shape) == 1:
            embedding = embedding.reshape(1, -1)

        # Ensure float32
        embedding = embedding.astype(np.float32)

        # Search index
        similarities, indices = self.index.search(embedding, k)

        # Extract results
        results = []
        threshold = threshold or settings.RECOGNITION_THRESHOLD

        for i in range(k):
            faiss_id = int(indices[0][i])
            similarity = float(similarities[0][i])

            # Check if valid result
            if faiss_id == -1:  # FAISS returns -1 for no match
                continue

            # Apply threshold
            if similarity < threshold:
                continue

            # Get user ID
            user_id = self.user_map.get(faiss_id)
            if user_id:
                results.append((user_id, similarity))

        return results

    def search_batch(
        self,
        embeddings: np.ndarray,
        k: int = 1,
        threshold: Optional[float] = None
    ) -> List[List[Tuple[str, float]]]:
        """
        Search for multiple faces

        Args:
            embeddings: Array of query embeddings [N, 512]
            k: Number of nearest neighbors per query
            threshold: Optional similarity threshold

        Returns:
            List of result lists (one per query)
        """
        if self.index is None or self.index.ntotal == 0:
            return [[] for _ in range(len(embeddings))]

        # Ensure float32
        embeddings = embeddings.astype(np.float32)

        # Search index
        similarities, indices = self.index.search(embeddings, k)

        # Extract results
        threshold = threshold or settings.RECOGNITION_THRESHOLD
        batch_results = []

        for i in range(len(embeddings)):
            results = []
            for j in range(k):
                faiss_id = int(indices[i][j])
                similarity = float(similarities[i][j])

                if faiss_id == -1 or similarity < threshold:
                    continue

                user_id = self.user_map.get(faiss_id)
                if user_id:
                    results.append((user_id, similarity))

            batch_results.append(results)

        return batch_results

    def search_with_margin(
        self,
        embedding: np.ndarray,
        k: int = None,
        threshold: float = None,
        margin: float = None,
    ) -> Dict:
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

        # Get all k results (unfiltered by threshold)
        results = self.search(embedding, k=k, threshold=0.0)

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
        # IndexFlatIP doesn't support native deletion
        # Remove from user map instead
        if faiss_id in self.user_map:
            del self.user_map[faiss_id]
            logger.debug(f"Removed FAISS ID {faiss_id} from user map (index rebuild required)")
            return True
        return False

    def rebuild(self, embeddings_data: List[Tuple[np.ndarray, str]]):
        """
        Rebuild index from scratch

        Used when embeddings are removed or updated.

        Args:
            embeddings_data: List of (embedding, user_id) tuples

        Raises:
            ValueError: If embeddings_data is empty or invalid
        """
        if not embeddings_data:
            logger.warning("No embeddings provided for rebuild, creating empty index")
            self.index = self._create_index()
            self.user_map = {}
            self.save()
            return

        logger.info(f"Rebuilding FAISS index with {len(embeddings_data)} embeddings...")

        # Create new index
        self.index = self._create_index()
        self.user_map = {}

        # Add all embeddings
        embeddings = np.array([emb for emb, _ in embeddings_data], dtype=np.float32)
        user_ids = [user_id for _, user_id in embeddings_data]

        self.add_batch(embeddings, user_ids)

        # Save rebuilt index
        self.save()

        logger.info("FAISS index rebuilt successfully")

    def save(self, path: Optional[str] = None):
        """
        Save FAISS index to disk

        Args:
            path: Optional custom path (default: self.index_path)

        Raises:
            RuntimeError: If index not initialized
        """
        if self.index is None:
            raise RuntimeError("Index not initialized")

        save_path = path or self.index_path

        try:
            faiss.write_index(self.index, save_path)
            logger.info(f"FAISS index saved to {save_path} ({self.index.ntotal} vectors)")
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")
            raise

    def get_stats(self) -> Dict:
        """
        Get index statistics

        Returns:
            Dictionary with index stats
        """
        if self.index is None:
            return {
                "initialized": False,
                "total_vectors": 0,
                "dimension": self.dimension,
                "index_type": None
            }

        return {
            "initialized": True,
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "index_type": "IndexFlatIP",
            "user_mappings": len(self.user_map)
        }


# Global FAISS manager instance (initialized in startup)
faiss_manager = FAISSManager()
