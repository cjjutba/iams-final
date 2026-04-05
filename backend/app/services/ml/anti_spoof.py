"""
Anti-Spoofing / Liveness Detection

Detects presentation attacks (printed photos, screen replays) using:
1. LBP texture analysis — printed/screen faces have different texture distributions
2. Frequency domain (FFT) — screens show moiré, prints show halftone patterns
3. Multi-image consistency — real faces at different angles produce moderate
   embedding cosine distances; flat photos produce nearly identical embeddings
"""

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.config import settings


@dataclass
class SpoofResult:
    """Result of an anti-spoofing check."""

    is_live: bool
    spoof_score: float  # 0.0 = likely spoof, 1.0 = likely live
    method: str
    details: dict = field(default_factory=dict)


def compute_lbp_score(face_bgr: np.ndarray) -> float:
    """Compute Local Binary Pattern texture uniformity score.

    Real skin has rich, varied micro-texture. Printed photos and screens
    tend to produce more uniform LBP histograms due to loss of fine detail.

    Args:
        face_bgr: Face crop in BGR format

    Returns:
        Score in [0, 1]. Higher = more texture variety = more likely real.
    """
    gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    if h < 3 or w < 3:
        return 0.0

    # Simple LBP: compare each pixel to its 8 neighbors
    lbp = np.zeros_like(gray, dtype=np.uint8)
    for dy, dx, bit in [
        (-1, -1, 0),
        (-1, 0, 1),
        (-1, 1, 2),
        (0, 1, 3),
        (1, 1, 4),
        (1, 0, 5),
        (1, -1, 6),
        (0, -1, 7),
    ]:
        shifted = np.roll(np.roll(gray, dy, axis=0), dx, axis=1)
        lbp |= (shifted >= gray).astype(np.uint8) << bit

    # Crop border pixels affected by roll wrapping
    lbp = lbp[1:-1, 1:-1]

    # Compute histogram and normalize
    hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256))
    hist = hist.astype(np.float64)
    hist /= hist.sum() + 1e-8

    # Entropy as texture variety measure (max entropy = log2(256) ≈ 8)
    entropy = -np.sum(hist * np.log2(hist + 1e-10))
    # Normalize to [0, 1] range (empirical: real faces ~5-7, spoofs ~3-5)
    score = min(entropy / 8.0, 1.0)
    return float(score)


def compute_fft_score(face_bgr: np.ndarray) -> float:
    """Compute frequency domain score using FFT.

    Real faces have a natural falloff of high-frequency energy. Screens
    produce moiré patterns (periodic high-freq spikes) and prints show
    halftone patterns.

    Args:
        face_bgr: Face crop in BGR format

    Returns:
        Score in [0, 1]. Higher = more natural frequency distribution = likely real.
    """
    gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
    gray = gray.astype(np.float32)

    # 2D FFT
    f_transform = np.fft.fft2(gray)
    f_shifted = np.fft.fftshift(f_transform)
    magnitude = np.abs(f_shifted)

    # Avoid log(0)
    magnitude = np.log1p(magnitude)

    h, w = magnitude.shape
    cy, cx = h // 2, w // 2

    # Compute energy in low-freq vs high-freq bands
    # Low freq: center 25% of spectrum
    r_low = min(h, w) // 4
    y, x = np.ogrid[:h, :w]
    low_mask = ((y - cy) ** 2 + (x - cx) ** 2) <= r_low**2

    total_energy = magnitude.sum() + 1e-8
    low_energy = magnitude[low_mask].sum()
    high_energy = total_energy - low_energy

    # Ratio of high-freq to total (real faces: moderate, spoofs: abnormal)
    ratio = high_energy / total_energy

    # Real faces typically have ratio in [0.3, 0.7]
    # Too high = screen moiré, too low = blurred print
    # Map to score: peak at 0.5, decay towards 0 and 1
    score = 1.0 - abs(ratio - 0.5) * 2.0
    return float(max(0.0, min(1.0, score)))


def check_embedding_variance(embeddings: list[np.ndarray]) -> float:
    """Check variance of embeddings across registration angles.

    Real faces at 5 different angles produce moderate pairwise cosine
    distances (0.15-0.4). A flat photo produces nearly identical embeddings
    regardless of the "angle" claimed (<0.1 pairwise distance).

    Args:
        embeddings: List of L2-normalized 512-dim embeddings

    Returns:
        Mean pairwise cosine distance. Higher = more variety = likely real.
    """
    if len(embeddings) < 2:
        return 0.0

    # Compute all pairwise cosine distances (1 - cosine_similarity)
    distances = []
    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            sim = float(np.dot(embeddings[i], embeddings[j]))
            distances.append(1.0 - sim)

    return float(np.mean(distances))


class AntiSpoofDetector:
    """Anti-spoofing detector combining multiple methods."""

    def check_single_image(self, face_crop_bgr: np.ndarray) -> SpoofResult:
        """Check a single face crop for spoofing indicators.

        Uses LBP texture and FFT frequency analysis.

        Args:
            face_crop_bgr: Face crop in BGR format

        Returns:
            SpoofResult with combined score
        """
        lbp_score = compute_lbp_score(face_crop_bgr)
        fft_score = compute_fft_score(face_crop_bgr)

        # Weighted combination
        combined = 0.6 * lbp_score + 0.4 * fft_score

        is_live = lbp_score >= settings.ANTISPOOF_LBP_THRESHOLD and fft_score >= settings.ANTISPOOF_FFT_THRESHOLD

        return SpoofResult(
            is_live=is_live,
            spoof_score=combined,
            method="single_image",
            details={
                "lbp_score": round(lbp_score, 4),
                "fft_score": round(fft_score, 4),
            },
        )

    def check_registration_set(
        self,
        face_crops: list[np.ndarray],
        embeddings: list[np.ndarray],
    ) -> SpoofResult:
        """Check a set of registration images for spoofing.

        Combines per-image checks with multi-image embedding variance.

        Args:
            face_crops: List of face crops in BGR format
            embeddings: List of L2-normalized 512-dim embeddings

        Returns:
            SpoofResult with combined assessment
        """
        # Per-image checks (majority must pass — single noisy frame shouldn't reject)
        image_scores = [self.check_single_image(crop) for crop in face_crops]
        passed_count = sum(1 for s in image_scores if s.is_live)
        majority_passed = passed_count > len(image_scores) / 2 if image_scores else True
        avg_image_score = np.mean([s.spoof_score for s in image_scores]) if image_scores else 1.0

        # Multi-image variance check
        variance = check_embedding_variance(embeddings)
        variance_passed = variance >= settings.ANTISPOOF_EMBEDDING_VARIANCE_MIN

        # Combined decision: majority of images pass + embedding variance is sufficient
        is_live = variance_passed and majority_passed
        combined_score = 0.5 * float(avg_image_score) + 0.5 * min(variance / 0.3, 1.0)

        details = {
            "avg_image_score": round(float(avg_image_score), 4),
            "embedding_variance": round(variance, 4),
            "variance_passed": variance_passed,
            "per_image": [{"lbp": s.details["lbp_score"], "fft": s.details["fft_score"]} for s in image_scores],
        }

        if not is_live:
            reasons = []
            if not variance_passed:
                reasons.append(
                    f"embedding variance too low ({variance:.3f} < {settings.ANTISPOOF_EMBEDDING_VARIANCE_MIN})"
                )
            if not majority_passed:
                failed_indices = [i for i, s in enumerate(image_scores) if not s.is_live]
                reasons.append(
                    f"majority of images ({len(failed_indices)}/{len(image_scores)}) failed texture/frequency check"
                )
            details["rejection_reasons"] = reasons

        return SpoofResult(
            is_live=is_live,
            spoof_score=float(combined_score),
            method="registration_set",
            details=details,
        )


# Global instance
anti_spoof_detector = AntiSpoofDetector()
