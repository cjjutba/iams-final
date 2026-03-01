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
}> = ({ detection, scaleInfo }) => {
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
  const borderColor = detection.user_id ? '#00C853' : '#FFD600';
  const label = detection.name || detection.student_id || (detection.user_id?.slice(0, 8) ?? '');
  const simText = detection.similarity != null ? ` ${(detection.similarity * 100).toFixed(0)}%` : '';

  return (
    <Animated.View style={[styles.box, { left, top, width, height, borderColor, opacity }]}>
      <View style={[styles.labelContainer, { backgroundColor: borderColor }]}>
        <Text style={styles.labelText}>{label}{simText}</Text>
      </View>
    </Animated.View>
  );
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const DetectionOverlay: React.FC<DetectionOverlayProps> = React.memo(
  ({ detections, videoWidth, videoHeight, containerWidth, containerHeight }) => {
    const scaleInfo = useMemo(
      () => computeScale(videoWidth, videoHeight, containerWidth, containerHeight),
      [videoWidth, videoHeight, containerWidth, containerHeight],
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
  labelContainer: {
    position: 'absolute',
    top: -20,
    left: -1,
    paddingHorizontal: 4,
    paddingVertical: 1,
    borderRadius: 2,
  },
  labelText: {
    color: '#000',
    fontSize: 11,
    fontWeight: '600',
  },
});
