/**
 * FaceScanCamera — ML-powered face registration with real-time detection.
 *
 * Uses VisionCamera + Google ML Kit to detect faces in real-time.
 * Captures photos only when a valid face is detected at a distinct angle.
 * Guides the user through 5 angle buckets: center, left, right, up, down.
 *
 * Quality gates ensure every captured image has:
 * - A face present and large enough (>30% of frame)
 * - Both eyes open
 * - Face centered in the oval guide
 * - A distinct head angle not yet captured
 */

import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import {
  View,
  StyleSheet,
  Animated,
  Dimensions,
  Vibration,
  StatusBar,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  Camera,
  useCameraDevice,
  useFrameProcessor,
} from 'react-native-vision-camera';
import { Worklets } from 'react-native-worklets-core';
// Import directly from FaceDetector submodule to avoid Camera.tsx which requires Skia
import {
  useFaceDetector,
  type Face,
  type FrameFaceDetectionOptions,
} from 'react-native-vision-camera-face-detector/lib/module/FaceDetector';
import Svg, { Circle, Ellipse } from 'react-native-svg';
import { Check } from 'lucide-react-native';
import { config, strings } from '../../constants';
import { Text } from '../ui';

// ── Types ──────────────────────────────────────────────────────

interface FaceScanCameraProps {
  /** Called with array of captured image file:// URIs when scanning is complete. */
  onComplete: (images: string[]) => void;
  /** Optional cancel handler (e.g. back button). */
  onCancel?: () => void;
  /** Number of angle buckets to capture. Default: config.REQUIRED_FACE_IMAGES (5). */
  captureCount?: number;
}

type ScanPhase = 'scanning' | 'complete' | 'error';

type AngleBucket = 'center' | 'left' | 'right' | 'up' | 'down';

type DetectionState = 'no_face' | 'adjusting' | 'ready';

// ── Constants ──────────────────────────────────────────────────

const ANGLE_BUCKETS: AngleBucket[] = ['center', 'left', 'right', 'up', 'down'];

// Head pose thresholds (degrees)
const CENTER_YAW_THRESHOLD = 10;
const CENTER_PITCH_THRESHOLD = 10;
const SIDE_YAW_THRESHOLD = 20;
const VERTICAL_PITCH_THRESHOLD = 15;

// Quality gate thresholds
const MIN_FACE_SIZE_RATIO = 0.30;  // Face width must be >30% of frame
const MIN_EYE_OPEN_PROB = 0.5;
const FACE_CENTER_TOLERANCE = 0.20; // 20% tolerance from frame center

// Face detection options for ML Kit
const FACE_DETECTION_OPTIONS: FrameFaceDetectionOptions = {
  performanceMode: 'accurate',
  landmarkMode: 'all',
  classificationMode: 'all',
  contourMode: 'none',
  minFaceSize: 0.15,
  trackingEnabled: false,
};

// ── Dimensions ─────────────────────────────────────────────────

const { width: SW, height: SH } = Dimensions.get('window');

// SVG overlay sizing
const RING_SIZE = SW * 0.72;
const SVG_CENTER = RING_SIZE / 2;
const RING_R = RING_SIZE / 2 - 8;
const OVAL_RX = SW * 0.24;
const OVAL_RY = SW * 0.34;
const CIRCUMFERENCE = 2 * Math.PI * RING_R;

// Oval colors by detection state
const OVAL_COLORS: Record<DetectionState, string> = {
  no_face: 'rgba(255,255,255,0.2)',
  adjusting: 'rgba(255,255,255,0.6)',
  ready: 'rgba(34,197,94,0.7)',
};

// ── Animated SVG ───────────────────────────────────────────────

const AnimatedCircle = Animated.createAnimatedComponent(Circle);
const AnimatedEllipse = Animated.createAnimatedComponent(Ellipse);

// ── Helpers ────────────────────────────────────────────────────

/**
 * Determine which angle bucket a face belongs to based on head pose.
 * Returns null if the face is in an ambiguous zone between buckets.
 */
function classifyAngle(yaw: number, pitch: number): AngleBucket | null {
  const absYaw = Math.abs(yaw);
  const absPitch = Math.abs(pitch);

  // Center: both yaw and pitch within threshold
  if (absYaw <= CENTER_YAW_THRESHOLD && absPitch <= CENTER_PITCH_THRESHOLD) {
    return 'center';
  }

  // Determine if yaw or pitch is the dominant deviation
  if (absYaw > absPitch) {
    // Horizontal is dominant
    if (absYaw >= SIDE_YAW_THRESHOLD) {
      return yaw > 0 ? 'left' : 'right';
    }
  } else {
    // Vertical is dominant
    if (absPitch >= VERTICAL_PITCH_THRESHOLD) {
      return pitch < 0 ? 'up' : 'down';
    }
  }

  // In a dead zone between thresholds
  return null;
}

/**
 * Get the next uncaptured bucket instruction text.
 */
function getInstruction(
  captured: Set<AngleBucket>,
  detectionState: DetectionState,
): string {
  if (detectionState === 'no_face') {
    return strings.register.faceInstructions.noFace;
  }

  // Find next uncaptured bucket in order
  for (const bucket of ANGLE_BUCKETS) {
    if (!captured.has(bucket)) {
      return strings.register.faceInstructions[bucket];
    }
  }

  return strings.register.faceInstructions.adjusting;
}

// ── Component ──────────────────────────────────────────────────

export const FaceScanCamera: React.FC<FaceScanCameraProps> = ({
  onComplete,
  captureCount = config.REQUIRED_FACE_IMAGES,
}) => {
  const insets = useSafeAreaInsets();
  const device = useCameraDevice('front');
  const cameraRef = useRef<any>(null);

  // Face detector plugin (uses VisionCamera frame processor API directly)
  const { detectFaces, stopListeners } = useFaceDetector(FACE_DETECTION_OPTIONS);

  // Phase & detection state
  const [phase, setPhase] = useState<ScanPhase>('scanning');
  const [capturedCount, setCapturedCount] = useState(0);
  const [detectionState, setDetectionState] = useState<DetectionState>('no_face');
  const [instruction, setInstruction] = useState<string>(strings.register.faceInstructions.noFace);

  // Refs for capture logic (avoids stale closures in callbacks)
  const imagesRef = useRef<string[]>([]);
  const capturedBucketsRef = useRef<Set<AngleBucket>>(new Set());
  const isCapturingRef = useRef(false);
  const completedRef = useRef(false);
  const lastCaptureTimeRef = useRef(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Animations
  const progressAnim = useRef(new Animated.Value(0)).current;
  const flashAnim = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(0.5)).current;
  const checkAnim = useRef(new Animated.Value(0)).current;

  // Animated strokeDashoffset for the progress ring
  const dashOffset = progressAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [CIRCUMFERENCE, 0],
  });

  // ── Cleanup ────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      stopListeners();
    };
  }, [stopListeners]);

  // ── Pulse animation ────────────────────────────────────────

  useEffect(() => {
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 0.8, duration: 1000, useNativeDriver: false }),
        Animated.timing(pulseAnim, { toValue: 0.5, duration: 1000, useNativeDriver: false }),
      ]),
    );
    pulse.start();
    return () => pulse.stop();
  }, [pulseAnim]);

  // ── Safety timeout ─────────────────────────────────────────

  useEffect(() => {
    const safetyTimeout = setTimeout(() => {
      if (completedRef.current) return;

      const count = imagesRef.current.length;
      if (count >= 3) {
        // We have at least the backend minimum (3), proceed
        completedRef.current = true;
        setPhase('complete');

        Animated.timing(progressAnim, {
          toValue: 1,
          duration: 300,
          useNativeDriver: false,
        }).start();

        Animated.spring(checkAnim, {
          toValue: 1,
          friction: 6,
          tension: 80,
          useNativeDriver: true,
        }).start();

        timeoutRef.current = setTimeout(() => onComplete(imagesRef.current), 1200);
      } else {
        setPhase('error');
      }
    }, config.FACE_SCAN_TIMEOUT_MS);

    return () => clearTimeout(safetyTimeout);
  }, [onComplete, progressAnim, checkAnim]);

  // ── Capture a photo ────────────────────────────────────────

  const capturePhoto = useCallback(async (bucket: AngleBucket) => {
    if (!cameraRef.current || isCapturingRef.current || completedRef.current) return;

    isCapturingRef.current = true;
    try {
      const photo = await cameraRef.current.takePhoto({ flash: 'off' });

      if (photo?.path && !completedRef.current) {
        const uri = `file://${photo.path}`;
        imagesRef.current.push(uri);
        capturedBucketsRef.current.add(bucket);
        lastCaptureTimeRef.current = Date.now();

        const count = imagesRef.current.length;
        const progress = count / captureCount;

        setCapturedCount(count);

        // Animate progress ring
        Animated.timing(progressAnim, {
          toValue: progress,
          duration: 300,
          useNativeDriver: false,
        }).start();

        // Flash effect
        flashAnim.setValue(0.25);
        Animated.timing(flashAnim, {
          toValue: 0,
          duration: 250,
          useNativeDriver: false,
        }).start();

        // Haptic feedback
        Vibration.vibrate(10);

        // Check completion
        if (count >= captureCount) {
          completedRef.current = true;
          setPhase('complete');

          Animated.spring(checkAnim, {
            toValue: 1,
            friction: 6,
            tension: 80,
            useNativeDriver: true,
          }).start();

          timeoutRef.current = setTimeout(() => {
            onComplete(imagesRef.current);
          }, 1200);
        }
      }
    } catch {
      // Silent fail — will retry on next detection frame
    }
    isCapturingRef.current = false;
  }, [captureCount, onComplete, progressAnim, flashAnim, checkAnim]);

  // ── Face detection callback (runs on JS thread) ───────────

  const handleFacesDetected = useCallback((faces: Face[]) => {
    if (completedRef.current || isCapturingRef.current) return;

    // No face detected
    if (!faces || faces.length === 0) {
      setDetectionState('no_face');
      setInstruction(strings.register.faceInstructions.noFace);
      return;
    }

    const face = faces[0]; // Use first (largest) face
    const bounds = face.bounds;

    // Quality gate 1: Face size (bounding box width > 30% of frame)
    const faceSizeRatio = bounds.width / SW;
    if (faceSizeRatio < MIN_FACE_SIZE_RATIO) {
      setDetectionState('adjusting');
      setInstruction('Move closer');
      return;
    }

    // Quality gate 2: Eyes open
    const leftEyeOpen = face.leftEyeOpenProbability ?? 1;
    const rightEyeOpen = face.rightEyeOpenProbability ?? 1;
    if (leftEyeOpen < MIN_EYE_OPEN_PROB || rightEyeOpen < MIN_EYE_OPEN_PROB) {
      setDetectionState('adjusting');
      setInstruction('Open your eyes');
      return;
    }

    // Quality gate 3: Face centered in frame
    const faceCenterX = bounds.x + bounds.width / 2;
    const faceCenterY = bounds.y + bounds.height / 2;
    const frameCenterX = SW / 2;
    const frameCenterY = SH / 2;
    const offsetX = Math.abs(faceCenterX - frameCenterX) / SW;
    const offsetY = Math.abs(faceCenterY - frameCenterY) / SH;

    if (offsetX > FACE_CENTER_TOLERANCE || offsetY > FACE_CENTER_TOLERANCE) {
      setDetectionState('adjusting');
      setInstruction('Center your face');
      return;
    }

    // Determine angle bucket from head pose
    const yaw = face.yawAngle ?? 0;
    const pitch = face.pitchAngle ?? 0;
    const bucket = classifyAngle(yaw, pitch);

    if (!bucket) {
      // In dead zone between thresholds
      setDetectionState('adjusting');
      setInstruction(getInstruction(capturedBucketsRef.current, 'adjusting'));
      return;
    }

    // Center must be captured first
    if (bucket !== 'center' && !capturedBucketsRef.current.has('center')) {
      setDetectionState('adjusting');
      setInstruction(strings.register.faceInstructions.center);
      return;
    }

    // Already captured this bucket
    if (capturedBucketsRef.current.has(bucket)) {
      setDetectionState('adjusting');
      setInstruction(getInstruction(capturedBucketsRef.current, 'adjusting'));
      return;
    }

    // Quality gate 4: Capture cooldown (prevents blur)
    const now = Date.now();
    if (now - lastCaptureTimeRef.current < config.FACE_CAPTURE_COOLDOWN_MS) {
      setDetectionState('adjusting');
      setInstruction(strings.register.faceInstructions.adjusting);
      return;
    }

    // All gates passed — capture!
    setDetectionState('ready');
    capturePhoto(bucket);
  }, [capturePhoto]);

  // ── Retry from error ───────────────────────────────────────

  const handleRetry = useCallback(() => {
    imagesRef.current = [];
    capturedBucketsRef.current.clear();
    isCapturingRef.current = false;
    completedRef.current = false;
    lastCaptureTimeRef.current = 0;
    setCapturedCount(0);
    setDetectionState('no_face');
    setInstruction(strings.register.faceInstructions.noFace);
    progressAnim.setValue(0);
    checkAnim.setValue(0);
    setPhase('scanning');
  }, [progressAnim, checkAnim]);

  // ── Frame processor (worklet → JS bridge) ─────────────────

  const runOnJs = useMemo(
    () => Worklets.createRunOnJS(handleFacesDetected),
    [handleFacesDetected],
  );

  const frameProcessor = useFrameProcessor((frame) => {
    'worklet';
    const faces = detectFaces(frame);
    runOnJs(faces);
  }, [detectFaces, runOnJs]);

  // ── Render ─────────────────────────────────────────────────

  const isComplete = phase === 'complete';
  const isError = phase === 'error';

  // No camera device available
  if (!device) {
    return (
      <View style={s.root}>
        <StatusBar barStyle="light-content" />
        <View style={s.noCameraContainer}>
          <Text variant="body" color="#FFFFFF" align="center">
            No front camera available
          </Text>
        </View>
      </View>
    );
  }

  // Determine oval color based on detection state
  const ovalColor = isComplete || isError
    ? OVAL_COLORS.no_face
    : OVAL_COLORS[detectionState];

  return (
    <View style={s.root}>
      <StatusBar barStyle="light-content" />

      <Camera
        ref={cameraRef}
        style={s.camera}
        device={device}
        isActive={phase === 'scanning'}
        photo={true}
        frameProcessor={frameProcessor}
        pixelFormat="yuv"
      />

      <View style={s.overlay} pointerEvents="box-none">
        {/* Top instruction */}
        <View style={[s.topArea, { paddingTop: insets.top + 24 }]}>
          <Text variant="h3" weight="600" color="#fff" align="center" style={s.instructionText}>
            {isComplete
              ? strings.register.faceInstructions.complete
              : isError
                ? strings.register.faceInstructions.failed
                : instruction}
          </Text>
          {!isComplete && !isError && phase === 'scanning' && (
            <Text variant="body" color="rgba(255,255,255,0.5)" align="center" style={s.subtext}>
              Keep your face visible
            </Text>
          )}
        </View>

        {/* Center: SVG oval + progress ring OR success checkmark */}
        <View style={s.centerArea}>
          {isComplete ? (
            <Animated.View
              style={[
                s.checkContainer,
                {
                  transform: [{ scale: checkAnim }],
                  opacity: checkAnim,
                },
              ]}
            >
              <View style={s.checkCircle}>
                <Check size={64} color="#FFFFFF" strokeWidth={3} />
              </View>
            </Animated.View>
          ) : (
            <Svg width={RING_SIZE} height={RING_SIZE}>
              {/* Face oval guide — color changes based on detection state */}
              <AnimatedEllipse
                cx={SVG_CENTER}
                cy={SVG_CENTER}
                rx={OVAL_RX}
                ry={OVAL_RY}
                stroke={ovalColor}
                strokeWidth={2.5}
                fill="none"
                opacity={detectionState === 'no_face' ? pulseAnim : 1}
              />
              {/* Progress ring */}
              <AnimatedCircle
                cx={SVG_CENTER}
                cy={SVG_CENTER}
                r={RING_R}
                stroke="#FFFFFF"
                strokeWidth={3}
                fill="none"
                strokeDasharray={`${CIRCUMFERENCE}`}
                strokeDashoffset={dashOffset}
                strokeLinecap="round"
                rotation={-90}
                origin={`${SVG_CENTER}, ${SVG_CENTER}`}
              />
            </Svg>
          )}
        </View>

        {/* Bottom info */}
        <View style={[s.bottomArea, { paddingBottom: Math.max(insets.bottom, 24) + 16 }]}>
          {isError ? (
            <ErrorRetry onRetry={handleRetry} />
          ) : (
            !isComplete && (
              <Text variant="caption" color="rgba(255,255,255,0.4)" align="center">
                {capturedCount} of {captureCount}
              </Text>
            )
          )}
        </View>

        {/* Flash overlay */}
        <Animated.View
          style={[s.flash, { opacity: flashAnim }]}
          pointerEvents="none"
        />
      </View>
    </View>
  );
};

// ── Error Retry Sub-component ─────────────────────────────────

const ErrorRetry: React.FC<{ onRetry: () => void }> = ({ onRetry }) => {
  return (
    <View style={s.retryContainer}>
      <Text
        variant="body"
        color="#FFFFFF"
        align="center"
        style={s.retryText}
        onPress={onRetry}
      >
        Tap to retry
      </Text>
    </View>
  );
};

// ── Styles ────────────────────────────────────────────────────

const s = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#000',
  },
  camera: {
    flex: 1,
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'space-between',
  },
  topArea: {
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  instructionText: {
    textShadowColor: 'rgba(0,0,0,0.8)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 6,
  },
  subtext: {
    marginTop: 6,
    textShadowColor: 'rgba(0,0,0,0.6)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 4,
  },
  centerArea: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkContainer: {
    width: RING_SIZE,
    height: RING_SIZE,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: 'rgba(34,197,94,0.85)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  bottomArea: {
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  flash: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#FFFFFF',
  },
  noCameraContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  retryContainer: {
    paddingVertical: 12,
    paddingHorizontal: 32,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.3)',
  },
  retryText: {
    textShadowColor: 'rgba(0,0,0,0.6)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 4,
  },
});
