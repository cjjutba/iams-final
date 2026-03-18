"""Server-side frame annotator — clean corner-bracket bounding boxes with labels.

Single unified box style: corner brackets with consistent thickness and sizing.
Color-coded by track state. Optimized for H.264 compression at 720p.
"""

import cv2
import numpy as np

# Color palette (BGR) — high-contrast, compression-friendly
COLORS: dict[str, tuple[int, int, int]] = {
    "confirmed": (0, 220, 0),        # Green  — recognized student
    "unknown":   (0, 220, 220),      # Yellow — detected, not matched
    "new":       (0, 220, 220),      # Yellow — same as unknown (unified look)
    "lost":      (150, 150, 150),    # Gray   — temporarily lost
    "alert":     (0, 0, 255),        # Red    — early leave
}

_FONT = cv2.FONT_HERSHEY_SIMPLEX


class FrameAnnotator:
    """Production-grade frame annotator with corner-bracket bounding boxes.

    All faces use the same box style: corner brackets with a compact label.
    Small faces are expanded to a minimum visible size.
    """

    # Minimum box size after expansion (pixels)
    MIN_BOX = 50

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

        # Scale drawing parameters based on resolution
        scale = width / 1280.0  # normalize to 720p
        self.corner_length = max(int(18 * scale), 8)
        self.box_thickness = 2
        self.font_scale = max(0.4 * scale, 0.3)
        self.font_thickness = 1

    def annotate(
        self,
        frame: np.ndarray,
        detections: list[dict],
        hud_info: dict,
    ) -> np.ndarray:
        """Draw all bounding boxes onto frame and return it."""
        for det in detections:
            self._draw_detection(frame, det)
        return frame

    def _draw_detection(self, frame: np.ndarray, det: dict) -> None:
        """Draw one detection: corner brackets + compact label."""
        x1, y1, x2, y2 = (int(v) for v in det["bbox"])
        state = det.get("track_state", "unknown")
        color = COLORS.get(state, COLORS["unknown"])
        h_frame, w_frame = frame.shape[:2]

        bw, bh = x2 - x1, y2 - y1

        # Expand small boxes to minimum visible size
        if bw < self.MIN_BOX or bh < self.MIN_BOX:
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            half = self.MIN_BOX // 2
            x1 = max(0, cx - half)
            y1 = max(0, cy - half)
            x2 = min(w_frame - 1, cx + half)
            y2 = min(h_frame - 1, cy + half)
            bw, bh = x2 - x1, y2 - y1

        t = self.box_thickness
        cl = min(self.corner_length, bw // 3, bh // 3)
        cl = max(cl, 6)

        # Corner brackets (unified style for all sizes)
        # Top-left
        cv2.line(frame, (x1, y1), (x1 + cl, y1), color, t, cv2.LINE_AA)
        cv2.line(frame, (x1, y1), (x1, y1 + cl), color, t, cv2.LINE_AA)
        # Top-right
        cv2.line(frame, (x2, y1), (x2 - cl, y1), color, t, cv2.LINE_AA)
        cv2.line(frame, (x2, y1), (x2, y1 + cl), color, t, cv2.LINE_AA)
        # Bottom-left
        cv2.line(frame, (x1, y2), (x1 + cl, y2), color, t, cv2.LINE_AA)
        cv2.line(frame, (x1, y2), (x1, y2 - cl), color, t, cv2.LINE_AA)
        # Bottom-right
        cv2.line(frame, (x2, y2), (x2 - cl, y2), color, t, cv2.LINE_AA)
        cv2.line(frame, (x2, y2), (x2, y2 - cl), color, t, cv2.LINE_AA)

        # Compact label: "Name" or "Unknown"
        name = det.get("name") or "Unknown"
        label = name

        (tw, th), baseline = cv2.getTextSize(label, _FONT, self.font_scale, self.font_thickness)
        pad = 2

        # Position label above the box
        label_y = y1 - pad - 2
        if label_y - th < 0:
            label_y = y2 + th + pad + 2  # below box if too close to top

        # Background pill
        bg_x1 = max(x1, 0)
        bg_x2 = min(x1 + tw + pad * 2, w_frame)
        bg_y1 = max(label_y - th - pad, 0)
        bg_y2 = min(label_y + pad + baseline, h_frame)

        if bg_y2 > bg_y1 and bg_x2 > bg_x1:
            cv2.rectangle(frame, (bg_x1, bg_y1), (bg_x2, bg_y2), color, cv2.FILLED)
            cv2.putText(
                frame, label, (bg_x1 + pad, label_y),
                _FONT, self.font_scale, (0, 0, 0),
                self.font_thickness, cv2.LINE_AA,
            )
