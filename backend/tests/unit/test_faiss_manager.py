"""
Unit Tests for FAISS Manager

Tests FAISSManager class using real FAISS operations (no mocking).
FAISS IndexFlatIP operations are fast in-memory, so real operations
are preferred over mocks for accurate behavior verification.

Covers: index creation, load/save, add/add_batch, search/search_batch,
remove (user_map only), rebuild, and get_stats.
"""

import os

import numpy as np
import pytest

from app.services.ml.faiss_manager import FAISSManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_embedding(seed: int = None) -> np.ndarray:
    """Create a random 512-dim L2-normalized vector.

    Using a seed produces a deterministic vector, which is useful for
    verifying that search returns the correct match.
    """
    rng = np.random.RandomState(seed)
    emb = rng.randn(512).astype(np.float32)
    return emb / np.linalg.norm(emb)


def _make_orthogonal_pair() -> tuple:
    """Return two 512-dim vectors with near-zero cosine similarity.

    Gram-Schmidt on two random vectors ensures they are orthogonal,
    which means their inner product (cosine similarity for unit vectors)
    is approximately 0.
    """
    rng = np.random.RandomState(42)
    v1 = rng.randn(512).astype(np.float32)
    v1 = v1 / np.linalg.norm(v1)

    v2 = rng.randn(512).astype(np.float32)
    # Remove the component of v2 along v1
    v2 = v2 - np.dot(v2, v1) * v1
    v2 = v2 / np.linalg.norm(v2)

    return v1, v2


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFAISSManager:
    """Unit tests for FAISSManager."""

    # -- Index creation and loading ----------------------------------------

    def test_create_index(self, tmp_path):
        """_create_index returns a new IndexFlatIP with 0 vectors."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        index = manager._create_index()

        assert index is not None
        assert index.ntotal == 0

    def test_load_or_create_new(self, tmp_path):
        """When no index file exists, load_or_create_index creates a new
        empty index and persists it to disk."""
        path = str(tmp_path / "test.index")
        manager = FAISSManager(index_path=path)
        manager.load_or_create_index()

        assert manager.index is not None
        assert manager.index.ntotal == 0
        assert os.path.exists(path)

    def test_load_existing_index(self, tmp_path):
        """A saved index can be loaded by a fresh FAISSManager instance
        and retains the same number of vectors."""
        path = str(tmp_path / "test.index")

        # First manager: create and populate
        m1 = FAISSManager(index_path=path)
        m1.load_or_create_index()
        m1.add(_make_embedding(seed=1), "user-aaa")
        m1.add(_make_embedding(seed=2), "user-bbb")
        m1.save()

        # Second manager: load from disk
        m2 = FAISSManager(index_path=path)
        m2.load_or_create_index()

        assert m2.index.ntotal == 2

    # -- Adding embeddings -------------------------------------------------

    def test_add_embedding(self, tmp_path):
        """Adding a single embedding increments ntotal and updates user_map."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        manager.load_or_create_index()

        emb = _make_embedding(seed=10)
        faiss_id = manager.add(emb, "user-123")

        assert faiss_id == 0
        assert manager.index.ntotal == 1
        assert manager.user_map[0] == "user-123"

    def test_add_wrong_dimension(self, tmp_path):
        """Adding a vector with incorrect dimension raises ValueError."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        manager.load_or_create_index()

        wrong_dim = np.random.randn(256).astype(np.float32)
        with pytest.raises(ValueError, match="Expected embedding dimension 512"):
            manager.add(wrong_dim, "user-bad")

    def test_add_not_initialized(self, tmp_path):
        """Adding to an uninitialized index (index=None) raises RuntimeError."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        # Do NOT call load_or_create_index
        emb = _make_embedding()
        with pytest.raises(RuntimeError, match="not initialized"):
            manager.add(emb, "user-fail")

    def test_add_batch(self, tmp_path):
        """add_batch inserts multiple vectors and assigns sequential IDs."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        manager.load_or_create_index()

        embeddings = np.array([
            _make_embedding(seed=1),
            _make_embedding(seed=2),
            _make_embedding(seed=3),
        ])
        user_ids = ["user-a", "user-b", "user-c"]

        ids = manager.add_batch(embeddings, user_ids)

        assert ids == [0, 1, 2]
        assert manager.index.ntotal == 3
        assert manager.user_map[0] == "user-a"
        assert manager.user_map[1] == "user-b"
        assert manager.user_map[2] == "user-c"

    # -- Search ------------------------------------------------------------

    def test_search_match(self, tmp_path):
        """Searching with the same vector that was added returns a high
        similarity score (near 1.0) and the correct user_id."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        manager.load_or_create_index()

        emb = _make_embedding(seed=42)
        manager.add(emb, "user-match")

        results = manager.search(emb, k=1, threshold=0.5)

        assert len(results) == 1
        user_id, similarity = results[0]
        assert user_id == "user-match"
        assert similarity > 0.99  # Same vector -> ~1.0

    def test_search_no_match(self, tmp_path):
        """Searching with a vector orthogonal to the stored one returns
        no results when using the default threshold (0.6)."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        manager.load_or_create_index()

        v1, v2 = _make_orthogonal_pair()
        manager.add(v1, "user-stored")

        # Orthogonal vector has ~0 similarity, well below 0.6 threshold
        results = manager.search(v2, k=1, threshold=0.6)

        assert len(results) == 0

    def test_search_empty_index(self, tmp_path):
        """Searching an empty index returns an empty list without crashing."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        manager.load_or_create_index()

        emb = _make_embedding()
        results = manager.search(emb, k=1)

        assert results == []

    def test_search_threshold_filters_moderate_matches(self, tmp_path):
        """A high threshold filters out matches with moderate similarity.

        We create a query vector by blending the stored vector (40%) with
        a random vector (60%), producing ~0.55 cosine similarity.  This
        passes a 0.4 threshold but fails a 0.99 threshold.
        """
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        manager.load_or_create_index()

        rng = np.random.RandomState(100)
        base = rng.randn(512).astype(np.float32)
        base = base / np.linalg.norm(base)

        # Create a "moderately similar" vector via blending
        rng2 = np.random.RandomState(200)
        rand = rng2.randn(512).astype(np.float32)
        rand = rand / np.linalg.norm(rand)
        moderate = 0.4 * base + 0.6 * rand
        moderate = (moderate / np.linalg.norm(moderate)).astype(np.float32)

        manager.add(base, "user-base")

        # With a very high threshold (0.99), the moderate vector should not match
        results_high = manager.search(moderate, k=1, threshold=0.99)
        assert len(results_high) == 0

        # With a lower threshold (0.4), the moderate vector should match
        results_low = manager.search(moderate, k=1, threshold=0.4)
        assert len(results_low) == 1
        assert results_low[0][0] == "user-base"

    def test_search_batch(self, tmp_path):
        """search_batch returns one result list per query embedding."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        manager.load_or_create_index()

        emb_a = _make_embedding(seed=1)
        emb_b = _make_embedding(seed=2)
        manager.add(emb_a, "user-a")
        manager.add(emb_b, "user-b")

        # Search with both vectors
        queries = np.array([emb_a, emb_b])
        batch_results = manager.search_batch(queries, k=1, threshold=0.5)

        assert len(batch_results) == 2
        # Each query should find its own match
        assert batch_results[0][0][0] == "user-a"
        assert batch_results[0][0][1] > 0.99
        assert batch_results[1][0][0] == "user-b"
        assert batch_results[1][0][1] > 0.99

    # -- Remove and rebuild ------------------------------------------------

    def test_remove(self, tmp_path):
        """remove() deletes the user_map entry but leaves the vector in
        the FAISS index (IndexFlatIP does not support native deletion)."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        manager.load_or_create_index()

        emb = _make_embedding(seed=7)
        faiss_id = manager.add(emb, "user-to-remove")

        result = manager.remove(faiss_id)

        assert result is True
        assert faiss_id not in manager.user_map
        # Vector is still physically in the index
        assert manager.index.ntotal == 1

    def test_remove_nonexistent_returns_false(self, tmp_path):
        """Removing a FAISS ID not in user_map returns False."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        manager.load_or_create_index()

        result = manager.remove(999)
        assert result is False

    def test_rebuild(self, tmp_path):
        """rebuild() replaces the index with new data, discarding old
        vectors and user_map entries."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        manager.load_or_create_index()

        # Add initial data
        manager.add(_make_embedding(seed=1), "old-user-1")
        manager.add(_make_embedding(seed=2), "old-user-2")
        assert manager.index.ntotal == 2

        # Rebuild with completely new data
        new_data = [
            (_make_embedding(seed=10), "new-user-x"),
            (_make_embedding(seed=20), "new-user-y"),
            (_make_embedding(seed=30), "new-user-z"),
        ]
        manager.rebuild(new_data)

        assert manager.index.ntotal == 3
        assert len(manager.user_map) == 3
        assert manager.user_map[0] == "new-user-x"
        assert manager.user_map[1] == "new-user-y"
        assert manager.user_map[2] == "new-user-z"

    def test_rebuild_empty_creates_empty_index(self, tmp_path):
        """Rebuilding with no data creates a fresh empty index."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        manager.load_or_create_index()
        manager.add(_make_embedding(seed=1), "user-1")

        manager.rebuild([])

        assert manager.index.ntotal == 0
        assert len(manager.user_map) == 0

    # -- Save and load round-trip -----------------------------------------

    def test_save_and_load(self, tmp_path):
        """Saving and loading preserves the index contents (ntotal)."""
        path = str(tmp_path / "roundtrip.index")
        manager = FAISSManager(index_path=path)
        manager.load_or_create_index()

        # Add several vectors
        for i in range(5):
            manager.add(_make_embedding(seed=i), f"user-{i}")
        manager.save()

        # Load in a fresh manager
        manager2 = FAISSManager(index_path=path)
        manager2.load_or_create_index()

        assert manager2.index.ntotal == 5

    # -- Statistics --------------------------------------------------------

    def test_get_stats_initialized(self, tmp_path):
        """get_stats reports correct values for an initialized index."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        manager.load_or_create_index()
        manager.add(_make_embedding(seed=1), "user-1")
        manager.add(_make_embedding(seed=2), "user-2")

        stats = manager.get_stats()

        assert stats["initialized"] is True
        assert stats["total_vectors"] == 2
        assert stats["dimension"] == 512
        assert stats["index_type"] == "IndexFlatIP"
        assert stats["user_mappings"] == 2

    def test_get_stats_not_initialized(self, tmp_path):
        """get_stats reports uninitialized state when index is None."""
        manager = FAISSManager(index_path=str(tmp_path / "test.index"))
        # Do NOT load or create

        stats = manager.get_stats()

        assert stats["initialized"] is False
        assert stats["total_vectors"] == 0
        assert stats["index_type"] is None
