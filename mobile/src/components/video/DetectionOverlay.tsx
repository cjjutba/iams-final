/**
 * Detection Overlay
 *
 * Renders face detection bounding boxes with smooth 60 FPS interpolation
 * using react-native-reanimated. Detection coordinates are received from
 * the backend at ~15 FPS; reanimated smoothly transitions positions on
 * the native UI thread between updates.
 *
 * The box and its name label are rendered as **separate** absolutely-
 * positioned Animated.Views (siblings in the overlay). This avoids
 * Android's overflow clipping: the label is never a child of the narrow
 * box, so its width isn't constrained by the tiny face-crop rectangle.
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
//
// Returns a Fragment with TWO sibling Animated.Views:
//   1. The bounding box (border rectangle)
//   2. The name label (positioned just above the box)
//
// Both share the same animated position values so they move in sync.
// Because they are siblings (not parent/child), the label's width is
// unconstrained and can display the full student name regardless of
// how small the face box is.
// ---------------------------------------------------------------------------

const LABEL_OFFSET = 10; // px above the box top

// ---------------------------------------------------------------------------
// Detection color scheme
// ---------------------------------------------------------------------------

/** Recognized student: green bounding box */
const COLOR_RECOGNIZED = '#22C55E';
/** Unknown / unrecognized face: muted red-orange */
const COLOR_UNKNOWN = '#EF4444';

/**
 * Determine bounding box color: green for recognized students, red for unknown.
 * A face is "recognized" when the backend returns a non-null user_id,
 * which only happens when similarity passes threshold + margin checks.
 */
function getDetectionColor(userId: string | null): string {
  return userId ? COLOR_RECOGNIZED : COLOR_UNKNOWN;
}

interface TrackedBoxProps {
  bbox: DetectionBBox;
  userId: string | null;
  label: string;
  staleFrames: number;
  scaleInfo: ScaleInfo;
}

const AnimatedDetectionBox: React.FC<TrackedBoxProps> = ({
  bbox,
  userId,
  label,
  staleFrames,
  scaleInfo,
}) => {
  const { scale, offsetX, offsetY } = scaleInfo;

  const hasLabel = label.length > 0;

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

  // Box style — positioned exactly at the face coordinates
  const boxStyle = useAnimatedStyle(() => ({
    left: left.value,
    top: top.value,
    width: width.value,
    height: height.value,
    opacity: opacity.value,
  }));

  // Label style — centered above the box, no width constraint
  const labelStyle = useAnimatedStyle(() => ({
    left: left.value + width.value / 2,
    top: Math.max(0, top.value - LABEL_OFFSET),
    opacity: opacity.value,
  }));

  const borderColor = getDetectionColor(userId);

  return (
    <>
      {/* Bounding box */}
      <Animated.View style={[styles.box, { borderColor }, boxStyle]} />
      {/* Name label (separate element — not clipped by box width) */}
      {hasLabel && (
        <Animated.View style={[styles.labelAnchor, labelStyle]}>
          {/* Stroke: dark text behind for readability */}
          <Text
            style={[styles.labelText, styles.labelStroke]}
            numberOfLines={1}
          >
            {label}
          </Text>
          {/* Fill: always white for readability */}
          <Text
            style={[styles.labelText, styles.labelFill, { color: '#FFFFFF' }]}
            numberOfLines={1}
          >
            {label}
          </Text>
        </Animated.View>
      )}
    </>
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
          // Show first name only for known, "Unknown" for unrecognized
          const fullName = det.name || det.student_id || '';
          const label = det.user_id
            ? fullName.split(' ')[0].slice(0, 10)
            : 'Unknown';
          const staleFrames = (det as any).staleFrames ?? 0;

          return (
            <AnimatedDetectionBox
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

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  box: {
    position: 'absolute',
    borderWidth: 2,
    borderRadius: 2,
  },
  labelAnchor: {
    position: 'absolute',
    width: 80,
    marginLeft: -40,
    alignItems: 'center',
  },
  labelText: {
    fontSize: 7,
    fontWeight: '700',
    textAlign: 'center',
  },
  labelStroke: {
    color: '#000000',
    textShadowColor: '#000000',
    textShadowOffset: { width: 0.4, height: 0.4 },
    textShadowRadius: 0.8,
  },
  labelFill: {
    position: 'absolute',
  },
  unknownBadge: {
    position: 'absolute',
    bottom: 8,
    right: 8,
    backgroundColor: 'rgba(239,68,68,0.18)',
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
