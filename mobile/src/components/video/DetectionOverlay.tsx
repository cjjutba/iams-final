/**
 * Detection Overlay
 *
 * Renders face detection bounding boxes on top of RTCView / video.
 * Uses plain View components (not react-native-reanimated) to ensure
 * rendering works on Android's SurfaceView (RTCView).
 *
 * The box and its name label are rendered as **separate** absolutely-
 * positioned Views (siblings in the overlay). This avoids Android's
 * overflow clipping: the label is never a child of the narrow box,
 * so its width isn't constrained by the tiny face-crop rectangle.
 */

import React, { useMemo } from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';

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
// Detection color scheme
// ---------------------------------------------------------------------------

/** Recognized student: green bounding box */
const COLOR_RECOGNIZED = '#22C55E';
/** Unknown / unrecognized face: amber/yellow */
const COLOR_UNKNOWN = '#F59E0B';

const LABEL_OFFSET = 10; // px above the box top

function getDetectionColor(userId: string | null): string {
  return userId ? COLOR_RECOGNIZED : COLOR_UNKNOWN;
}

// ---------------------------------------------------------------------------
// DetectionBox — plain View (works on top of Android SurfaceView/RTCView)
// ---------------------------------------------------------------------------

interface BoxProps {
  bbox: DetectionBBox;
  userId: string | null;
  label: string;
  staleFrames: number;
  scaleInfo: ScaleInfo;
}

const DetectionBox: React.FC<BoxProps> = React.memo(({
  bbox,
  userId,
  label,
  staleFrames,
  scaleInfo,
}) => {
  const { scale, offsetX, offsetY } = scaleInfo;

  const left = bbox.x * scale + offsetX;
  const top = bbox.y * scale + offsetY;
  const width = bbox.width * scale;
  const height = bbox.height * scale;
  const borderColor = getDetectionColor(userId);
  const opacity = staleFrames > 0 ? 0.3 : 1;
  const hasLabel = label.length > 0;

  return (
    <>
      {/* Bounding box */}
      <View
        style={[
          styles.box,
          {
            left,
            top,
            width,
            height,
            borderColor,
            opacity,
          },
        ]}
      />
      {/* Name label (separate element — not clipped by box width) */}
      {hasLabel && (
        <View
          style={[
            styles.labelAnchor,
            {
              left: left + width / 2,
              top: Math.max(0, top - LABEL_OFFSET),
              opacity,
            },
          ]}
        >
          <View style={[styles.labelBg, { backgroundColor: borderColor }]}>
            <Text style={styles.labelText} numberOfLines={1}>
              {label}
            </Text>
          </View>
        </View>
      )}
    </>
  );
});
DetectionBox.displayName = 'DetectionBox';

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
UnknownBadge.displayName = 'UnknownBadge';

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
      <View style={styles.overlay} pointerEvents="none">
        {detections.map((det) => {
          const trackId =
            (det as any).trackId || det.user_id || `unk-${det.bbox.x}-${det.bbox.y}`;
          // Show first name only for known, "Unknown" for unrecognized
          const fullName = det.name || det.student_id || '';
          const label = det.user_id
            ? fullName.split(' ')[0].slice(0, 10)
            : 'Unknown';
          const staleFrames = (det as any).staleFrames ?? 0;

          return (
            <DetectionBox
              key={trackId}
              bbox={det.bbox}
              userId={det.user_id}
              label={label}
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
DetectionOverlay.displayName = 'DetectionOverlay';

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    // On Android, elevation ensures we render above SurfaceView (RTCView)
    ...(Platform.OS === 'android' ? { elevation: 10 } : {}),
  },
  box: {
    position: 'absolute',
    borderWidth: 2,
    borderRadius: 3,
  },
  labelAnchor: {
    position: 'absolute',
    alignItems: 'center',
    transform: [{ translateX: -40 }],
  },
  labelBg: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    minWidth: 50,
    alignItems: 'center',
  },
  labelText: {
    fontSize: 9,
    fontWeight: '700',
    color: '#FFFFFF',
    textAlign: 'center',
  },
  unknownBadge: {
    position: 'absolute',
    bottom: 8,
    right: 8,
    backgroundColor: 'rgba(245,158,11,0.18)',
    borderWidth: 1,
    borderColor: COLOR_UNKNOWN,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  unknownBadgeText: {
    color: COLOR_UNKNOWN,
    fontSize: 11,
    fontWeight: '600',
  },
});
