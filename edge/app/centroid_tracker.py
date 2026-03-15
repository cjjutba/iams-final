"""Centroid-based bounding box tracker for stable face track IDs.

Assigns persistent track IDs to face detections across consecutive frames
using greedy nearest-neighbor matching on Euclidean distance between
bounding box centroids.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class TrackedObject:
    """A tracked face detection with a stable ID across frames."""

    track_id: int
    centroid: tuple[float, float]
    bbox: list[int]
    confidence: float
    frames_since_seen: int = 0
    prev_centroid: tuple[float, float] | None = None

    @property
    def velocity(self) -> tuple[float, float]:
        """Return (dx, dy) from prev_centroid to centroid.

        Returns (0.0, 0.0) if there is no previous centroid.
        """
        if self.prev_centroid is None:
            return (0.0, 0.0)
        return (
            self.centroid[0] - self.prev_centroid[0],
            self.centroid[1] - self.prev_centroid[1],
        )


class CentroidTracker:
    """Lightweight centroid tracker for face bounding boxes.

    Parameters
    ----------
    max_disappeared : int
        Number of consecutive frames a track can go unmatched before removal.
    max_distance : float
        Maximum Euclidean distance (in pixels) to consider a match.
    """

    _MAX_TRACK_ID = 65535

    def __init__(
        self, max_disappeared: int = 5, max_distance: float = 50.0
    ) -> None:
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

        self._next_id: int = 0
        self._objects: dict[int, TrackedObject] = {}
        self._frame_seq: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def frame_seq(self) -> int:
        """Monotonic counter incremented on each ``update()`` call."""
        return self._frame_seq

    def reset(self) -> None:
        """Clear all tracked objects and reset internal state."""
        self._next_id = 0
        self._objects.clear()
        self._frame_seq = 0

    def update(self, detections: list[dict]) -> list[TrackedObject]:
        """Process a new frame of detections and return tracked objects.

        Parameters
        ----------
        detections : list[dict]
            Each dict must contain:
            - ``bbox``: ``[x, y, w, h]`` (ints)
            - ``confidence``: ``float``

        Returns
        -------
        list[TrackedObject]
            All currently-alive tracked objects (matched + newly registered).
        """
        self._frame_seq += 1

        # Compute centroids for incoming detections.
        det_centroids: list[tuple[float, float]] = []
        for det in detections:
            x, y, w, h = det["bbox"]
            det_centroids.append((x + w / 2.0, y + h / 2.0))

        # If no existing tracks, register all detections as new.
        if not self._objects:
            for det, centroid in zip(detections, det_centroids):
                self._register(centroid, det["bbox"], det["confidence"])
            return list(self._objects.values())

        # If no detections this frame, increment disappeared counters.
        if len(detections) == 0:
            self._mark_all_disappeared()
            return list(self._objects.values())

        # Build distance matrix between existing tracks and new detections.
        track_ids = list(self._objects.keys())
        track_centroids = np.array(
            [self._objects[tid].centroid for tid in track_ids]
        )
        det_centroids_arr = np.array(det_centroids)

        # Euclidean distance matrix: shape (num_tracks, num_detections)
        diff = track_centroids[:, np.newaxis, :] - det_centroids_arr[np.newaxis, :, :]
        dist_matrix = np.sqrt((diff ** 2).sum(axis=2))

        # Greedy nearest-neighbor matching.
        matched_tracks: set[int] = set()
        matched_dets: set[int] = set()

        # Use numpy argsort for efficient pair ordering.
        flat_indices = np.argsort(dist_matrix, axis=None)
        for idx in flat_indices:
            ti, di = divmod(int(idx), dist_matrix.shape[1])
            dist = dist_matrix[ti, di]
            if dist > self.max_distance:
                break
            if ti in matched_tracks or di in matched_dets:
                continue

            tid = track_ids[ti]
            obj = self._objects[tid]

            # Save previous centroid before updating.
            obj.prev_centroid = obj.centroid
            obj.centroid = det_centroids[di]
            obj.bbox = detections[di]["bbox"]
            obj.confidence = detections[di]["confidence"]
            obj.frames_since_seen = 0

            matched_tracks.add(ti)
            matched_dets.add(di)

        # Mark unmatched tracks as disappeared.
        for ti in range(len(track_ids)):
            if ti not in matched_tracks:
                tid = track_ids[ti]
                self._objects[tid].frames_since_seen += 1
                if self._objects[tid].frames_since_seen > self.max_disappeared:
                    del self._objects[tid]

        # Register unmatched detections as new tracks.
        for di in range(len(detections)):
            if di not in matched_dets:
                self._register(
                    det_centroids[di],
                    detections[di]["bbox"],
                    detections[di]["confidence"],
                )

        return list(self._objects.values())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register(
        self,
        centroid: tuple[float, float],
        bbox: list[int],
        confidence: float,
    ) -> None:
        """Create a new tracked object with the next available ID."""
        start = self._next_id
        while self._next_id in self._objects:
            self._next_id = (self._next_id + 1) % (self._MAX_TRACK_ID + 1)
            if self._next_id == start:
                return  # ID space exhausted, skip registration
        obj = TrackedObject(
            track_id=self._next_id,
            centroid=centroid,
            bbox=bbox,
            confidence=confidence,
        )
        self._objects[self._next_id] = obj
        self._next_id = (self._next_id + 1) % (self._MAX_TRACK_ID + 1)

    def _mark_all_disappeared(self) -> None:
        """Increment disappeared counter for all tracks; drop expired ones."""
        to_delete = []
        for tid, obj in self._objects.items():
            obj.frames_since_seen += 1
            if obj.frames_since_seen > self.max_disappeared:
                to_delete.append(tid)
        for tid in to_delete:
            del self._objects[tid]
