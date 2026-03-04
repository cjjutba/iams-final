"""Tests for face quality assessment module."""

import numpy as np
import pytest
from app.services.ml.face_quality import (
    QualityReport,
    compute_blur_score,
    compute_brightness,
    compute_face_size_ratio,
    assess_quality,
)


class TestComputeBlurScore:
    """Tests for Laplacian-variance blur detection."""

    def test_sharp_image_high_score(self):
        """Random noise has high Laplacian variance (sharp edges)."""
        rng = np.random.RandomState(42)
        sharp = rng.randint(0, 255, (160, 160, 3), dtype=np.uint8)
        score = compute_blur_score(sharp)
        assert score > 50

    def test_blurry_image_low_score(self):
        """Uniform image has near-zero Laplacian variance."""
        blurry = np.ones((160, 160, 3), dtype=np.uint8) * 128
        score = compute_blur_score(blurry)
        assert score < 10

    def test_gradient_image_moderate_score(self):
        """Smooth gradient has moderate variance."""
        gradient = np.zeros((160, 160, 3), dtype=np.uint8)
        gradient[:, :, 0] = np.tile(np.linspace(0, 255, 160, dtype=np.uint8), (160, 1))
        score = compute_blur_score(gradient)
        assert 0 < score < 200

    def test_returns_float(self):
        img = np.zeros((160, 160, 3), dtype=np.uint8)
        assert isinstance(compute_blur_score(img), float)


class TestComputeBrightness:
    """Tests for mean-brightness calculation."""

    def test_black_image_dark(self):
        dark = np.zeros((160, 160, 3), dtype=np.uint8)
        assert compute_brightness(dark) < 1.0

    def test_white_image_bright(self):
        bright = np.ones((160, 160, 3), dtype=np.uint8) * 255
        assert compute_brightness(bright) > 250

    def test_mid_gray(self):
        mid = np.ones((160, 160, 3), dtype=np.uint8) * 128
        brightness = compute_brightness(mid)
        assert 100 < brightness < 160

    def test_returns_float(self):
        img = np.zeros((160, 160, 3), dtype=np.uint8)
        assert isinstance(compute_brightness(img), float)


class TestComputeFaceSizeRatio:
    """Tests for face-to-image area ratio."""

    def test_full_image_face(self):
        ratio = compute_face_size_ratio(
            bbox=(0, 0, 160, 160), image_shape=(160, 160, 3)
        )
        assert ratio == pytest.approx(1.0, abs=0.01)

    def test_quarter_image_face(self):
        ratio = compute_face_size_ratio(
            bbox=(0, 0, 80, 80), image_shape=(160, 160, 3)
        )
        assert ratio == pytest.approx(0.25, abs=0.01)

    def test_small_face(self):
        ratio = compute_face_size_ratio(
            bbox=(0, 0, 20, 20), image_shape=(640, 640, 3)
        )
        assert ratio < 0.01

    def test_returns_float(self):
        assert isinstance(
            compute_face_size_ratio((0, 0, 100, 100), (200, 200, 3)), float
        )


class TestAssessQuality:
    """Tests for the unified quality assessment."""

    def _make_good_image(self):
        """Create an image that should pass quality checks."""
        rng = np.random.RandomState(42)
        img = rng.randint(60, 200, (320, 320, 3), dtype=np.uint8)
        return img

    def _make_blurry_image(self):
        """Create a uniform (blurry) image."""
        return np.ones((320, 320, 3), dtype=np.uint8) * 128

    def _make_dark_image(self):
        """Create a very dark image with some texture."""
        rng = np.random.RandomState(42)
        return rng.randint(0, 20, (320, 320, 3), dtype=np.uint8)

    def test_good_image_passes(self):
        img = self._make_good_image()
        report = assess_quality(
            image_bgr=img,
            det_score=0.9,
            bbox=(50, 50, 200, 200),
            image_shape=(320, 320, 3),
        )
        assert isinstance(report, QualityReport)
        assert report.passed is True
        assert len(report.rejection_reasons) == 0

    def test_blurry_image_fails(self):
        img = self._make_blurry_image()
        report = assess_quality(
            image_bgr=img,
            det_score=0.9,
            bbox=(50, 50, 200, 200),
            image_shape=(320, 320, 3),
        )
        assert report.passed is False
        assert any("blur" in r.lower() for r in report.rejection_reasons)

    def test_dark_image_fails(self):
        img = self._make_dark_image()
        report = assess_quality(
            image_bgr=img,
            det_score=0.9,
            bbox=(50, 50, 200, 200),
            image_shape=(320, 320, 3),
        )
        assert report.passed is False
        assert any("bright" in r.lower() or "dark" in r.lower() for r in report.rejection_reasons)

    def test_low_det_score_fails(self):
        img = self._make_good_image()
        report = assess_quality(
            image_bgr=img,
            det_score=0.3,
            bbox=(50, 50, 200, 200),
            image_shape=(320, 320, 3),
        )
        assert report.passed is False
        assert any("detection" in r.lower() or "confidence" in r.lower() for r in report.rejection_reasons)

    def test_small_face_fails(self):
        img = self._make_good_image()
        report = assess_quality(
            image_bgr=img,
            det_score=0.9,
            bbox=(0, 0, 10, 10),
            image_shape=(320, 320, 3),
        )
        assert report.passed is False
        assert any("size" in r.lower() or "small" in r.lower() for r in report.rejection_reasons)

    def test_bright_image_fails(self):
        bright = np.ones((320, 320, 3), dtype=np.uint8) * 250
        # Add some noise so it doesn't fail blur too
        rng = np.random.RandomState(42)
        bright = bright + rng.randint(-5, 5, bright.shape).astype(np.uint8)
        report = assess_quality(
            image_bgr=bright,
            det_score=0.9,
            bbox=(50, 50, 200, 200),
            image_shape=(320, 320, 3),
        )
        assert report.passed is False
        assert any("bright" in r.lower() for r in report.rejection_reasons)

    def test_report_has_all_scores(self):
        img = self._make_good_image()
        report = assess_quality(
            image_bgr=img,
            det_score=0.85,
            bbox=(50, 50, 200, 200),
            image_shape=(320, 320, 3),
        )
        assert isinstance(report.blur_score, float)
        assert isinstance(report.brightness, float)
        assert isinstance(report.face_size_ratio, float)
        assert isinstance(report.det_score, float)
        assert report.det_score == pytest.approx(0.85)
