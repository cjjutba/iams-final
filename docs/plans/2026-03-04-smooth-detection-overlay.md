# Smooth 60 FPS Detection Overlay — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make face detection bounding boxes track smoothly at 60 FPS over the live video feed.

**Architecture:** Raise backend recognition from 2 FPS → 15 FPS (InsightFace on M5 handles this). Add `react-native-reanimated` to the mobile app so bounding boxes interpolate smoothly between detection updates on the native UI thread at 60 FPS. A new `useDetectionTracker` hook assigns stable IDs to faces across frames using IoU matching.

**Tech Stack:** react-native-reanimated (mobile), FastAPI config change (backend)

---

### Task 1: Backend — Raise Recognition FPS and WebSocket Push Rate

**Files:**
- Modify: `backend/app/config.py:94`
- Modify: `backend/app/routers/live_stream.py:265,410`

**Step 1: Update RECOGNITION_FPS config**

In `backend/app/config.py`, change line 94:

```python
# Before
RECOGNITION_FPS: float = 2.0  # Frames/sec to sample for face recognition

# After
RECOGNITION_FPS: float = 15.0  # Frames/sec to sample for face recognition
```

**Step 2: Update WebSocket poll intervals in live_stream.py**

In `backend/app/routers/live_stream.py`, change the `poll_interval` in both `_hls_mode` (line 265) and `_webrtc_mode` (line 410):

```python
# Before (both locations)
poll_interval = 0.100  # 100ms = 10Hz, matching RECOGNITION_FPS

# After (both locations)
poll_interval = 0.066  # 66ms ≈ 15Hz, matching RECOGNITION_FPS
```

**Step 3: Verify backend starts**

Run: `cd backend && python -c "from app.config import settings; print(f'RECOGNITION_FPS={settings.RECOGNITION_FPS}')"`
Expected: `RECOGNITION_FPS=15.0`

**Step 4: Commit**

```bash
git add backend/app/config.py backend/app/routers/live_stream.py
git commit -m "perf: raise recognition FPS from 2 to 15 and match WS push rate"
```

---

### Task 2: Mobile — Install react-native-reanimated

**Files:**
- Modify: `mobile/package.json`
- Modify: `mobile/babel.config.js`

**Step 1: Install reanimated**

Run: `cd mobile && pnpm add react-native-reanimated`

**Step 2: Add babel plugin**

In `mobile/babel.config.js`, add the reanimated plugin. It MUST be last in the plugins array:

```js
module.exports = function(api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: [
      'react-native-worklets-core/plugin',
      'react-native-reanimated/plugin',
    ],
  };
};
```

**Step 3: Verify install**

Run: `cd mobile && pnpm list react-native-reanimated`
Expected: Shows installed version (3.x)

**Step 4: Clear metro cache**

Run: `cd mobile && pnpm start -- --clear` (Ctrl+C after confirming it starts)

**Step 5: Commit**

```bash
git add mobile/package.json mobile/pnpm-lock.yaml mobile/babel.config.js
git commit -m "deps: add react-native-reanimated for smooth bbox interpolation"
```

---

### Task 3: Mobile — Create `useDetectionTracker` Hook

This hook takes raw detections from the WebSocket and assigns stable `trackId` values using IoU matching. This is what lets reanimated know "this box is the SAME face as last frame" so it can interpolate smoothly.

**Files:**
- Create: `mobile/src/hooks/useDetectionTracker.ts`

**Step 1: Write the hook**

```typescript
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
```

**Step 2: Commit**

```bash
git add mobile/src/hooks/useDetectionTracker.ts
git commit -m "feat: add useDetectionTracker hook with IoU-based face tracking"
```

---

### Task 4: Mobile — Rewrite DetectionOverlay with Reanimated Interpolation

Replace the static `View`-based DetectionBox with reanimated animated components that smoothly interpolate bbox positions on the native UI thread at 60 FPS.

**Files:**
- Rewrite: `mobile/src/components/video/DetectionOverlay.tsx`

**Step 1: Rewrite the overlay**

The key changes:
- `AnimatedDetectionBox` uses `useSharedValue` + `withTiming` for x/y/w/h
- `useEffect` drives shared values when detection bbox changes
- `useAnimatedStyle` runs on UI thread at 60 FPS
- Stale tracks (disappearing faces) fade out via animated opacity
- `computeScale` stays unchanged

```typescript
/**
 * Detection Overlay
 *
 * Renders face detection bounding boxes with smooth 60 FPS interpolation
 * using react-native-reanimated. Detection coordinates are received from
 * the backend at ~15 FPS; reanimated smoothly transitions positions on
 * the native UI thread between updates.
 */

import React, { useEffect, useMemo } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  Easing,
} from 'react-native-reanimated';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DetectionBBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DetectionItem {
  bbox: DetectionBBox;
  confidence: number;
  user_id: string | null;
  student_id: string | null;
  name: string | null;
  similarity: number | null;
}

interface DetectionOverlayProps {
  detections: DetectionItem[];
  /** Native video width the backend used for detection. */
  videoWidth: number;
  /** Native video height the backend used for detection. */
  videoHeight: number;
  /** On-screen container width (from onLayout). */
  containerWidth: number;
  /** On-screen container height (from onLayout). */
  containerHeight: number;
  /** How the video is fitted into its container (default: 'contain'). */
  resizeMode?: 'contain' | 'cover';
}

// ---------------------------------------------------------------------------
// Coordinate scaling (handles letterboxing / cover)
// ---------------------------------------------------------------------------

interface ScaleInfo {
  scale: number;
  offsetX: number;
  offsetY: number;
}

function computeScale(
  videoW: number,
  videoH: number,
  containerW: number,
  containerH: number,
  mode: 'contain' | 'cover' = 'contain',
): ScaleInfo {
  if (videoW <= 0 || videoH <= 0 || containerW <= 0 || containerH <= 0) {
    return { scale: 1, offsetX: 0, offsetY: 0 };
  }

  const videoAspect = videoW / videoH;
  const containerAspect = containerW / containerH;

  let scale: number;
  let offsetX = 0;
  let offsetY = 0;

  if (mode === 'cover') {
    if (videoAspect > containerAspect) {
      scale = containerH / videoH;
      offsetX = (containerW - videoW * scale) / 2;
    } else {
      scale = containerW / videoW;
      offsetY = (containerH - videoH * scale) / 2;
    }
  } else {
    if (videoAspect > containerAspect) {
      scale = containerW / videoW;
      offsetY = (containerH - videoH * scale) / 2;
    } else {
      scale = containerH / videoH;
      offsetX = (containerW - videoW * scale) / 2;
    }
  }

  return { scale, offsetX, offsetY };
}

// ---------------------------------------------------------------------------
// Timing config: fast ease-out for snappy tracking
// ---------------------------------------------------------------------------

const TIMING_CONFIG = {
  duration: 80,
  easing: Easing.out(Easing.quad),
};

const FADE_OUT_CONFIG = {
  duration: 150,
  easing: Easing.out(Easing.quad),
};

// ---------------------------------------------------------------------------
// AnimatedDetectionBox
// ---------------------------------------------------------------------------

interface TrackedBoxProps {
  bbox: DetectionBBox;
  isKnown: boolean;
  label: string;
  simText: string;
  staleFrames: number;
  scaleInfo: ScaleInfo;
}

const AnimatedDetectionBox: React.FC<TrackedBoxProps> = ({
  bbox,
  isKnown,
  label,
  simText,
  staleFrames,
  scaleInfo,
}) => {
  const { scale, offsetX, offsetY } = scaleInfo;

  const targetLeft = bbox.x * scale + offsetX;
  const targetTop = bbox.y * scale + offsetY;
  const targetWidth = bbox.width * scale;
  const targetHeight = bbox.height * scale;

  const left = useSharedValue(targetLeft);
  const top = useSharedValue(targetTop);
  const width = useSharedValue(targetWidth);
  const height = useSharedValue(targetHeight);
  const opacity = useSharedValue(staleFrames > 0 ? 0 : 1);

  useEffect(() => {
    left.value = withTiming(targetLeft, TIMING_CONFIG);
    top.value = withTiming(targetTop, TIMING_CONFIG);
    width.value = withTiming(targetWidth, TIMING_CONFIG);
    height.value = withTiming(targetHeight, TIMING_CONFIG);
  }, [targetLeft, targetTop, targetWidth, targetHeight]);

  useEffect(() => {
    opacity.value = withTiming(staleFrames > 0 ? 0 : 1, FADE_OUT_CONFIG);
  }, [staleFrames]);

  const animatedStyle = useAnimatedStyle(() => ({
    left: left.value,
    top: top.value,
    width: width.value,
    height: height.value,
    opacity: opacity.value,
  }));

  const borderColor = isKnown ? '#00E676' : '#FFD600';
  const hasLabel = label.length > 0;

  return (
    <Animated.View style={[styles.box, { borderColor }, animatedStyle]}>
      {hasLabel && (
        <View
          style={[
            styles.labelContainer,
            {
              backgroundColor: isKnown
                ? 'rgba(0,0,0,0.72)'
                : 'rgba(60,40,0,0.80)',
            },
          ]}
        >
          <Text
            style={[styles.labelText, { color: borderColor }]}
            numberOfLines={1}
          >
            {label}
            {simText}
          </Text>
        </View>
      )}
    </Animated.View>
  );
};

// ---------------------------------------------------------------------------
// UnknownBadge
// ---------------------------------------------------------------------------

const UnknownBadge: React.FC<{ count: number }> = React.memo(({ count }) => {
  if (count === 0) return null;
  return (
    <View style={styles.unknownBadge}>
      <Text style={styles.unknownBadgeText}>{count} unrecognized</Text>
    </View>
  );
});

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export const DetectionOverlay: React.FC<DetectionOverlayProps> = React.memo(
  ({
    detections,
    videoWidth,
    videoHeight,
    containerWidth,
    containerHeight,
    resizeMode = 'contain',
  }) => {
    const scaleInfo = useMemo(
      () =>
        computeScale(
          videoWidth,
          videoHeight,
          containerWidth,
          containerHeight,
          resizeMode,
        ),
      [videoWidth, videoHeight, containerWidth, containerHeight, resizeMode],
    );

    const unknownCount = useMemo(
      () => detections.filter((d) => !d.user_id).length,
      [detections],
    );

    if (!detections.length || containerWidth === 0 || containerHeight === 0) {
      return null;
    }

    return (
      <View style={StyleSheet.absoluteFill} pointerEvents="none">
        {detections.map((det) => {
          const trackId =
            (det as any).trackId || det.user_id || `unk-${det.bbox.x}-${det.bbox.y}`;
          const label =
            det.name ||
            det.student_id ||
            (det.user_id?.slice(0, 8) ?? '');
          const simText =
            det.similarity != null
              ? ` ${(det.similarity * 100).toFixed(0)}%`
              : '';
          const staleFrames = (det as any).staleFrames ?? 0;

          return (
            <AnimatedDetectionBox
              key={trackId}
              bbox={det.bbox}
              isKnown={!!det.user_id}
              label={label}
              simText={simText}
              staleFrames={staleFrames}
              scaleInfo={scaleInfo}
            />
          );
        })}
        <UnknownBadge count={unknownCount} />
      </View>
    );
  },
);

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  box: {
    position: 'absolute',
    borderWidth: 1.5,
    borderRadius: 2,
  },
  labelContainer: {
    position: 'absolute',
    top: -20,
    left: -1,
    paddingHorizontal: 5,
    paddingVertical: 1,
    borderRadius: 2,
  },
  labelText: {
    fontSize: 10,
    fontWeight: '700',
  },
  unknownBadge: {
    position: 'absolute',
    bottom: 8,
    right: 8,
    backgroundColor: 'rgba(255,214,0,0.18)',
    borderWidth: 1,
    borderColor: '#FFD600',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  unknownBadgeText: {
    color: '#FFD600',
    fontSize: 11,
    fontWeight: '600',
  },
});
```

**Step 2: Commit**

```bash
git add mobile/src/components/video/DetectionOverlay.tsx
git commit -m "feat: rewrite DetectionOverlay with reanimated 60fps interpolation"
```

---

### Task 5: Mobile — Wire Tracker into FacultyLiveFeedScreen

Connect the `useDetectionTracker` hook between the WebSocket detections and the overlay so tracked detections (with stable IDs) flow into the reanimated overlay.

**Files:**
- Modify: `mobile/src/screens/faculty/FacultyLiveFeedScreen.tsx`

**Step 1: Add tracker import and wire it in**

Add import at top of file (after existing imports):

```typescript
import { useDetectionTracker } from '../../hooks/useDetectionTracker';
```

Inside the component, after the `useDetectionWebSocket` call (line ~162), add:

```typescript
// Assign stable track IDs for smooth interpolation
const trackedDetections = useDetectionTracker(detections);
```

Then replace all three occurrences of `detections={detections}` on the `<DetectionOverlay>` components (lines ~441 and ~458) with:

```typescript
detections={trackedDetections}
```

Also update the `detectedCount` derivation (line ~274) to use `detections` (raw, not tracked — tracked includes stale):

```typescript
// Keep using raw detections for count (excludes stale tracks)
const detectedCount = useMemo(() => detections.length, [detections]);
```

This is already correct — no change needed here. Only the `<DetectionOverlay>` props change.

**Step 2: Verify TypeScript compiles**

Run: `cd mobile && npx tsc --noEmit 2>&1 | grep -v "FaceScanCamera\|config.ts"`
Expected: No new errors (only the 3 pre-existing ones)

**Step 3: Commit**

```bash
git add mobile/src/screens/faculty/FacultyLiveFeedScreen.tsx
git commit -m "feat: wire useDetectionTracker into live feed for smooth bbox tracking"
```

---

### Task 6: Smoke Test — Full Pipeline Verification

**Step 1: Start backend**

Run: `cd backend && source venv/bin/activate && python run.py`
Verify log shows: `RECOGNITION_FPS` is now 15.0 (or appears in startup logs)

**Step 2: Start mobile app**

Run: `cd mobile && pnpm start --clear` then open on device/emulator

**Step 3: Manual verification checklist**

Open a live feed screen and verify:
- [ ] Video streams at 30 FPS via WebRTC (smooth video)
- [ ] Bounding boxes appear on detected faces
- [ ] Boxes move smoothly when faces move (no jumping/teleporting)
- [ ] Known faces show green border + name label
- [ ] Unknown faces show yellow border, no empty orange label pill
- [ ] Border thickness is thin (1.5px)
- [ ] When a face leaves frame, its box fades out (~150ms)
- [ ] Status bar shows detection count updating more frequently than before

**Step 4: Commit any fixes discovered during testing**

---

### Summary of All Changes

| File | Change |
|------|--------|
| `backend/app/config.py:94` | `RECOGNITION_FPS` 2.0 → 15.0 |
| `backend/app/routers/live_stream.py:265,410` | `poll_interval` 0.100 → 0.066 |
| `mobile/package.json` | Add `react-native-reanimated` |
| `mobile/babel.config.js` | Add reanimated babel plugin |
| `mobile/src/hooks/useDetectionTracker.ts` | New: IoU-based face tracking across frames |
| `mobile/src/components/video/DetectionOverlay.tsx` | Rewrite: reanimated 60 FPS interpolation |
| `mobile/src/screens/faculty/FacultyLiveFeedScreen.tsx` | Wire tracker → overlay |
