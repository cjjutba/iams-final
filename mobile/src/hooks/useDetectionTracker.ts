/**
 * useDetectionTracker
 *
 * Assigns stable track IDs to detections across frames using IoU
 * (Intersection over Union) matching. Known faces use their user_id;
 * unknown faces get a generated ID that persists as long as the bbox
 * overlaps with a previous frame's bbox.
 *
 * Stale tracks (not matched for STALE_FRAMES consecutive frames) are
 * removed with a brief fade-out window.
 */

import { useRef, useMemo } from 'react';
import type { DetectionItem } from '../components/video/DetectionOverlay';

export interface TrackedDetection extends DetectionItem {
  trackId: string;
  /** Number of consecutive frames this track was NOT matched. 0 = active. */
  staleFrames: number;
}

// How many missed frames before a track is dropped
const STALE_THRESHOLD = 5;
const IOU_THRESHOLD = 0.3;

let _nextTrackId = 0;
function generateTrackId(): string {
  return `track-${++_nextTrackId}`;
}

function computeIoU(
  a: { x: number; y: number; width: number; height: number },
  b: { x: number; y: number; width: number; height: number },
): number {
  const ax2 = a.x + a.width;
  const ay2 = a.y + a.height;
  const bx2 = b.x + b.width;
  const by2 = b.y + b.height;

  const ix1 = Math.max(a.x, b.x);
  const iy1 = Math.max(a.y, b.y);
  const ix2 = Math.min(ax2, bx2);
  const iy2 = Math.min(ay2, by2);

  if (ix2 <= ix1 || iy2 <= iy1) return 0;

  const intersection = (ix2 - ix1) * (iy2 - iy1);
  const areaA = a.width * a.height;
  const areaB = b.width * b.height;
  const union = areaA + areaB - intersection;

  return union > 0 ? intersection / union : 0;
}

export function useDetectionTracker(
  detections: DetectionItem[],
): TrackedDetection[] {
  const prevTracksRef = useRef<TrackedDetection[]>([]);

  const tracked = useMemo(() => {
    const prevTracks = prevTracksRef.current;
    const newTracks: TrackedDetection[] = [];
    const usedPrevIndices = new Set<number>();

    for (const det of detections) {
      // Known faces always use user_id as trackId
      if (det.user_id) {
        const prevIdx = prevTracks.findIndex(
          (t) => t.user_id === det.user_id,
        );
        if (prevIdx >= 0) usedPrevIndices.add(prevIdx);

        newTracks.push({
          ...det,
          trackId: det.user_id,
          staleFrames: 0,
        });
        continue;
      }

      // Unknown faces: match by IoU
      let bestIdx = -1;
      let bestIoU = IOU_THRESHOLD;

      for (let i = 0; i < prevTracks.length; i++) {
        if (usedPrevIndices.has(i)) continue;
        // Only match against other unknown tracks
        if (prevTracks[i].user_id) continue;

        const iou = computeIoU(det.bbox, prevTracks[i].bbox);
        if (iou > bestIoU) {
          bestIoU = iou;
          bestIdx = i;
        }
      }

      if (bestIdx >= 0) {
        usedPrevIndices.add(bestIdx);
        newTracks.push({
          ...det,
          trackId: prevTracks[bestIdx].trackId,
          staleFrames: 0,
        });
      } else {
        newTracks.push({
          ...det,
          trackId: generateTrackId(),
          staleFrames: 0,
        });
      }
    }

    // Carry forward unmatched previous tracks as stale (for fade-out)
    for (let i = 0; i < prevTracks.length; i++) {
      if (usedPrevIndices.has(i)) continue;
      const stale = prevTracks[i].staleFrames + 1;
      if (stale < STALE_THRESHOLD) {
        newTracks.push({ ...prevTracks[i], staleFrames: stale });
      }
    }

    prevTracksRef.current = newTracks;
    return newTracks;
  }, [detections]);

  return tracked;
}
