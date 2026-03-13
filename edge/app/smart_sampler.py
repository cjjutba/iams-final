"""
Smart Sampler - IoU-based face tracking and deduplication

Sits between the face detector and the sender on the RPi to reduce
redundant transmissions:
- 50 students sitting still -> only send changed/new faces
- New student enters -> send immediately
- Student leaves -> detect within FACE_GONE_TIMEOUT seconds

Uses IoU (Intersection over Union) matching to track faces across frames
without requiring re-identification. Each tracked face accumulates the
best-confidence frame within a dedup window before sending.
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.config import logger
from app.processor import FaceData


@dataclass
class TrackedFace:
    """State for a single tracked face across frames."""

    track_id: int
    bbox: List[int]              # [x, y, w, h]
    confidence: float
    last_seen: float             # timestamp
    last_sent: float             # timestamp (0 = never sent)
    best_frame_data: Optional[FaceData] = None
    best_confidence: float = 0.0
    is_new: bool = True


class SmartSampler:
    """
    Tracks faces across frames using IoU matching and reduces redundant
    transmissions by deduplicating within a configurable time window.

    Args:
        config: Edge device Config class with Smart Sampler settings
    """

    def __init__(self, config):
        self.send_interval = config.SEND_INTERVAL
        self.dedup_window = config.DEDUP_WINDOW
        self.face_gone_timeout = config.FACE_GONE_TIMEOUT
        self.iou_threshold = config.IOU_MATCH_THRESHOLD

        self._tracks: Dict[int, TrackedFace] = {}
        self._next_track_id: int = 1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self,
        detections: List[List[int]],
        face_data_list: List[FaceData],
        current_time: Optional[float] = None,
    ) -> Tuple[List[FaceData], List[int]]:
        """
        Process a new set of detections and decide which faces to send.

        Args:
            detections: List of bounding boxes [x, y, w, h] for each
                detected face (same order as face_data_list).
            face_data_list: Corresponding processed FaceData objects.
            current_time: Override for current timestamp (for testing).

        Returns:
            (faces_to_send, gone_track_ids):
                faces_to_send  - FaceData objects that should be sent now.
                gone_track_ids - track IDs that disappeared (face gone).
        """
        now = current_time if current_time is not None else time.time()

        faces_to_send: List[FaceData] = []
        matched_track_ids: set = set()

        # --- Match each detection to an existing or new track ----------
        for bbox, face_data in zip(detections, face_data_list):
            track_id = self._match_or_create(bbox, now)
            matched_track_ids.add(track_id)
            track = self._tracks[track_id]

            # Update track state
            track.bbox = bbox
            track.confidence = face_data.confidence
            track.last_seen = now

            # Keep the best frame within the current dedup window
            if face_data.confidence > track.best_confidence:
                track.best_confidence = face_data.confidence
                track.best_frame_data = face_data

            # Decide whether to send
            if track.is_new:
                # New face: send immediately
                faces_to_send.append(face_data)
                track.last_sent = now
                track.is_new = False
                track.best_confidence = 0.0
                track.best_frame_data = None
                logger.debug(f"SmartSampler: new track {track_id}, sending immediately")

            elif (now - track.last_sent) >= self.dedup_window:
                # Dedup window expired: send the best frame accumulated
                to_send = track.best_frame_data or face_data
                faces_to_send.append(to_send)
                track.last_sent = now
                track.best_confidence = 0.0
                track.best_frame_data = None
                logger.debug(
                    f"SmartSampler: track {track_id} dedup window expired, sending"
                )

        # --- Detect gone faces -----------------------------------------
        gone_track_ids: List[int] = []
        stale_ids = [
            tid
            for tid, t in self._tracks.items()
            if tid not in matched_track_ids and (now - t.last_seen) >= self.face_gone_timeout
        ]
        for tid in stale_ids:
            gone_track_ids.append(tid)
            del self._tracks[tid]
            logger.debug(f"SmartSampler: track {tid} gone (timeout)")

        return faces_to_send, gone_track_ids

    @property
    def active_tracks(self) -> int:
        """Number of currently tracked faces."""
        return len(self._tracks)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _match_or_create(self, bbox: List[int], now: float) -> int:
        """
        Match a detection bbox to an existing track via IoU, or create a
        new track if no match exceeds the threshold.

        Args:
            bbox: [x, y, w, h] of the detection.
            now: Current timestamp.

        Returns:
            Track ID (existing or newly created).
        """
        best_iou = 0.0
        best_tid: Optional[int] = None

        for tid, track in self._tracks.items():
            iou = self._compute_iou(bbox, track.bbox)
            if iou > best_iou:
                best_iou = iou
                best_tid = tid

        if best_iou >= self.iou_threshold and best_tid is not None:
            return best_tid

        # Create new track
        new_id = self._next_track_id
        self._next_track_id += 1
        self._tracks[new_id] = TrackedFace(
            track_id=new_id,
            bbox=bbox,
            confidence=0.0,
            last_seen=now,
            last_sent=0.0,
            is_new=True,
        )
        return new_id

    @staticmethod
    def _compute_iou(box1: List[int], box2: List[int]) -> float:
        """
        Compute Intersection over Union between two [x, y, w, h] boxes.

        Args:
            box1: First bounding box [x, y, width, height].
            box2: Second bounding box [x, y, width, height].

        Returns:
            IoU value in [0.0, 1.0].
        """
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2

        # Convert to (left, top, right, bottom)
        left1, top1, right1, bottom1 = x1, y1, x1 + w1, y1 + h1
        left2, top2, right2, bottom2 = x2, y2, x2 + w2, y2 + h2

        # Intersection
        inter_left = max(left1, left2)
        inter_top = max(top1, top2)
        inter_right = min(right1, right2)
        inter_bottom = min(bottom1, bottom2)

        inter_w = max(0, inter_right - inter_left)
        inter_h = max(0, inter_bottom - inter_top)
        inter_area = inter_w * inter_h

        # Union
        area1 = w1 * h1
        area2 = w2 * h2
        union_area = area1 + area2 - inter_area

        if union_area <= 0:
            return 0.0

        return inter_area / union_area
