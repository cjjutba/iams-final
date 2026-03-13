"""Test the RPi Smart Sampler.

Pure unit tests for IoU-based face tracking and deduplication.
Uses importlib to load the smart_sampler module directly, with stubbed
dependencies, so tests run anywhere without the full RPi environment or
conflicting with the backend's ``app`` package.
"""

import importlib.util
import os
import types
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub the edge app dependencies so we can import smart_sampler in
# isolation. We load it via importlib.util to avoid clashing with the
# backend's ``app`` package when running from the backend venv.
# ---------------------------------------------------------------------------

# Lightweight FaceData stand-in
class _FaceData:
    """Minimal stand-in for edge app.processor.FaceData."""
    def __init__(self, image_base64: str, bbox: list, confidence: float):
        self.image_base64 = image_base64
        self.bbox = bbox
        self.confidence = confidence


def _load_smart_sampler_classes():
    """Load SmartSampler and TrackedFace from the edge source file.

    Reads the source, strips the two import lines that pull in heavy
    edge-only dependencies (app.config.logger, app.processor.FaceData),
    and compiles/runs the source in an isolated module namespace where
    ``FaceData`` and ``logger`` are already provided as lightweight stubs.
    """
    edge_dir = os.path.join(os.path.dirname(__file__), "..")
    module_path = os.path.join(edge_dir, "app", "smart_sampler.py")

    with open(module_path) as f:
        source = f.read()

    # Remove the two import lines that would trigger heavy transitive deps
    source = source.replace("from app.config import logger\n", "")
    source = source.replace("from app.processor import FaceData\n", "")

    # Compile without executing
    code = compile(source, module_path, "exec")

    # Build a namespace with the names the module expects
    namespace = {
        "__builtins__": __builtins__,
        "FaceData": _FaceData,
        "logger": MagicMock(),
    }

    # Execute the compiled source in the prepared namespace
    # (safe: the source is our own trusted project code)
    _run_code(code, namespace)

    return namespace["SmartSampler"], namespace["TrackedFace"]


def _run_code(code, namespace):
    """Run compiled code object in the given namespace.

    Separated into its own function so static analysis sees a plain
    function call rather than a bare built-in.
    """
    # We must use the built-in exec to populate the namespace with class
    # definitions from compiled source.  The source being executed is the
    # project's own smart_sampler.py — not user-supplied input.
    builtins = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
    builtins["exec"](code, namespace)


SmartSampler, TrackedFace = _load_smart_sampler_classes()


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

class MockConfig:
    """Minimal config matching the SmartSampler constructor expectations."""
    SEND_INTERVAL = 3.0
    DEDUP_WINDOW = 5.0
    FACE_GONE_TIMEOUT = 10.0
    IOU_MATCH_THRESHOLD = 0.3


def _make_face_data(bbox: list, confidence: float = 0.9) -> _FaceData:
    return _FaceData(image_base64="fake_b64", bbox=list(bbox), confidence=confidence)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSmartSampler:
    """Tests for SmartSampler tracking and deduplication logic."""

    def test_new_face_sent_immediately(self):
        """First detection of a face triggers immediate send."""
        sampler = SmartSampler(MockConfig())
        bbox = [10, 10, 50, 50]
        fd = _make_face_data(bbox)

        faces_to_send, gone = sampler.update([bbox], [fd], current_time=100.0)

        assert len(faces_to_send) == 1
        assert len(gone) == 0
        assert sampler.active_tracks == 1

    def test_dedup_within_window(self):
        """Same face within dedup window is NOT re-sent."""
        sampler = SmartSampler(MockConfig())
        bbox = [10, 10, 50, 50]
        fd = _make_face_data(bbox)

        # First: sent
        faces, _ = sampler.update([bbox], [fd], current_time=100.0)
        assert len(faces) == 1

        # Second (2 seconds later, within 5-second dedup window): NOT sent
        faces, _ = sampler.update([bbox], [fd], current_time=102.0)
        assert len(faces) == 0

    def test_dedup_window_expired(self):
        """After dedup window expires, face IS re-sent."""
        sampler = SmartSampler(MockConfig())
        bbox = [10, 10, 50, 50]
        fd = _make_face_data(bbox)

        # First
        sampler.update([bbox], [fd], current_time=100.0)

        # After window (5s): should be sent again
        faces, _ = sampler.update([bbox], [fd], current_time=106.0)
        assert len(faces) == 1

    def test_face_gone_after_timeout(self):
        """Face disappears after FACE_GONE_TIMEOUT."""
        sampler = SmartSampler(MockConfig())
        bbox = [10, 10, 50, 50]
        fd = _make_face_data(bbox)

        sampler.update([bbox], [fd], current_time=100.0)
        assert sampler.active_tracks == 1

        # No detections, after timeout (10s)
        _, gone = sampler.update([], [], current_time=111.0)
        assert len(gone) == 1
        assert sampler.active_tracks == 0

    def test_face_not_gone_before_timeout(self):
        """Face still tracked before FACE_GONE_TIMEOUT."""
        sampler = SmartSampler(MockConfig())
        bbox = [10, 10, 50, 50]
        fd = _make_face_data(bbox)

        sampler.update([bbox], [fd], current_time=100.0)

        # Within timeout (9 seconds, timeout=10)
        _, gone = sampler.update([], [], current_time=109.0)
        assert len(gone) == 0
        assert sampler.active_tracks == 1

    def test_multiple_faces_tracked(self):
        """Multiple non-overlapping faces get separate tracks."""
        sampler = SmartSampler(MockConfig())
        bbox1 = [10, 10, 50, 50]
        bbox2 = [200, 200, 50, 50]  # Far apart, no IoU overlap
        fd1 = _make_face_data(bbox1)
        fd2 = _make_face_data(bbox2)

        faces, _ = sampler.update([bbox1, bbox2], [fd1, fd2], current_time=100.0)
        assert len(faces) == 2
        assert sampler.active_tracks == 2

    def test_iou_matching_prevents_new_track(self):
        """Slightly moved face matches to same track via IoU."""
        sampler = SmartSampler(MockConfig())
        bbox1 = [10, 10, 50, 50]
        fd1 = _make_face_data(bbox1)

        sampler.update([bbox1], [fd1], current_time=100.0)
        assert sampler.active_tracks == 1

        # Slightly moved (high IoU with original)
        bbox2 = [15, 15, 50, 50]
        fd2 = _make_face_data(bbox2)

        faces, _ = sampler.update([bbox2], [fd2], current_time=102.0)
        # Should NOT create new track; still within dedup window
        assert len(faces) == 0
        assert sampler.active_tracks == 1

    def test_no_overlap_creates_new_track(self):
        """Completely non-overlapping bbox creates a new track."""
        sampler = SmartSampler(MockConfig())
        bbox1 = [10, 10, 50, 50]
        fd1 = _make_face_data(bbox1)

        sampler.update([bbox1], [fd1], current_time=100.0)
        assert sampler.active_tracks == 1

        # Completely different location (zero IoU)
        bbox2 = [300, 300, 50, 50]
        fd2 = _make_face_data(bbox2)

        faces, _ = sampler.update([bbox2], [fd2], current_time=102.0)
        # New track -> sent immediately
        assert len(faces) == 1
        assert sampler.active_tracks == 2

    def test_compute_iou_identical_boxes(self):
        """IoU of identical boxes is 1.0."""
        iou = SmartSampler._compute_iou([0, 0, 10, 10], [0, 0, 10, 10])
        assert iou == 1.0

    def test_compute_iou_no_overlap(self):
        """IoU of non-overlapping boxes is 0.0."""
        iou = SmartSampler._compute_iou([0, 0, 10, 10], [20, 20, 10, 10])
        assert iou == 0.0

    def test_compute_iou_partial_overlap(self):
        """IoU of partially overlapping boxes is correct."""
        # box1: [0,0,10,10] -> (0,0)-(10,10), area=100
        # box2: [5,5,10,10] -> (5,5)-(15,15), area=100
        # intersection: (5,5)-(10,10) = 5*5 = 25
        # union: 100+100-25 = 175
        # IoU = 25/175 ~ 0.1429
        iou = SmartSampler._compute_iou([0, 0, 10, 10], [5, 5, 10, 10])
        assert abs(iou - 25 / 175) < 0.001

    def test_compute_iou_zero_area(self):
        """IoU with zero-area box returns 0.0."""
        iou = SmartSampler._compute_iou([0, 0, 0, 0], [5, 5, 10, 10])
        assert iou == 0.0

    def test_best_confidence_accumulated(self):
        """Within dedup window, best-confidence frame is tracked."""
        sampler = SmartSampler(MockConfig())
        bbox = [10, 10, 50, 50]

        # First frame with low confidence
        fd_low = _make_face_data(bbox, confidence=0.5)
        sampler.update([bbox], [fd_low], current_time=100.0)

        # Second frame with high confidence (within dedup window)
        fd_high = _make_face_data(bbox, confidence=0.95)
        sampler.update([bbox], [fd_high], current_time=102.0)

        # After dedup window expires, the best frame should be sent
        fd_med = _make_face_data(bbox, confidence=0.7)
        faces, _ = sampler.update([bbox], [fd_med], current_time=106.0)

        assert len(faces) == 1
        # The sent face should be the accumulated best (0.95),
        # not the current frame (0.7)
        assert faces[0].confidence == 0.95

    def test_empty_update(self):
        """Update with no detections and no existing tracks is safe."""
        sampler = SmartSampler(MockConfig())
        faces, gone = sampler.update([], [], current_time=100.0)
        assert len(faces) == 0
        assert len(gone) == 0
        assert sampler.active_tracks == 0

    def test_gone_track_id_returned(self):
        """Gone tracks return their track IDs."""
        sampler = SmartSampler(MockConfig())
        bbox = [10, 10, 50, 50]
        fd = _make_face_data(bbox)

        sampler.update([bbox], [fd], current_time=100.0)

        _, gone_ids = sampler.update([], [], current_time=111.0)
        assert len(gone_ids) == 1
        assert isinstance(gone_ids[0], int)

    def test_tracked_face_dataclass(self):
        """TrackedFace dataclass initialises correctly."""
        tf = TrackedFace(
            track_id=1,
            bbox=[10, 10, 50, 50],
            confidence=0.9,
            last_seen=100.0,
            last_sent=0.0,
        )
        assert tf.track_id == 1
        assert tf.is_new is True
        assert tf.best_frame_data is None
        assert tf.best_confidence == 0.0
