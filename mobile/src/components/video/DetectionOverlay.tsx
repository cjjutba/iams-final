/**
 * Detection Overlay
 *
 * Renders face detection bounding boxes on top of RTCView / video.
 * Uses React Native's Animated API for smooth interpolation between
 * detection frames — boxes glide to new positions instead of jumping.
 *
 * The box and its name label are rendered as **separate** absolutely-
 * positioned Views (siblings in the overlay). This avoids Android's
 * overflow clipping: the label is never a child of the narrow box,
 * so its width isn't constrained by the tiny face-crop rectangle.
 */

import React, { useRef, useEffect, useMemo, useState } from 'react';
import { View, Text, Animated, Easing, StyleSheet, Platform } from 'react-native';
import {
  TrackAnimationEngine,
  FusedTrack,
  AnimatedTrack,
} from '../../engines/TrackAnimationEngine';

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
  /** Track ID from edge device (used for identity mapping). */
  track_id?: string;
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

/** Duration for position interpolation (ms). Should roughly match the
 *  interval between detection updates (~100ms at 10 FPS). */
const INTERPOLATION_DURATION = 100;

function getDetectionColor(userId: string | null): string {
  return userId ? COLOR_RECOGNIZED : COLOR_UNKNOWN;
}

// ---------------------------------------------------------------------------
// AnimatedDetectionBox — smooth position interpolation
// ---------------------------------------------------------------------------

interface BoxProps {
  bbox: DetectionBBox;
  userId: string | null;
  label: string;
  staleFrames: number;
  scaleInfo: ScaleInfo;
}

const AnimatedDetectionBox: React.FC<BoxProps> = React.memo(({
  bbox,
  userId,
  label,
  staleFrames,
  scaleInfo,
}) => {
  const { scale, offsetX, offsetY } = scaleInfo;

  const targetLeft = bbox.x * scale + offsetX;
  const targetTop = bbox.y * scale + offsetY;
  const targetWidth = bbox.width * scale;
  const targetHeight = bbox.height * scale;
  const borderColor = getDetectionColor(userId);
  const targetOpacity = staleFrames > 0 ? 0.3 : 1;
  const hasLabel = label.length > 0;

  // Label position (centered above box)
  const targetLabelLeft = targetLeft + targetWidth / 2;
  const targetLabelTop = Math.max(0, targetTop - LABEL_OFFSET);

  // Animated values — initialized to target on first render
  const anim = useRef({
    left: new Animated.Value(targetLeft),
    top: new Animated.Value(targetTop),
    width: new Animated.Value(targetWidth),
    height: new Animated.Value(targetHeight),
    opacity: new Animated.Value(targetOpacity),
    labelLeft: new Animated.Value(targetLabelLeft),
    labelTop: new Animated.Value(targetLabelTop),
  }).current;

  const isFirstRender = useRef(true);

  useEffect(() => {
    if (isFirstRender.current) {
      // First render: snap to position (no animation)
      isFirstRender.current = false;
      return;
    }

    // Animate smoothly to new position
    Animated.parallel([
      Animated.timing(anim.left, {
        toValue: targetLeft,
        duration: INTERPOLATION_DURATION,
        easing: Easing.linear,
        useNativeDriver: false,
      }),
      Animated.timing(anim.top, {
        toValue: targetTop,
        duration: INTERPOLATION_DURATION,
        easing: Easing.linear,
        useNativeDriver: false,
      }),
      Animated.timing(anim.width, {
        toValue: targetWidth,
        duration: INTERPOLATION_DURATION,
        easing: Easing.linear,
        useNativeDriver: false,
      }),
      Animated.timing(anim.height, {
        toValue: targetHeight,
        duration: INTERPOLATION_DURATION,
        easing: Easing.linear,
        useNativeDriver: false,
      }),
      Animated.timing(anim.opacity, {
        toValue: targetOpacity,
        duration: 200,
        easing: Easing.linear,
        useNativeDriver: false,
      }),
      Animated.timing(anim.labelLeft, {
        toValue: targetLabelLeft,
        duration: INTERPOLATION_DURATION,
        easing: Easing.linear,
        useNativeDriver: false,
      }),
      Animated.timing(anim.labelTop, {
        toValue: targetLabelTop,
        duration: INTERPOLATION_DURATION,
        easing: Easing.linear,
        useNativeDriver: false,
      }),
    ]).start();
  }, [targetLeft, targetTop, targetWidth, targetHeight, targetOpacity, targetLabelLeft, targetLabelTop]);

  return (
    <>
      {/* Bounding box */}
      <Animated.View
        style={[
          styles.box,
          {
            left: anim.left,
            top: anim.top,
            width: anim.width,
            height: anim.height,
            borderColor,
            opacity: anim.opacity,
          },
        ]}
      />
      {/* Name label (separate element — not clipped by box width) */}
      {hasLabel && (
        <Animated.View
          style={[
            styles.labelAnchor,
            {
              left: anim.labelLeft,
              top: anim.labelTop,
              opacity: anim.opacity,
            },
          ]}
        >
          <Text style={[styles.labelText, { color: borderColor }]} numberOfLines={1}>
            {label}
          </Text>
        </Animated.View>
      )}
    </>
  );
});
AnimatedDetectionBox.displayName = 'AnimatedDetectionBox';

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
DetectionOverlay.displayName = 'DetectionOverlay';

// ---------------------------------------------------------------------------
// FusedDetectionOverlay — uses TrackAnimationEngine for smooth 30 FPS boxes
// ---------------------------------------------------------------------------

interface FusedDetectionOverlayProps {
  tracks: FusedTrack[];
  videoWidth: number;
  videoHeight: number;
  containerWidth: number;
  containerHeight: number;
  resizeMode?: 'contain' | 'cover';
}

const FusedBox = React.memo(
  ({ track, scaleInfo }: { track: AnimatedTrack; scaleInfo: ScaleInfo }) => {
    const { scale, offsetX, offsetY } = scaleInfo;
    const isRecognized = track.userId != null;
    const color = isRecognized ? COLOR_RECOGNIZED : COLOR_UNKNOWN;
    const label = track.name
      ? `${track.name.split(' ')[0].substring(0, 10)} (${Math.round((track.similarity ?? 0) * 100)}%)`
      : 'Unknown';

    // Scale detection-space coords to screen-space using Animated arithmetic.
    // `scale` and offsets are plain numbers; track.x/y/w/h are Animated.Values.
    const animatedStyle = {
      position: 'absolute' as const,
      left: Animated.add(Animated.multiply(track.x, scale), offsetX),
      top: Animated.add(Animated.multiply(track.y, scale), offsetY),
      width: Animated.multiply(track.w, scale),
      height: Animated.multiply(track.h, scale),
      borderWidth: 2,
      borderColor: color,
      borderRadius: 3,
      opacity: track.opacity,
    };

    const labelStyle = {
      position: 'absolute' as const,
      left: Animated.add(Animated.multiply(track.x, scale), offsetX),
      top: Animated.add(
        Animated.add(Animated.multiply(track.y, scale), offsetY),
        -16,
      ),
      opacity: track.opacity,
    };

    return (
      <>
        <Animated.View style={animatedStyle} />
        {track.missedFrames === 0 && (
          <Animated.View style={labelStyle}>
            <Text style={[styles.labelText, { color }]}>{label}</Text>
          </Animated.View>
        )}
      </>
    );
  },
);
FusedBox.displayName = 'FusedBox';

export const FusedDetectionOverlay: React.FC<FusedDetectionOverlayProps> =
  React.memo(
    ({
      tracks,
      videoWidth,
      videoHeight,
      containerWidth,
      containerHeight,
      resizeMode = 'contain',
    }) => {
      const engineRef = useRef(new TrackAnimationEngine());
      const [animatedTracks, setAnimatedTracks] = useState<AnimatedTrack[]>([]);

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

      useEffect(() => {
        const updated = engineRef.current.update(tracks);
        setAnimatedTracks(updated);
      }, [tracks]);

      // Cleanup on unmount
      useEffect(() => {
        return () => engineRef.current.clear();
      }, []);

      if (
        !animatedTracks.length ||
        containerWidth === 0 ||
        containerHeight === 0
      ) {
        return null;
      }

      const unknownCount = animatedTracks.filter(
        (t) => t.userId == null,
      ).length;

      return (
        <View style={styles.overlay} pointerEvents="none">
          {animatedTracks.map((track) => (
            <FusedBox
              key={track.trackId}
              track={track}
              scaleInfo={scaleInfo}
            />
          ))}
          <UnknownBadge count={unknownCount} />
        </View>
      );
    },
  );
FusedDetectionOverlay.displayName = 'FusedDetectionOverlay';

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
    transform: [{ translateX: -30 }],
  },
  labelText: {
    fontSize: 7,
    fontWeight: '700',
    textAlign: 'center',
    textShadowColor: 'rgba(0,0,0,0.8)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 2,
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
