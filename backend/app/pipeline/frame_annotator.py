"""Server-side frame annotator -- draws bounding boxes, labels, and HUD bars.

Uses OpenCV drawing functions for enterprise-style corner bracket boxes,
color-coded by track state, with semi-transparent HUD bars.

Performance: ~3-5 ms for 50 faces at 640x480.
"""

import cv2
import numpy as np

# Color palette (BGR)
COLORS: dict[str, tuple[int, int, int]] = {
    "confirmed": (0, 200, 0),       # Green  -- recognized student
    "unknown":   (0, 200, 255),      # Yellow/amber -- detected, not matched
    "new":       (255, 200, 0),      # Cyan   -- just appeared
    "lost":      (128, 128, 128),    # Gray   -- temporarily lost
    "alert":     (0, 0, 255),        # Red    -- early leave
}

_FONT = cv2.FONT_HERSHEY_SIMPLEX


class FrameAnnotator:
    """High-performance frame annotator with corner bracket boxes and HUD.

    Draws enterprise-style bounding boxes (corner brackets, not full
    rectangles), color-coded labels with track metadata, and a semi-transparent
    HUD showing room/session information.

    Args:
        width: Frame width in pixels.
        height: Frame height in pixels.
    """

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.corner_length = 15
        self.box_thickness = 2
        self.font_scale = 0.45
        self.font_thickness = 1
        self.bar_height = 30

    def annotate(
        self,
        frame: np.ndarray,
        detections: list[dict],
        hud_info: dict,
    ) -> np.ndarray:
        """Draw all annotations onto *frame* in-place and return it.

        Args:
            frame: BGR numpy array to annotate.
            detections: List of detection dicts, each containing:
                ``bbox`` (x1, y1, x2, y2), ``name``, ``student_id``,
                ``confidence``, ``track_state``, ``track_id``, ``duration_sec``.
            hud_info: Dict with ``room_name``, ``timestamp``, ``subject``,
                ``professor``, ``present_count``, ``total_count``.

        Returns:
            The annotated frame (same object as *frame*).
        """
        for det in detections:
            self._draw_detection(frame, det)
        self._draw_hud(frame, hud_info)
        return frame

    # ------------------------------------------------------------------
    # Detection drawing
    # ------------------------------------------------------------------

    def _draw_detection(self, frame: np.ndarray, det: dict) -> None:
        """Draw corner brackets, label background, and text for one detection."""
        x1, y1, x2, y2 = (int(v) for v in det["bbox"])
        state = det.get("track_state", "unknown")
        color = COLORS.get(state, COLORS["unknown"])

        # Corner bracket length -- cap at one-third of the shorter side
        cl = min(self.corner_length, (x2 - x1) // 3, (y2 - y1) // 3)
        t = self.box_thickness

        # Top-left
        cv2.line(frame, (x1, y1), (x1 + cl, y1), color, t)
        cv2.line(frame, (x1, y1), (x1, y1 + cl), color, t)
        # Top-right
        cv2.line(frame, (x2, y1), (x2 - cl, y1), color, t)
        cv2.line(frame, (x2, y1), (x2, y1 + cl), color, t)
        # Bottom-left
        cv2.line(frame, (x1, y2), (x1 + cl, y2), color, t)
        cv2.line(frame, (x1, y2), (x1, y2 - cl), color, t)
        # Bottom-right
        cv2.line(frame, (x2, y2), (x2 - cl, y2), color, t)
        cv2.line(frame, (x2, y2), (x2, y2 - cl), color, t)

        # -- Label text --
        if det.get("name"):
            line1 = f"{det['name']}"
            if det.get("student_id"):
                line1 += f" ({det['student_id']})"
        else:
            line1 = "Unknown Face"

        conf = det.get("confidence", 0)
        tid = det.get("track_id", 0)
        dur = det.get("duration_sec", 0)
        mins, secs = int(dur // 60), int(dur % 60)
        line2 = f"{conf:.0%} | T#{tid} | {mins}m{secs:02d}s"

        (tw1, th1), _ = cv2.getTextSize(line1, _FONT, self.font_scale, self.font_thickness)
        (tw2, th2), _ = cv2.getTextSize(line2, _FONT, self.font_scale * 0.85, self.font_thickness)

        tw = max(tw1, tw2)
        pad = 3
        label_h = th1 + th2 + pad * 3

        # Position above box, or inside if near top
        if y1 > label_h + 5:
            lx, ly = x1, y1 - label_h - 2
        else:
            lx, ly = x1, y1 + 2

        # Label background (ROI-only blend for performance)
        bg_y1 = max(ly, 0)
        bg_y2 = min(ly + label_h, frame.shape[0])
        bg_x1 = max(lx, 0)
        bg_x2 = min(lx + tw + pad * 2, frame.shape[1])

        if bg_y2 > bg_y1 and bg_x2 > bg_x1:
            roi = frame[bg_y1:bg_y2, bg_x1:bg_x2]
            bg_color = np.array(color, dtype=np.uint16)
            blended = (roi.astype(np.uint16) * 102 // 255 + bg_color * 153 // 255).astype(np.uint8)
            frame[bg_y1:bg_y2, bg_x1:bg_x2] = blended

        # Text lines
        text_y = ly + pad + th1
        if 0 <= text_y < frame.shape[0] and 0 <= lx + pad < frame.shape[1]:
            cv2.putText(
                frame, line1, (lx + pad, text_y),
                _FONT, self.font_scale, (255, 255, 255),
                self.font_thickness, cv2.LINE_AA,
            )
            cv2.putText(
                frame, line2, (lx + pad, text_y + th2 + pad),
                _FONT, self.font_scale * 0.85, (200, 200, 200),
                self.font_thickness, cv2.LINE_AA,
            )

    # ------------------------------------------------------------------
    # HUD bars
    # ------------------------------------------------------------------

    def _draw_hud(self, frame: np.ndarray, info: dict) -> None:
        """Draw semi-transparent top and bottom HUD bars."""
        h, w = frame.shape[:2]
        bh = self.bar_height

        # -- Top bar --
        roi_top = frame[0:bh, :]
        roi_top[:] = (roi_top.astype(np.uint16) * 102 // 255).astype(np.uint8)

        top_left = f"IAMS | {info.get('room_name', '')}"
        top_right = info.get("timestamp", "")
        cv2.putText(
            frame, top_left, (8, bh - 8),
            _FONT, 0.45, (255, 255, 255), 1, cv2.LINE_AA,
        )
        (trw, _), _ = cv2.getTextSize(top_right, _FONT, 0.45, 1)
        cv2.putText(
            frame, top_right, (w - trw - 8, bh - 8),
            _FONT, 0.45, (255, 255, 255), 1, cv2.LINE_AA,
        )

        # -- Bottom bar --
        roi_bot = frame[h - bh : h, :]
        roi_bot[:] = (roi_bot.astype(np.uint16) * 102 // 255).astype(np.uint8)

        present = info.get("present_count", 0)
        total = info.get("total_count", 0)
        bot_text = (
            f"{info.get('subject', '')} | {info.get('professor', '')} | "
            f"{present}/{total} Present"
        )
        cv2.putText(
            frame, bot_text, (8, h - 8),
            _FONT, 0.45, (255, 255, 255), 1, cv2.LINE_AA,
        )
