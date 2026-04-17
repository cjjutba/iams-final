"""
Face Quality Assessment

Evaluates image quality before face registration to reject blurry, poorly lit,
or too-small face crops. Uses Laplacian variance for blur detection and mean
pixel intensity for brightness assessment.

Quality checks:
  - Blur (Laplacian variance): rejects motion blur, out-of-focus images
  - Brightness (mean intensity): rejects under/over-exposed images
  - Face size ratio: rejects faces that are too small in the frame
  - Detection confidence: rejects low-confidence SCRFD detections
"""

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.config import settings


@dataclass
class QualityReport:
    """Result of quality assessment for a single face image."""

    blur_score: float  # Laplacian variance (higher = sharper)
    brightness: float  # Mean pixel intensity (0-255)
    face_size_ratio: float  # Face bbox area / image area
    det_score: float  # SCRFD detection confidence
    passed: bool = True
    rejection_reasons: list[str] = field(default_factory=list)


def compute_blur_score(image_bgr: np.ndarray) -> float:
    """
    Compute sharpness via Laplacian variance.

    Higher values indicate sharper images. A uniform or heavily blurred
    image produces near-zero variance.

    Args:
        image_bgr: BGR numpy array.

    Returns:
        Laplacian variance (float). Typical sharp face: >100, blurry: <50.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def compute_brightness(image_bgr: np.ndarray) -> float:
    """
    Compute mean brightness of the image.

    Args:
        image_bgr: BGR numpy array.

    Returns:
        Mean pixel intensity in grayscale (0.0–255.0).
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray))


def compute_face_size_ratio(
    bbox: tuple[int, int, int, int],
    image_shape: tuple[int, ...],
) -> float:
    """
    Compute the ratio of face bounding box area to total image area.

    Args:
        bbox: (x, y, width, height) of the detected face.
        image_shape: (height, width, channels) of the source image.

    Returns:
        Ratio in [0.0, 1.0].
    """
    _, _, bw, bh = bbox
    face_area = bw * bh
    image_area = image_shape[0] * image_shape[1]  # height × width
    if image_area == 0:
        return 0.0
    return float(face_area / image_area)


def assess_recognition_quality(
    face_crop_bgr: np.ndarray,
    min_size: int = 40,
) -> tuple[bool, float]:
    """
    Fast quality check for recognition-time face crops (~0.3ms).

    Rejects crops that are too small, too blurry, or have extreme lighting
    before they reach ArcFace. Skipping a bad frame costs nothing — the track
    simply retries on the next frame (100ms at 10fps).

    Uses a single BGR→gray conversion for both blur and brightness checks.

    Args:
        face_crop_bgr: BGR face crop extracted from the CCTV frame.
        min_size: Minimum width/height in pixels. Below this, ArcFace
                  produces unstable embeddings.

    Returns:
        (passed, blur_score) — passed is True if the crop is worth recognizing.
    """
    h, w = face_crop_bgr.shape[:2]
    if h < min_size or w < min_size:
        return False, 0.0

    # Single BGR→gray conversion for both blur and brightness
    gray = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2GRAY)

    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if blur < settings.QUALITY_BLUR_THRESHOLD:
        return False, blur

    brightness = float(np.mean(gray))
    if brightness < settings.QUALITY_BRIGHTNESS_MIN or brightness > settings.QUALITY_BRIGHTNESS_MAX:
        return False, blur

    return True, blur


def assess_quality(
    image_bgr: np.ndarray,
    det_score: float,
    bbox: tuple[int, int, int, int],
    image_shape: tuple[int, ...],
    blur_threshold_override: float | None = None,
) -> QualityReport:
    """
    Run all quality checks and return a unified report.

    Args:
        image_bgr: BGR numpy array of the image (or face crop).
        det_score: SCRFD detection confidence for this face.
        bbox: (x, y, width, height) bounding box of the detected face.
        image_shape: (height, width, channels) of the source image.

    Returns:
        QualityReport with pass/fail and individual scores.
    """
    blur = compute_blur_score(image_bgr)
    brightness = compute_brightness(image_bgr)
    size_ratio = compute_face_size_ratio(bbox, image_shape)

    reasons: list[str] = []

    if settings.QUALITY_GATE_ENABLED:
        blur_min = blur_threshold_override if blur_threshold_override is not None else settings.QUALITY_BLUR_THRESHOLD
        if blur < blur_min:
            reasons.append(f"Image too blurry (score {blur:.1f}, min {blur_min})")

        if brightness < settings.QUALITY_BRIGHTNESS_MIN:
            reasons.append(f"Image too dark (brightness {brightness:.1f}, min {settings.QUALITY_BRIGHTNESS_MIN})")

        if brightness > settings.QUALITY_BRIGHTNESS_MAX:
            reasons.append(f"Image too bright (brightness {brightness:.1f}, max {settings.QUALITY_BRIGHTNESS_MAX})")

        if size_ratio < settings.QUALITY_MIN_FACE_SIZE_RATIO:
            reasons.append(f"Face too small (ratio {size_ratio:.3f}, min {settings.QUALITY_MIN_FACE_SIZE_RATIO})")

        if det_score < settings.QUALITY_MIN_DET_SCORE:
            reasons.append(f"Low detection confidence ({det_score:.2f}, min {settings.QUALITY_MIN_DET_SCORE})")

    return QualityReport(
        blur_score=blur,
        brightness=brightness,
        face_size_ratio=size_ratio,
        det_score=det_score,
        passed=len(reasons) == 0,
        rejection_reasons=reasons,
    )
