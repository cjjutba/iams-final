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

// Height reserved for the name label above the bounding box.
const LABEL_HEIGHT = 22;

// ---------------------------------------------------------------------------
// Confidence-based color tiers
// ---------------------------------------------------------------------------

/** High confidence: similarity >= 0.8 */
const COLOR_HIGH = '#22C55E';
/** Medium confidence: similarity >= 0.6 */
const COLOR_MEDIUM = '#06B6D4';
/** Low confidence / unknown: similarity < 0.6 or null */
const COLOR_LOW = '#EAB308';

/**
 * Determine bounding box border color based on a 3-tier confidence system.
 * - similarity >= 0.8  -> green  (high confidence match)
 * - similarity >= 0.6  -> cyan   (acceptable match)
 * - similarity < 0.6 or null (unknown face) -> yellow
 */
function getConfidenceColor(similarity: number | null): string {
  if (similarity == null) return COLOR_LOW;
  if (similarity >= 0.8) return COLOR_HIGH;
  if (similarity >= 0.6) return COLOR_MEDIUM;
  return COLOR_LOW;
}

/**
 * Background color for the label container, matched to the confidence tier.
 */
function getLabelBackground(similarity: number | null): string {
  if (similarity == null) return 'rgba(60,40,0,0.85)';
  if (similarity >= 0.8) return 'rgba(0,0,0,0.80)';
  if (similarity >= 0.6) return 'rgba(0,20,30,0.80)';
  return 'rgba(60,40,0,0.85)';
}

interface TrackedBoxProps {
  bbox: DetectionBBox;
  similarity: number | null;
  label: string;
  simText: string;
  staleFrames: number;
  scaleInfo: ScaleInfo;
}

const AnimatedDetectionBox: React.FC<TrackedBoxProps> = ({
  bbox,
  similarity,
  label,
  simText,
  staleFrames,
  scaleInfo,
}) => {
  const { scale, offsetX, offsetY } = scaleInfo;

  const hasLabel = label.length > 0;

  // The wrapper includes the label area above the box so that everything
  // stays inside the Animated.View bounds (avoids Android overflow clipping).
  const boxLeft = bbox.x * scale + offsetX;
  const boxTop = bbox.y * scale + offsetY;
  const boxWidth = bbox.width * scale;
  const boxHeight = bbox.height * scale;

  const targetLeft = boxLeft;
  const targetTop = hasLabel ? boxTop - LABEL_HEIGHT : boxTop;
  const targetWidth = boxWidth;
  const targetHeight = hasLabel ? boxHeight + LABEL_HEIGHT : boxHeight;

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

  const borderColor = getConfidenceColor(similarity);
  const labelBg = getLabelBackground(similarity);

  return (
    <Animated.View style={[styles.wrapper, animatedStyle]}>
      {/* Label sits inside the wrapper, above the box border area */}
      {hasLabel && (
        <View
          style={[
            styles.labelContainer,
            { backgroundColor: labelBg },
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
      {/* Box border fills remaining space */}
      <View style={[styles.box, { borderColor }]} />
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
              similarity={det.similarity}
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
  wrapper: {
    position: 'absolute',
  },
  box: {
    flex: 1,
    borderWidth: 2,
    borderRadius: 2,
  },
  labelContainer: {
    alignSelf: 'flex-start',
    paddingHorizontal: 5,
    paddingVertical: 2,
    borderRadius: 3,
    marginBottom: 1,
  },
  labelText: {
    fontSize: 11,
    fontWeight: '800',
  },
  unknownBadge: {
    position: 'absolute',
    bottom: 8,
    right: 8,
    backgroundColor: 'rgba(234,179,8,0.18)',
    borderWidth: 1,
    borderColor: COLOR_LOW,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  unknownBadgeText: {
    color: COLOR_LOW,
    fontSize: 11,
    fontWeight: '600',
  },
});
