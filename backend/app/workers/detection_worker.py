# backend/app/workers/detection_worker.py
"""
Detection Worker — Standalone container process.

Consumes: stream:frames:{room_id}  (12MP JPEG snapshots from RPi)
Publishes: stream:detections:{room_id}  (bboxes + track IDs)
           stream:recognition_req  (new/unidentified track face crops)

Uses SCRFD (InsightFace) for face detection. Runs at ~3 FPS per room.
"""
import base64
import logging
import time

import cv2
import numpy as np

from app.config import settings
from app.services.ml.insightface_model import insightface_model
from app.services.stream_bus import STREAM_FRAMES, STREAM_RECOGNITION_REQ
from app.workers.base_worker import BaseWorker, run_worker

logger = logging.getLogger(__name__)


class SimpleTracker:
    """IoU + centroid tracker for assigning stable track IDs across frames."""

    def __init__(self, iou_threshold: float = 0.3, max_lost: int = 5):
        self.next_id = 1
        self.tracks: dict[int, dict] = {}  # track_id -> {bbox, lost_count, identified}
        self.iou_threshold = iou_threshold
        self.max_lost = max_lost

    def update(self, detections: list[dict]) -> list[dict]:
        """Match new detections to existing tracks. Returns detections with track_id."""
        if not self.tracks:
            # First frame — assign new IDs to all
            for det in detections:
                det["track_id"] = self.next_id
                det["is_new"] = True
                self.tracks[self.next_id] = {
                    "bbox": det["bbox"],
                    "lost_count": 0,
                    "identified": False,
                }
                self.next_id += 1
            return detections

        # Compute IoU between existing tracks and new detections
        track_ids = list(self.tracks.keys())
        track_bboxes = [self.tracks[tid]["bbox"] for tid in track_ids]
        det_bboxes = [d["bbox"] for d in detections]

        matched_dets = set()
        matched_tracks = set()

        if track_bboxes and det_bboxes:
            iou_matrix = self._compute_iou_matrix(track_bboxes, det_bboxes)

            # Greedy matching (highest IoU first)
            while True:
                if iou_matrix.size == 0:
                    break
                max_idx = np.unravel_index(iou_matrix.argmax(), iou_matrix.shape)
                max_iou = iou_matrix[max_idx]
                if max_iou < self.iou_threshold:
                    break
                t_idx, d_idx = max_idx
                tid = track_ids[t_idx]
                detections[d_idx]["track_id"] = tid
                detections[d_idx]["is_new"] = False
                self.tracks[tid]["bbox"] = detections[d_idx]["bbox"]
                self.tracks[tid]["lost_count"] = 0
                matched_dets.add(d_idx)
                matched_tracks.add(t_idx)
                iou_matrix[t_idx, :] = -1
                iou_matrix[:, d_idx] = -1

        # Unmatched detections → new tracks
        for i, det in enumerate(detections):
            if i not in matched_dets:
                det["track_id"] = self.next_id
                det["is_new"] = True
                self.tracks[self.next_id] = {
                    "bbox": det["bbox"],
                    "lost_count": 0,
                    "identified": False,
                }
                self.next_id += 1

        # Unmatched tracks → increment lost count, remove if too old
        for i, tid in enumerate(track_ids):
            if i not in matched_tracks:
                self.tracks[tid]["lost_count"] += 1
                if self.tracks[tid]["lost_count"] > self.max_lost:
                    del self.tracks[tid]

        return detections

    def mark_identified(self, track_id: int):
        if track_id in self.tracks:
            self.tracks[track_id]["identified"] = True

    def is_identified(self, track_id: int) -> bool:
        return self.tracks.get(track_id, {}).get("identified", False)

    def _compute_iou_matrix(
        self, boxes_a: list[list], boxes_b: list[list]
    ) -> np.ndarray:
        a = np.array(boxes_a, dtype=float)  # [N, 4] as [x1, y1, x2, y2]
        b = np.array(boxes_b, dtype=float)  # [M, 4]

        # Intersection
        inter_x1 = np.maximum(a[:, None, 0], b[None, :, 0])
        inter_y1 = np.maximum(a[:, None, 1], b[None, :, 1])
        inter_x2 = np.minimum(a[:, None, 2], b[None, :, 2])
        inter_y2 = np.minimum(a[:, None, 3], b[None, :, 3])
        inter_area = np.maximum(0, inter_x2 - inter_x1) * np.maximum(
            0, inter_y2 - inter_y1
        )

        # Union
        area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
        area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
        union = area_a[:, None] + area_b[None, :] - inter_area

        return inter_area / np.maximum(union, 1e-6)


class DetectionWorker(BaseWorker):
    def __init__(self):
        super().__init__(
            name="detection-worker",
            group=settings.DETECTION_GROUP,
        )
        self.model = None
        self.trackers: dict[str, SimpleTracker] = {}  # room_id -> tracker
        self.room_ids: list[str] = []

    async def setup(self):
        await super().setup()
        # Load InsightFace model (SCRFD detector only needed here,
        # but buffalo_l loads both — we only use det_model)
        logger.info(f"[{self.name}] Loading InsightFace model...")
        insightface_model.load_model()
        self.model = insightface_model
        logger.info(f"[{self.name}] Model loaded")

        # Discover active rooms from Redis or config
        # We'll dynamically add rooms as frames arrive

    async def get_streams(self) -> dict[str, str]:
        """Discover all room frame streams dynamically from Redis."""
        r = self.bus.redis if self.bus else None
        streams = {}
        if r:
            async for key in r.scan_iter(match=b"stream:frames:*"):
                key_str = key.decode() if isinstance(key, bytes) else key
                streams[key_str] = ">"
                room_id = key_str.replace("stream:frames:", "")
                if room_id not in self.room_ids:
                    self.room_ids.append(room_id)
        return streams

    async def process_message(self, stream: str, msg_id: str, data: dict):
        room_id = data.get("room_id", "unknown")
        t_start = time.time()

        # Decode JPEG frame
        frame_b64 = data.get("frame_b64", "")
        if not frame_b64:
            return

        frame_bytes = base64.b64decode(frame_b64)
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            logger.warning(f"[{self.name}] Failed to decode frame from {room_id}")
            return

        orig_h, orig_w = frame.shape[:2]

        # Downscale to 1080p for detection (keep original for cropping)
        det_frame = frame
        scale = 1.0
        if orig_w > 1920:
            scale = 1920 / orig_w
            det_h = int(orig_h * scale)
            det_frame = cv2.resize(frame, (1920, det_h))

        # Run SCRFD detection
        faces = self.model.get_faces(det_frame)

        # Build detection list with bboxes mapped to original resolution
        detections = []
        for face_info in faces:
            # DetectedFace has x, y, width, height — convert to [x1, y1, x2, y2]
            bbox = [
                face_info.x,
                face_info.y,
                face_info.x + face_info.width,
                face_info.y + face_info.height,
            ]
            confidence = face_info.confidence

            # Map back to original 12MP coordinates
            if scale != 1.0:
                orig_bbox = [
                    int(bbox[0] / scale),
                    int(bbox[1] / scale),
                    int(bbox[2] / scale),
                    int(bbox[3] / scale),
                ]
            else:
                orig_bbox = [int(b) for b in bbox]

            detections.append(
                {
                    "bbox": orig_bbox,
                    "confidence": float(confidence),
                }
            )

        # Track assignment
        tracker = self.trackers.setdefault(room_id, SimpleTracker())
        tracked_dets = tracker.update(detections)

        # Normalize bboxes to 0-1 for WebSocket output
        norm_detections = []
        recognition_requests = []

        for det in tracked_dets:
            bbox = det["bbox"]
            norm_bbox = [
                bbox[0] / orig_w,
                bbox[1] / orig_h,
                bbox[2] / orig_w,
                bbox[3] / orig_h,
            ]

            norm_det = {
                "track_id": det["track_id"],
                "bbox": norm_bbox,
                "confidence": det["confidence"],
                "is_new": det.get("is_new", False),
            }
            norm_detections.append(norm_det)

            # If new or unidentified track, crop face and request recognition
            if det.get("is_new") or not tracker.is_identified(det["track_id"]):
                # Crop face from ORIGINAL 12MP frame
                x1, y1, x2, y2 = bbox
                # Add 20% padding
                pad_w = int((x2 - x1) * 0.2)
                pad_h = int((y2 - y1) * 0.2)
                cx1 = max(0, x1 - pad_w)
                cy1 = max(0, y1 - pad_h)
                cx2 = min(orig_w, x2 + pad_w)
                cy2 = min(orig_h, y2 + pad_h)
                face_crop = frame[cy1:cy2, cx1:cx2]

                if face_crop.size > 0:
                    _, crop_jpeg = cv2.imencode(
                        ".jpg", face_crop, [cv2.IMWRITE_JPEG_QUALITY, 90]
                    )
                    crop_b64 = base64.b64encode(crop_jpeg.tobytes()).decode()

                    recognition_requests.append(
                        {
                            "room_id": room_id,
                            "track_id": det["track_id"],
                            "face_crop_b64": crop_b64,
                            "bbox": det["bbox"],
                            "confidence": det["confidence"],
                            "timestamp": data.get("timestamp", ""),
                        }
                    )

        # Publish detections
        await self.bus.publish_detections(
            room_id,
            {
                "room_id": room_id,
                "timestamp": data.get("timestamp", ""),
                "frame_width": orig_w,
                "frame_height": orig_h,
                "detections": norm_detections,
                "face_count": len(norm_detections),
            },
        )

        # Publish recognition requests (only for new/unidentified tracks)
        for req in recognition_requests:
            await self.bus.publish_recognition_request(req)

        latency_ms = (time.time() - t_start) * 1000
        if len(norm_detections) > 0:
            logger.info(
                f"[{self.name}] room={room_id} faces={len(norm_detections)} "
                f"new={len(recognition_requests)} latency={latency_ms:.0f}ms"
            )


# ── Entry point ─────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    worker = DetectionWorker()
    run_worker(worker)
