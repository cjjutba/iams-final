"""
Unit Tests for Anti-Spoofing Module

Tests LBP texture analysis, FFT frequency analysis, and
multi-image embedding variance checking.
"""

import numpy as np
import pytest

from app.services.ml.anti_spoof import (
    AntiSpoofDetector,
    SpoofResult,
    compute_lbp_score,
    compute_fft_score,
    check_embedding_variance,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_textured_face(seed: int = 42) -> np.ndarray:
    """Create a realistic-ish textured image (random noise = rich texture)."""
    rng = np.random.RandomState(seed)
    return rng.randint(0, 255, (160, 160, 3), dtype=np.uint8)


def _make_flat_face() -> np.ndarray:
    """Create a flat/uniform image simulating a printed photo."""
    return np.ones((160, 160, 3), dtype=np.uint8) * 128


def _make_embedding(seed: int) -> np.ndarray:
    """Create a deterministic L2-normalized 512-dim embedding."""
    rng = np.random.RandomState(seed)
    emb = rng.randn(512).astype(np.float32)
    return emb / np.linalg.norm(emb)


# ---------------------------------------------------------------------------
# LBP Tests
# ---------------------------------------------------------------------------

class TestLBPScore:
    def test_textured_image_high_score(self):
        """Random noise (rich texture) should produce a high LBP score."""
        img = _make_textured_face()
        score = compute_lbp_score(img)
        assert score > 0.5

    def test_flat_image_low_score(self):
        """Uniform image should produce a low LBP score."""
        img = _make_flat_face()
        score = compute_lbp_score(img)
        assert score < 0.3

    def test_score_range(self):
        """Score should be in [0, 1]."""
        for seed in [1, 2, 3]:
            score = compute_lbp_score(_make_textured_face(seed))
            assert 0.0 <= score <= 1.0

    def test_tiny_image_returns_zero(self):
        """Images too small for LBP return 0."""
        tiny = np.zeros((2, 2, 3), dtype=np.uint8)
        assert compute_lbp_score(tiny) == 0.0


# ---------------------------------------------------------------------------
# FFT Tests
# ---------------------------------------------------------------------------

class TestFFTScore:
    def test_natural_image_moderate_score(self):
        """Natural-looking image has balanced frequency distribution."""
        img = _make_textured_face()
        score = compute_fft_score(img)
        assert 0.2 < score < 1.0

    def test_flat_image_score(self):
        """Uniform image has mostly low-frequency energy."""
        img = _make_flat_face()
        score = compute_fft_score(img)
        assert 0.0 <= score <= 1.0

    def test_score_range(self):
        """Score should be in [0, 1]."""
        for seed in [10, 20, 30]:
            score = compute_fft_score(_make_textured_face(seed))
            assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Embedding Variance Tests
# ---------------------------------------------------------------------------

class TestEmbeddingVariance:
    def test_diverse_embeddings_high_variance(self):
        """Different random embeddings should have high pairwise distance."""
        embeddings = [_make_embedding(i) for i in range(5)]
        variance = check_embedding_variance(embeddings)
        # Random unit vectors in 512-d have expected cosine distance ~1.0
        assert variance > 0.5

    def test_identical_embeddings_zero_variance(self):
        """Identical embeddings (flat photo scenario) → zero variance."""
        emb = _make_embedding(42)
        embeddings = [emb.copy() for _ in range(5)]
        variance = check_embedding_variance(embeddings)
        assert variance < 0.01

    def test_near_identical_low_variance(self):
        """Very similar embeddings (simulated spoof) → low variance."""
        base = _make_embedding(42)
        rng = np.random.RandomState(99)
        embeddings = []
        for _ in range(5):
            noise = rng.randn(512).astype(np.float32) * 0.01
            v = base + noise
            v = v / np.linalg.norm(v)
            embeddings.append(v)
        variance = check_embedding_variance(embeddings)
        assert variance < 0.05

    def test_single_embedding_returns_zero(self):
        """Single embedding can't compute variance."""
        assert check_embedding_variance([_make_embedding(1)]) == 0.0

    def test_empty_returns_zero(self):
        assert check_embedding_variance([]) == 0.0


# ---------------------------------------------------------------------------
# AntiSpoofDetector Tests
# ---------------------------------------------------------------------------

class TestAntiSpoofDetector:
    def test_single_image_textured_passes(self):
        """Rich texture image passes single-image check."""
        detector = AntiSpoofDetector()
        result = detector.check_single_image(_make_textured_face())
        assert isinstance(result, SpoofResult)
        assert result.method == "single_image"
        assert "lbp_score" in result.details
        assert "fft_score" in result.details

    def test_single_image_flat_fails(self):
        """Flat/uniform image fails single-image check."""
        detector = AntiSpoofDetector()
        result = detector.check_single_image(_make_flat_face())
        assert result.is_live is False

    def test_registration_set_diverse_passes(self):
        """Diverse face crops + embeddings pass registration check."""
        detector = AntiSpoofDetector()
        crops = [_make_textured_face(seed=i) for i in range(5)]
        embeddings = [_make_embedding(i) for i in range(5)]
        result = detector.check_registration_set(crops, embeddings)
        assert result.method == "registration_set"
        assert result.details["variance_passed"] is True

    def test_registration_set_identical_embeddings_fails(self):
        """Identical embeddings (flat photo spoof) fail registration check."""
        detector = AntiSpoofDetector()
        crops = [_make_textured_face(seed=i) for i in range(5)]
        emb = _make_embedding(42)
        embeddings = [emb.copy() for _ in range(5)]
        result = detector.check_registration_set(crops, embeddings)
        assert result.details["variance_passed"] is False
        assert result.is_live is False

    def test_registration_set_reports_rejection_reasons(self):
        """Failed registration includes rejection reasons."""
        detector = AntiSpoofDetector()
        crops = [_make_flat_face() for _ in range(5)]
        emb = _make_embedding(42)
        embeddings = [emb.copy() for _ in range(5)]
        result = detector.check_registration_set(crops, embeddings)
        assert result.is_live is False
        assert "rejection_reasons" in result.details
        assert len(result.details["rejection_reasons"]) > 0

    def test_spoof_score_range(self):
        """Combined spoof_score is in [0, 1]."""
        detector = AntiSpoofDetector()
        for seed in [1, 2, 3]:
            result = detector.check_single_image(_make_textured_face(seed))
            assert 0.0 <= result.spoof_score <= 1.0
