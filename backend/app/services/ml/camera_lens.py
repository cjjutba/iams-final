"""
Per-Camera Lens Distortion for CCTV Embedding Synthesis

Closes part of the phone→CCTV cross-domain gap that ArcFace cannot bridge
on its own. The realtime CCTV pipeline sees faces through specific
camera lenses (e.g. Reolink P340 wide-angle on EB227, Reolink CX810
normal lens on EB226). Each lens introduces characteristic geometric
distortion (barrel for wide-angle, near-zero for normal) plus a
sensor-specific colour signature. The phone-side selfies a student
uploads at registration time have NONE of this — selfie cameras have
near-rectilinear lenses and warmer white balance.

This module:
  1. Loads per-camera lens parameters from ``backend/data/camera_lens.json``,
     keyed by ``Room.stream_key`` (e.g. "eb226", "eb227").
  2. Provides ``apply_lens_distortion(crop, profile)`` that takes a phone
     face crop and returns a version that has been geometrically warped
     to match what that camera's lens would produce, plus a colour shift
     to approximate its white balance.
  3. Provides ``apply_pose_perturbation(crop, severity)`` for 2D affine
     warps that simulate slight head turns the way CCTV captures them.

Output is fed back into ArcFace at registration time so the FAISS index
contains synthesized embeddings that live in the camera's native image
domain — recognition at runtime then has a much shorter distance to
travel between query and target. Empirically this should lift the
median sim of correct matches by 0.05-0.15 on the affected cameras.

The forward distortion model (undistorted → distorted) used here is
the Brown-Conrady model that OpenCV uses elsewhere:

    x' = x * (1 + k1*r² + k2*r⁴ + k3*r⁶) + 2*p1*x*y + p2*(r² + 2*x²)
    y' = y * (1 + k1*r² + k2*r⁴ + k3*r⁶) + p1*(r² + 2*y²) + 2*p2*x*y

where (x, y) are normalised image coordinates and r² = x² + y².
For typical security-camera barrel distortion, k1 < 0.

The implementation uses ``cv2.remap`` with a precomputed inverse map
(distorted output coord → undistorted input coord) so re-rendering one
crop is ~1 ms on the M5 — cheap enough to do per-angle per-camera at
registration time without slowing the upload flow.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Bundled config — lives inside the app package so it gets baked into the
# Docker image. (The repo's top-level backend/data/ directory is gitignored
# and Docker-ignored because it holds runtime state like the FAISS index.)
_LENS_CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "camera_lens.json"


@dataclass(frozen=True)
class CameraLensProfile:
    """Per-camera lens distortion + colour profile."""

    stream_key: str
    model: str
    fov_horizontal_deg: float
    sensor_megapixels: float
    k1: float
    k2: float
    k3: float
    p1: float
    p2: float
    color_temperature_shift_k: float

    @classmethod
    def from_dict(cls, stream_key: str, data: dict) -> "CameraLensProfile":
        return cls(
            stream_key=stream_key,
            model=data.get("model", "unknown"),
            fov_horizontal_deg=float(data.get("fov_horizontal_deg", 95.0)),
            sensor_megapixels=float(data.get("sensor_megapixels", 8.0)),
            k1=float(data.get("distortion_k1", -0.15)),
            k2=float(data.get("distortion_k2", 0.02)),
            k3=float(data.get("distortion_k3", -0.001)),
            p1=float(data.get("distortion_p1", 0.0)),
            p2=float(data.get("distortion_p2", 0.0)),
            color_temperature_shift_k=float(data.get("color_temperature_shift_k", 0.0)),
        )

    def is_significantly_distorted(self) -> bool:
        """True if distortion coefficients are large enough to bother applying.

        Used to short-circuit the cv2.remap call for near-rectilinear
        cameras where the warp would produce visually identical output.
        """
        return abs(self.k1) > 0.02 or abs(self.k2) > 0.005


class CameraLensRegistry:
    """Loads and caches per-camera lens profiles.

    Singleton-style: read once at first lookup, cached for the lifetime
    of the process. Reload happens by recreating the registry (currently
    only at process restart — the lens config doesn't change at runtime
    in any deployment).
    """

    _instance: "CameraLensRegistry | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "CameraLensRegistry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_once()
        return cls._instance

    def _init_once(self) -> None:
        self._profiles: dict[str, CameraLensProfile] = {}
        self._default: CameraLensProfile | None = None
        try:
            with _LENS_CONFIG_PATH.open() as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.warning(
                "Camera lens config not found at %s — synthesis will use a generic default profile",
                _LENS_CONFIG_PATH,
            )
            data = {"profiles": {}, "default": {}}
        except Exception:
            logger.exception("Failed to parse camera lens config; using generic defaults")
            data = {"profiles": {}, "default": {}}

        for key, raw in (data.get("profiles") or {}).items():
            self._profiles[key.lower()] = CameraLensProfile.from_dict(key.lower(), raw)

        default_raw = data.get("default")
        if default_raw:
            self._default = CameraLensProfile.from_dict("__default__", default_raw)
        else:
            # Hard-coded fallback so the system still works without the JSON file
            self._default = CameraLensProfile(
                stream_key="__default__",
                model="generic_fallback",
                fov_horizontal_deg=100.0,
                sensor_megapixels=8.0,
                k1=-0.20, k2=0.04, k3=-0.002,
                p1=0.0, p2=0.0,
                color_temperature_shift_k=-200.0,
            )

        logger.info(
            "CameraLensRegistry loaded %d profile(s) (default model=%s)",
            len(self._profiles),
            self._default.model if self._default else "<none>",
        )

    def get(self, stream_key: str | None) -> CameraLensProfile:
        """Look up a profile by stream_key. Falls back to the default
        profile if no per-camera entry exists. Always returns something
        usable so callers don't need a None-guard.
        """
        if stream_key:
            prof = self._profiles.get(stream_key.lower())
            if prof is not None:
                return prof
        return self._default

    def all_known_profiles(self) -> list[CameraLensProfile]:
        """Return every per-camera profile (excludes the fallback default).

        Used by the registration path to generate one synthetic embedding
        set per *known* camera, so a student gets `sim_eb226_*` AND
        `sim_eb227_*` even before they appear in either room.
        """
        return list(self._profiles.values())


# ----------------------------------------------------------------------
# Distortion application
# ----------------------------------------------------------------------


def _build_distortion_maps(
    h: int, w: int, profile: CameraLensProfile
) -> tuple[np.ndarray, np.ndarray]:
    """Compute cv2.remap maps for forward distortion of an undistorted image.

    For each output pixel (i, j) in the distorted result, computes the
    undistorted source pixel to sample from. Uses the Brown-Conrady
    radial+tangential model with normalised coordinates centred on the
    image midpoint.

    A subtle but important choice: we normalise coordinates by HALF the
    image dimension so the effective r=1 lies at the corner of the crop.
    This means k1=-0.15 produces a moderate, visible barrel effect across
    the face crop — strong enough to materially shift the ArcFace
    embedding without making the face cartoonishly warped.
    """
    cx = w / 2.0
    cy = h / 2.0
    # Indices: y_grid is rows, x_grid is cols
    y_grid, x_grid = np.indices((h, w), dtype=np.float32)
    xn = (x_grid - cx) / cx
    yn = (y_grid - cy) / cy
    r2 = xn * xn + yn * yn
    r4 = r2 * r2
    r6 = r4 * r2

    radial = 1.0 + profile.k1 * r2 + profile.k2 * r4 + profile.k3 * r6
    # Inverse mapping: where (in the undistorted source) does this distorted
    # output pixel sample from? For a pure radial model the answer is
    # "scale by 1/radial". The tangential terms add a small offset.
    safe_radial = np.where(np.abs(radial) < 1e-6, 1.0, radial)
    src_xn = xn / safe_radial - 2.0 * profile.p1 * xn * yn - profile.p2 * (r2 + 2.0 * xn * xn)
    src_yn = yn / safe_radial - profile.p1 * (r2 + 2.0 * yn * yn) - 2.0 * profile.p2 * xn * yn

    map_x = (src_xn * cx + cx).astype(np.float32)
    map_y = (src_yn * cy + cy).astype(np.float32)
    return map_x, map_y


def apply_lens_distortion(
    crop_bgr: np.ndarray, profile: CameraLensProfile
) -> np.ndarray:
    """Apply the camera's lens distortion to a face crop.

    Cheap (~1-2 ms on the M5 for a 200x200 crop). The map computation
    is a few numpy ops; the cv2.remap is one BLAS-optimised call.
    Short-circuits when the profile has near-zero distortion to avoid
    pointless work.
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return crop_bgr
    if not profile.is_significantly_distorted():
        return crop_bgr.copy()

    h, w = crop_bgr.shape[:2]
    map_x, map_y = _build_distortion_maps(h, w, profile)
    return cv2.remap(
        crop_bgr,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def apply_color_shift(crop_bgr: np.ndarray, kelvin_delta: float) -> np.ndarray:
    """Approximate a white-balance shift by tinting the BGR channels.

    Negative kelvin_delta = cooler (more blue, less red) — what most
    security cameras produce vs phone selfie cameras. The mapping from
    kelvin to channel gain is a rough linear approximation; good enough
    for the scale of shift we need (~200-400K) without pulling in a
    full colour-science library.
    """
    if abs(kelvin_delta) < 50.0 or crop_bgr is None or crop_bgr.size == 0:
        return crop_bgr if crop_bgr is None else crop_bgr.copy()

    # Linear approximation: -100K shifts blue gain up ~1.5%, red down ~1.5%
    blue_gain = 1.0 - kelvin_delta / 6500.0 * 0.10  # negative delta => blue_gain > 1
    red_gain = 1.0 + kelvin_delta / 6500.0 * 0.10   # negative delta => red_gain < 1
    out = crop_bgr.astype(np.float32, copy=True)
    out[..., 0] = np.clip(out[..., 0] * blue_gain, 0.0, 255.0)
    out[..., 2] = np.clip(out[..., 2] * red_gain, 0.0, 255.0)
    return out.astype(np.uint8)


def apply_pose_perturbation(
    crop_bgr: np.ndarray, severity: float = 0.5
) -> np.ndarray:
    """Apply a small affine warp simulating a head turn / nod.

    severity in [0, 1]: 0 = no perturbation, 1 = noticeable rotation +
    shear. Used to broaden the synthetic embedding cloud beyond the
    fixed angles a student captured during phone registration. Values
    around 0.3-0.6 hit the sweet spot — produces a measurably different
    ArcFace embedding without changing the face enough to break identity.
    """
    if severity <= 0.0 or crop_bgr is None or crop_bgr.size == 0:
        return crop_bgr if crop_bgr is None else crop_bgr.copy()

    h, w = crop_bgr.shape[:2]
    rng = np.random.default_rng()
    # Rotation: ±10° at severity=1
    angle_deg = float(rng.uniform(-10.0, 10.0)) * severity
    # Shear: small horizontal shear simulating head tilt
    shear_x = float(rng.uniform(-0.08, 0.08)) * severity
    # Scale: ±5% size change
    scale = 1.0 + float(rng.uniform(-0.05, 0.05)) * severity

    cx = w / 2.0
    cy = h / 2.0
    cos_a = np.cos(np.radians(angle_deg))
    sin_a = np.sin(np.radians(angle_deg))

    # Build affine matrix: rotation + scale + shear + translate-back
    M = np.array(
        [
            [cos_a * scale, -sin_a * scale + shear_x, 0.0],
            [sin_a * scale, cos_a * scale, 0.0],
        ],
        dtype=np.float32,
    )
    # Re-center: translate so the centre of the crop maps to itself
    M[0, 2] = cx - (M[0, 0] * cx + M[0, 1] * cy)
    M[1, 2] = cy - (M[1, 0] * cx + M[1, 1] * cy)

    return cv2.warpAffine(
        crop_bgr,
        M,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )


# Convenience accessor
camera_lens_registry = CameraLensRegistry()
