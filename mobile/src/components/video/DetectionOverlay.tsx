/**
 * Detection Overlay
 *
 * Renders face detection bounding boxes and labels as absolutely-positioned
 * Views on top of the video player. Scales detection coordinates from the
 * backend's processing resolution to the on-screen container dimensions,
 * accounting for letterboxing when the video uses `contain` mode.
 */

import React, { useEffect, useRef, useMemo } from 'react';
import { Animated, View, Text, StyleSheet } from 'react-native';

const FADE_DURATION = 200;

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
}

// ---------------------------------------------------------------------------
// Coordinate scaling (handles letterboxing)
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
): ScaleInfo {
  if (videoW <= 0 || videoH <= 0 || containerW <= 0 || containerH <= 0) {
    return { scale: 1, offsetX: 0, offsetY: 0 };
  }

  const videoAspect = videoW / videoH;
  const containerAspect = containerW / containerH;

  let scale: number;
  let offsetX = 0;
  let offsetY = 0;

  if (videoAspect > containerAspect) {
    // Video wider than container — letterbox top/bottom
    scale = containerW / videoW;
    const scaledHeight = videoH * scale;
    offsetY = (containerH - scaledHeight) / 2;
  } else {
    // Video taller than container — pillarbox left/right
    scale = containerH / videoH;
    const scaledWidth = videoW * scale;
    offsetX = (containerW - scaledWidth) / 2;
  }

  return { scale, offsetX, offsetY };
}

// ---------------------------------------------------------------------------
// DetectionBox (animated fade-in)
// ---------------------------------------------------------------------------

const DetectionBox: React.FC<{
  detection: DetectionItem;
  scaleInfo: ScaleInfo;
}> = React.memo(({ detection, scaleInfo }) => {
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(opacity, {
      toValue: 1,
      duration: FADE_DURATION,
      useNativeDriver: true,
    }).start();
  }, []);

  const { scale, offsetX, offsetY } = scaleInfo;
  const left = detection.bbox.x * scale + offsetX;
  const top = detection.bbox.y * scale + offsetY;
  const width = detection.bbox.width * scale;
  const height = detection.bbox.height * scale;

  const isKnown = !!detection.user_id;
  const borderColor = isKnown ? '#00E676' : '#FFD600';
  const labelBg = isKnown ? 'rgba(0,0,0,0.72)' : 'rgba(60,40,0,0.80)';

  const label = detection.name || detection.student_id || (detection.user_id?.slice(0, 8) ?? '');
  const simText = detection.similarity != null ? ` ${(detection.similarity * 100).toFixed(0)}%` : '';

  return (
    <Animated.View style={[styles.box, { left, top, width, height, borderColor, opacity }]}>
      <View style={[styles.labelContainer, { backgroundColor: labelBg }]}>
        <Text style={[styles.labelText, { color: borderColor }]} numberOfLines={1}>
          {label}{simText}
        </Text>
      </View>
    </Animated.View>
  );
}, (prev, next) =>
  prev.detection.bbox.x === next.detection.bbox.x &&
  prev.detection.bbox.y === next.detection.bbox.y &&
  prev.detection.bbox.width === next.detection.bbox.width &&
  prev.detection.bbox.height === next.detection.bbox.height &&
  prev.detection.name === next.detection.name &&
  prev.detection.similarity === next.detection.similarity &&
  prev.scaleInfo.scale === next.scaleInfo.scale &&
  prev.scaleInfo.offsetX === next.scaleInfo.offsetX &&
  prev.scaleInfo.offsetY === next.scaleInfo.offsetY,
);

// ---------------------------------------------------------------------------
// UnknownBadge
// ---------------------------------------------------------------------------

const UnknownBadge: React.FC<{ count: number }> = React.memo(({ count }) => {
  if (count === 0) return null;
  return (
    <View style={styles.unknownBadge}>
      <Text style={styles.unknownBadgeText}>
        {count} unrecognized
      </Text>
    </View>
  );
});

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const DetectionOverlay: React.FC<DetectionOverlayProps> = React.memo(
  ({ detections, videoWidth, videoHeight, containerWidth, containerHeight }) => {
    const scaleInfo = useMemo(
      () => computeScale(videoWidth, videoHeight, containerWidth, containerHeight),
      [videoWidth, videoHeight, containerWidth, containerHeight],
    );

    const unknownCount = useMemo(
      () => detections.filter(d => !d.user_id).length,
      [detections],
    );

    if (!detections.length || containerWidth === 0 || containerHeight === 0) {
      return null;
    }

    return (
      <View style={StyleSheet.absoluteFill} pointerEvents="none">
        {detections.map((det, i) => (
          <DetectionBox
            key={det.user_id || `unknown-${i}`}
            detection={det}
            scaleInfo={scaleInfo}
          />
        ))}
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
    borderWidth: 3,
    borderRadius: 3,
  },
  labelContainer: {
    position: 'absolute',
    top: -22,
    left: -1,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 2,
  },
  labelText: {
    fontSize: 11,
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
