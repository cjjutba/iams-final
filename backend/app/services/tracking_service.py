"""
DeepSORT Tracking Service

Implements continuous tracking of detected faces across video frames using DeepSORT algorithm.
Links face recognition results to persistent track IDs for presence monitoring.

Key Concepts:
- Track: A persistent identity for a detected face across frames
- Track ID: Unique identifier for each track (persists across frames)
- Track Lifecycle: Creation → Update (association with detections) → Deletion (after max_age)
- Association: Linking new detections to existing tracks using IoU and appearance features

Architecture:
- DeepSORT handles the core tracking algorithm (Hungarian matching, Kalman filtering)
- This service manages track-to-user mappings and integrates with face recognition
- Tracks are associated with recognized users (user_id) for presence logging
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np

from app.config import settings, logger


@dataclass
class Detection:
    """
    Face detection with bounding box and optional identity

    Attributes:
        bbox: Bounding box [x1, y1, x2, y2] in pixel coordinates
        confidence: Detection confidence (0-1)
        user_id: Optional recognized user ID (from face recognition)
        recognition_confidence: Optional recognition confidence (0-1)
        frame_id: Frame number or timestamp
    """
    bbox: List[float]  # [x1, y1, x2, y2]
    confidence: float
    user_id: Optional[str] = None
    recognition_confidence: Optional[float] = None
    frame_id: Optional[int] = None

    def to_ltwh(self) -> List[float]:
        """Convert bbox from [x1,y1,x2,y2] to [left,top,width,height]"""
        x1, y1, x2, y2 = self.bbox
        return [x1, y1, x2 - x1, y2 - y1]

    def to_tlbr(self) -> List[float]:
        """Convert bbox to [top,left,bottom,right]"""
        x1, y1, x2, y2 = self.bbox
        return [y1, x1, y2, x2]


@dataclass
class Track:
    """
    Persistent track representing a person across frames

    Attributes:
        track_id: Unique track identifier (from DeepSORT)
        user_id: Associated user ID (None if unknown)
        recognition_confidence: Best recognition confidence for this track
        first_seen: Timestamp when track was first created
        last_seen: Timestamp when track was last updated
        detection_count: Number of times this track was detected
        bbox: Current bounding box [x1, y1, x2, y2]
        is_confirmed: Whether track is confirmed (passed n_init threshold)
    """
    track_id: int
    user_id: Optional[str] = None
    recognition_confidence: Optional[float] = None
    first_seen: datetime = None
    last_seen: datetime = None
    detection_count: int = 0
    bbox: Optional[List[float]] = None
    is_confirmed: bool = False

    def __post_init__(self):
        if self.first_seen is None:
            self.first_seen = datetime.now()
        if self.last_seen is None:
            self.last_seen = datetime.now()


class TrackingService:
    """
    Service for continuous face tracking using DeepSORT-like algorithm

    This implementation uses a simplified tracking approach suitable for classroom
    attendance monitoring where:
    - People are relatively stationary (seated)
    - Tracking is across discrete scan intervals (60s), not continuous video
    - Identity persistence is more important than real-time tracking accuracy

    Features:
    - Track lifecycle management (creation, update, deletion)
    - Track-to-user association (linking recognized faces to tracks)
    - Track confirmation (require multiple detections before confirming)
    - Track aging (delete tracks not seen for max_age seconds)
    - Session-based tracking (tracks are session-specific)

    Note: Since we're processing images at 60-second intervals (not continuous video),
    this uses a simplified tracking approach based on:
    - Spatial proximity (IoU between bounding boxes)
    - Identity consistency (same user_id detected in similar location)
    - Temporal persistence (tracks expire after 3 missed scans = 180 seconds)
    """

    def __init__(
        self,
        max_age: int = 180,  # 180 seconds = 3 scans at 60s interval
        min_hits: int = 1,  # Minimum detections to confirm track (1 for single-image scans)
        iou_threshold: float = 0.3,  # IoU threshold for matching detections to tracks
    ):
        """
        Initialize tracking service

        Args:
            max_age: Maximum seconds a track can exist without detection before deletion
            min_hits: Minimum number of detections to confirm track
            iou_threshold: Minimum IoU for associating detection to track
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold

        # Active tracks by session
        # Key: session_id (schedule_id)
        # Value: Dict[track_id, Track]
        self.session_tracks: Dict[str, Dict[int, Track]] = {}

        # Track ID counter (global across all sessions)
        self.next_track_id = 1

        logger.info(
            f"TrackingService initialized (max_age={max_age}s, "
            f"min_hits={min_hits}, iou_threshold={iou_threshold})"
        )

    def start_session(self, session_id: str):
        """
        Start tracking session

        Creates a new tracking context for a schedule/room session.
        All tracks are isolated per session.

        Args:
            session_id: Session identifier (typically schedule_id)
        """
        if session_id in self.session_tracks:
            logger.warning(f"Tracking session already exists: {session_id}")
            return

        self.session_tracks[session_id] = {}
        logger.info(f"Started tracking session: {session_id}")

    def end_session(self, session_id: str):
        """
        End tracking session

        Removes all tracks for the session.

        Args:
            session_id: Session identifier
        """
        if session_id in self.session_tracks:
            track_count = len(self.session_tracks[session_id])
            del self.session_tracks[session_id]
            logger.info(f"Ended tracking session: {session_id} ({track_count} tracks)")
        else:
            logger.warning(f"No active tracking session: {session_id}")

    def update(
        self,
        session_id: str,
        detections: List[Detection]
    ) -> List[Track]:
        """
        Update tracks with new detections

        This is the core tracking method called for each scan cycle:
        1. Associate new detections with existing tracks
        2. Update matched tracks
        3. Create new tracks for unmatched detections
        4. Delete old tracks (age > max_age)

        Args:
            session_id: Session identifier
            detections: List of face detections from current scan

        Returns:
            List of updated/created tracks
        """
        if session_id not in self.session_tracks:
            logger.warning(f"Session not started, auto-creating: {session_id}")
            self.start_session(session_id)

        tracks = self.session_tracks[session_id]
        current_time = datetime.now()

        # Step 1: Remove stale tracks (not seen for > max_age seconds)
        stale_track_ids = []
        for track_id, track in tracks.items():
            age_seconds = (current_time - track.last_seen).total_seconds()
            if age_seconds > self.max_age:
                stale_track_ids.append(track_id)
                logger.debug(
                    f"Removing stale track {track_id} "
                    f"(age: {age_seconds:.1f}s, user: {track.user_id})"
                )

        for track_id in stale_track_ids:
            del tracks[track_id]

        # Step 2: Associate detections with tracks
        matched_tracks, unmatched_detections = self._associate_detections_to_tracks(
            tracks,
            detections
        )

        # Step 3: Update matched tracks
        updated_tracks = []
        for track_id, detection in matched_tracks:
            track = tracks[track_id]
            self._update_track(track, detection, current_time)
            updated_tracks.append(track)

        # Step 4: Create new tracks for unmatched detections
        for detection in unmatched_detections:
            track = self._create_track(detection, current_time)
            tracks[track.track_id] = track
            updated_tracks.append(track)

        logger.debug(
            f"Session {session_id}: {len(updated_tracks)} active tracks "
            f"({len(matched_tracks)} matched, {len(unmatched_detections)} new, "
            f"{len(stale_track_ids)} removed)"
        )

        return updated_tracks

    def _associate_detections_to_tracks(
        self,
        tracks: Dict[int, Track],
        detections: List[Detection]
    ) -> Tuple[List[Tuple[int, Detection]], List[Detection]]:
        """
        Associate detections with existing tracks using Hungarian matching

        Matching strategy:
        1. Compute cost matrix: IoU + identity consistency
        2. Use greedy matching (simple approach for sparse detections)
        3. Match if cost below threshold

        Args:
            tracks: Active tracks
            detections: New detections

        Returns:
            Tuple of (matched pairs, unmatched detections)
        """
        if not tracks or not detections:
            return [], detections

        # Build cost matrix
        track_list = list(tracks.values())
        cost_matrix = np.zeros((len(track_list), len(detections)))

        for i, track in enumerate(track_list):
            for j, detection in enumerate(detections):
                # Cost = 1 - IoU (lower is better)
                iou = self._compute_iou(track.bbox, detection.bbox)
                cost = 1.0 - iou

                # Bonus for identity consistency
                if track.user_id and detection.user_id:
                    if track.user_id == detection.user_id:
                        cost *= 0.5  # Strong preference for same user_id
                    else:
                        cost *= 2.0  # Penalize different user_id

                cost_matrix[i, j] = cost

        # Simple greedy matching (works well for sparse detections)
        matched_tracks = []
        unmatched_detections = list(range(len(detections)))
        matched_track_indices = set()

        # Find best match for each detection
        for j in range(len(detections)):
            best_track_idx = None
            best_cost = float('inf')

            for i in range(len(track_list)):
                if i in matched_track_indices:
                    continue

                cost = cost_matrix[i, j]
                iou = 1.0 - cost if cost < 1.0 else 0.0

                # Match if IoU above threshold
                if iou >= self.iou_threshold and cost < best_cost:
                    best_cost = cost
                    best_track_idx = i

            if best_track_idx is not None:
                track_id = track_list[best_track_idx].track_id
                matched_tracks.append((track_id, detections[j]))
                matched_track_indices.add(best_track_idx)
                unmatched_detections.remove(j)

        unmatched_detections = [detections[i] for i in unmatched_detections]

        return matched_tracks, unmatched_detections

    def _compute_iou(
        self,
        bbox1: Optional[List[float]],
        bbox2: List[float]
    ) -> float:
        """
        Compute Intersection over Union (IoU) between two bounding boxes

        Args:
            bbox1: Bounding box [x1, y1, x2, y2] or None
            bbox2: Bounding box [x1, y1, x2, y2]

        Returns:
            IoU score (0-1)
        """
        if bbox1 is None:
            return 0.0

        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2

        # Compute intersection
        xi1 = max(x1_1, x1_2)
        yi1 = max(y1_1, y1_2)
        xi2 = min(x2_1, x2_2)
        yi2 = min(y2_1, y2_2)

        intersection_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)

        # Compute union
        box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
        box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
        union_area = box1_area + box2_area - intersection_area

        if union_area == 0:
            return 0.0

        return intersection_area / union_area

    def _create_track(self, detection: Detection, current_time: datetime) -> Track:
        """
        Create new track from detection

        Args:
            detection: Face detection
            current_time: Current timestamp

        Returns:
            New Track object
        """
        track = Track(
            track_id=self.next_track_id,
            user_id=detection.user_id,
            recognition_confidence=detection.recognition_confidence,
            first_seen=current_time,
            last_seen=current_time,
            detection_count=1,
            bbox=detection.bbox,
            is_confirmed=(self.min_hits <= 1)  # Confirm immediately if min_hits=1
        )

        self.next_track_id += 1

        conf_str = f"{track.recognition_confidence:.3f}" if track.recognition_confidence else "N/A"
        logger.debug(
            f"Created track {track.track_id} "
            f"(user: {track.user_id}, conf: {conf_str})"
        )

        return track

    def _update_track(
        self,
        track: Track,
        detection: Detection,
        current_time: datetime
    ):
        """
        Update existing track with new detection

        Args:
            track: Track to update
            detection: New detection
            current_time: Current timestamp
        """
        # Update timestamps
        track.last_seen = current_time
        track.detection_count += 1

        # Update bbox
        track.bbox = detection.bbox

        # Update user_id if detected with higher confidence
        if detection.user_id:
            if track.user_id is None:
                track.user_id = detection.user_id
                track.recognition_confidence = detection.recognition_confidence
                logger.debug(f"Track {track.track_id} identified as user {track.user_id}")
            elif track.user_id == detection.user_id:
                # Same user, update confidence if higher
                if detection.recognition_confidence and (
                    track.recognition_confidence is None or
                    detection.recognition_confidence > track.recognition_confidence
                ):
                    track.recognition_confidence = detection.recognition_confidence
            else:
                # Different user detected - this shouldn't happen often
                # Keep existing user_id but log warning
                logger.warning(
                    f"Track {track.track_id}: user_id mismatch "
                    f"(existing: {track.user_id}, detected: {detection.user_id})"
                )

        # Confirm track if reached min_hits
        if not track.is_confirmed and track.detection_count >= self.min_hits:
            track.is_confirmed = True
            logger.debug(f"Track {track.track_id} confirmed")

    def get_active_tracks(self, session_id: str) -> List[Track]:
        """
        Get all active tracks for a session

        Args:
            session_id: Session identifier

        Returns:
            List of active tracks
        """
        if session_id not in self.session_tracks:
            return []

        return list(self.session_tracks[session_id].values())

    def get_confirmed_tracks(self, session_id: str) -> List[Track]:
        """
        Get confirmed tracks for a session

        Args:
            session_id: Session identifier

        Returns:
            List of confirmed tracks
        """
        tracks = self.get_active_tracks(session_id)
        return [t for t in tracks if t.is_confirmed]

    def get_identified_users(self, session_id: str) -> Dict[str, Track]:
        """
        Get map of identified users to their tracks

        Args:
            session_id: Session identifier

        Returns:
            Dict mapping user_id to Track
        """
        tracks = self.get_confirmed_tracks(session_id)
        identified = {}

        for track in tracks:
            if track.user_id:
                # If multiple tracks for same user, keep most confident one
                if track.user_id not in identified:
                    identified[track.user_id] = track
                else:
                    existing = identified[track.user_id]
                    if (track.recognition_confidence or 0) > (existing.recognition_confidence or 0):
                        identified[track.user_id] = track

        return identified

    def get_session_stats(self, session_id: str) -> dict:
        """
        Get tracking statistics for a session

        Args:
            session_id: Session identifier

        Returns:
            Dict with tracking stats
        """
        if session_id not in self.session_tracks:
            return {
                "total_tracks": 0,
                "confirmed_tracks": 0,
                "identified_tracks": 0,
                "unidentified_tracks": 0
            }

        tracks = self.get_active_tracks(session_id)
        confirmed = [t for t in tracks if t.is_confirmed]
        identified = [t for t in confirmed if t.user_id]

        return {
            "total_tracks": len(tracks),
            "confirmed_tracks": len(confirmed),
            "identified_tracks": len(identified),
            "unidentified_tracks": len(confirmed) - len(identified)
        }


# Global tracking service instance (singleton)
# This is initialized in main.py during startup
tracking_service: Optional[TrackingService] = None


def get_tracking_service() -> TrackingService:
    """
    Get global tracking service instance

    Returns:
        TrackingService instance

    Raises:
        RuntimeError: If service not initialized
    """
    global tracking_service

    if tracking_service is None:
        # Auto-initialize with default settings
        tracking_service = TrackingService(
            max_age=settings.EARLY_LEAVE_THRESHOLD * settings.SCAN_INTERVAL_SECONDS,
            min_hits=1,  # Single detection confirms track (for 60s interval scans)
            iou_threshold=0.3
        )

    return tracking_service
