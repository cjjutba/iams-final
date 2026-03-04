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
