/**
 * FaceScanCamera — Step-by-step guided face registration.
 *
 * 5-step flow: user follows an instruction per step and taps a capture button.
 * Face detection enables/disables the button and colors the oval border green.
 * Dark mask with oval cutout, progress dots, shutter button.
 * After all captures, a review phase lets users preview and retake photos.
 *
 * Key design: frameProcessor + runOnJs are completely STABLE (never recreated)
 * to avoid gray camera flash on retakes. All mutable state is accessed via refs.
 */

import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import {
  View,
  StyleSheet,
  Animated,
  Dimensions,
  Vibration,
  StatusBar,
  TouchableOpacity,
  Image,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  Camera,
  useCameraDevice,
  useCameraPermission,
  useFrameProcessor,
} from 'react-native-vision-camera';
import { Worklets } from 'react-native-worklets-core';
import {
  useFaceDetector,
  type Face,
  type FrameFaceDetectionOptions,
} from 'react-native-vision-camera-face-detector/lib/module/FaceDetector';
import Svg, { Path, Ellipse } from 'react-native-svg';
import { Check, RotateCcw } from 'lucide-react-native';
import { config, strings } from '../../constants';
import { Text } from '../ui';
import { FaceQualityBar } from './FaceQualityBar';
import { AngleGuide } from './AngleGuide';
import { StepIndicator } from './StepIndicator';

// ── Types ──────────────────────────────────────────────────────

interface FaceScanCameraProps {
  onComplete: (images: string[]) => void;
  onCancel?: () => void;
  captureCount?: number;
}

type ScanPhase = 'scanning' | 'complete' | 'review' | 'error';

// ── Constants ──────────────────────────────────────────────────

const { width: SW, height: SH } = Dimensions.get('window');

// Oval cutout
const OVAL_RX = SW * 0.32;
const OVAL_RY = SW * 0.44;
const OVAL_CX = SW / 2;
const OVAL_CY = SH * 0.35;

const MIN_FACE_SIZE_RATIO = 0.25;

// Quality tracking thresholds
const STABILITY_THRESHOLD = 15; // Max pixel movement between frames to count as "stable"
const ALIGNMENT_TOLERANCE = 0.35; // Fraction of oval radius — face center must be within this

// ── Quality state type (used via refs for frame processor stability) ──

interface QualityState {
  faceSizeOk: boolean;
  stabilityOk: boolean;
  alignmentOk: boolean;
  eyesOpenOk: boolean;
}

const INITIAL_QUALITY: QualityState = {
  faceSizeOk: false,
  stabilityOk: false,
  alignmentOk: false,
  eyesOpenOk: false,
};

// Step instructions (maps to the 5 angle captures)
const STEP_INSTRUCTIONS = [
  strings.register.faceInstructions.center,
  strings.register.faceInstructions.left,
  strings.register.faceInstructions.right,
  strings.register.faceInstructions.up,
  strings.register.faceInstructions.down,
];

// Short labels for review thumbnails
const STEP_LABELS = ['Center', 'Left', 'Right', 'Up', 'Down'];

// Review layout — dynamic thumbnail sizing to fit screen without scrolling
const REVIEW_H_PAD = 20;
const THUMB_GAP = 10;
const THUMB_COLS = 2;
const THUMB_W = (SW - REVIEW_H_PAD * 2 - THUMB_GAP) / THUMB_COLS;

// Face detection with classification for eyes-open check
const FACE_DETECTION_OPTIONS: FrameFaceDetectionOptions = {
  performanceMode: 'fast',
  landmarkMode: 'none',
  classificationMode: 'all',
  contourMode: 'none',
  minFaceSize: 0.15,
  trackingEnabled: false,
};

// ── Mask path ──────────────────────────────────────────────────

function buildMaskPath(): string {
  const outer = `M0,0 L${SW},0 L${SW},${SH} L0,${SH} Z`;

  const k = 0.5522847498;
  const kx = OVAL_RX * k;
  const ky = OVAL_RY * k;
  const cx = OVAL_CX;
  const cy = OVAL_CY;

  const inner = [
    `M${cx},${cy - OVAL_RY}`,
    `C${cx + kx},${cy - OVAL_RY} ${cx + OVAL_RX},${cy - ky} ${cx + OVAL_RX},${cy}`,
    `C${cx + OVAL_RX},${cy + ky} ${cx + kx},${cy + OVAL_RY} ${cx},${cy + OVAL_RY}`,
    `C${cx - kx},${cy + OVAL_RY} ${cx - OVAL_RX},${cy + ky} ${cx - OVAL_RX},${cy}`,
    `C${cx - OVAL_RX},${cy - ky} ${cx - kx},${cy - OVAL_RY} ${cx},${cy - OVAL_RY}`,
    'Z',
  ].join(' ');

  return `${outer} ${inner}`;
}

const MASK_PATH = buildMaskPath();

// ── Component ──────────────────────────────────────────────────

export const FaceScanCamera: React.FC<FaceScanCameraProps> = ({
  onComplete,
  captureCount = config.REQUIRED_FACE_IMAGES,
}) => {
  const insets = useSafeAreaInsets();
  const device = useCameraDevice('front');
  const { hasPermission, requestPermission } = useCameraPermission();
  const cameraRef = useRef<any>(null);

  const { detectFaces, stopListeners } = useFaceDetector(FACE_DETECTION_OPTIONS);

  // ── State (for UI rendering) ────────────────────────────────
  const [phase, setPhase] = useState<ScanPhase>('scanning');
  const [currentStep, setCurrentStep] = useState(0);
  const [faceDetected, setFaceDetected] = useState(false);
  const [retakeIndex, setRetakeIndex] = useState<number | null>(null);
  const [images, setImages] = useState<string[]>([]);

  // ── Quality state (for UI rendering) ──
  const [quality, setQuality] = useState<QualityState>(INITIAL_QUALITY);

  // ── Refs (for stable callbacks — avoids frameProcessor recreation) ──
  const phaseRef = useRef<ScanPhase>('scanning');
  const isCapturingRef = useRef(false);
  const completedRef = useRef(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Quality tracking refs (accessed in frame callback — must NOT be useState)
  const prevFaceBoundsRef = useRef<{ x: number; y: number } | null>(null);

  // Keep phaseRef in sync
  useEffect(() => { phaseRef.current = phase; }, [phase]);

  // Animations
  const flashAnim = useRef(new Animated.Value(0)).current;
  const checkAnim = useRef(new Animated.Value(0)).current;

  // ── Cleanup ────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      stopListeners();
    };
  }, [stopListeners]);

  // ── Safety timeout (60s for manual capture) ────────────────

  useEffect(() => {
    if (phase !== 'scanning') return;

    const safetyTimeout = setTimeout(() => {
      if (completedRef.current || phaseRef.current !== 'scanning') return;

      if (images.length >= 3) {
        completedRef.current = true;
        setPhase('review');
      } else {
        setPhase('error');
      }
    }, 60000);

    return () => clearTimeout(safetyTimeout);
  }, [phase, images.length]);

  // ── Face detection — STABLE callback (no state deps) ───────
  // Uses phaseRef so it never needs to be recreated. This keeps
  // runOnJs and frameProcessor stable, preventing gray camera flash.

  const handleFacesDetected = useCallback((faces: Face[]) => {
    if (phaseRef.current !== 'scanning') return;

    if (!faces || faces.length === 0) {
      setFaceDetected(false);
      setQuality(INITIAL_QUALITY);
      prevFaceBoundsRef.current = null;
      return;
    }

    const face = faces[0];
    const { bounds } = face;

    // ── Face size ──
    const faceSizeRatio = bounds.width / SW;
    const faceSizeOk = faceSizeRatio >= MIN_FACE_SIZE_RATIO;

    // ── Eyes open (lenient threshold for angled captures) ──
    const eyesOpenOk =
      face.leftEyeOpenProbability > 0.25 &&
      face.rightEyeOpenProbability > 0.25;

    // ── Stability (compare face center with previous frame) ──
    const faceCenterX = bounds.x + bounds.width / 2;
    const faceCenterY = bounds.y + bounds.height / 2;
    let stabilityOk = false;

    if (prevFaceBoundsRef.current) {
      const dx = Math.abs(faceCenterX - prevFaceBoundsRef.current.x);
      const dy = Math.abs(faceCenterY - prevFaceBoundsRef.current.y);
      stabilityOk = dx < STABILITY_THRESHOLD && dy < STABILITY_THRESHOLD;
    }
    prevFaceBoundsRef.current = { x: faceCenterX, y: faceCenterY };

    // ── Alignment (face center within oval tolerance) ──
    const offsetX = Math.abs(faceCenterX - OVAL_CX) / OVAL_RX;
    const offsetY = Math.abs(faceCenterY - OVAL_CY) / OVAL_RY;
    const alignmentOk = offsetX < ALIGNMENT_TOLERANCE && offsetY < ALIGNMENT_TOLERANCE;

    // ── Update UI state ──
    setFaceDetected(faceSizeOk && eyesOpenOk);
    setQuality({ faceSizeOk, stabilityOk, alignmentOk, eyesOpenOk });
  }, []); // Empty deps → stable forever

  // ── Capture (button press) ─────────────────────────────────

  const handleCapture = useCallback(async () => {
    if (!cameraRef.current || isCapturingRef.current) return;

    isCapturingRef.current = true;
    try {
      const photo = await cameraRef.current.takePhoto({ flash: 'off' });

      if (photo?.path) {
        const uri = `file://${photo.path}`;

        // Flash + haptic
        flashAnim.setValue(0.3);
        Animated.timing(flashAnim, {
          toValue: 0,
          duration: 250,
          useNativeDriver: false,
        }).start();
        Vibration.vibrate(30);

        if (retakeIndex !== null) {
          // Retake: replace the specific image and go back to review
          setImages(prev => {
            const updated = [...prev];
            updated[retakeIndex] = uri;
            return updated;
          });
          setRetakeIndex(null);
          setFaceDetected(false);
          completedRef.current = true;
          setPhase('review');
        } else {
          // Normal capture: add image
          const newImages = [...images, uri];
          setImages(newImages);

          if (newImages.length >= captureCount) {
            // All steps done — show completion briefly then review
            completedRef.current = true;
            setPhase('complete');

            Animated.spring(checkAnim, {
              toValue: 1,
              friction: 6,
              tension: 80,
              useNativeDriver: true,
            }).start();

            timeoutRef.current = setTimeout(() => {
              setPhase('review');
            }, 1000);
          } else {
            // Advance to next step
            setCurrentStep(newImages.length);
          }
        }
      }
    } catch {
      // Silent fail
    }
    isCapturingRef.current = false;
  }, [captureCount, flashAnim, checkAnim, retakeIndex, images]);

  // ── Retake a specific photo ─────────────────────────────────

  const handleRetakePhoto = useCallback((index: number) => {
    setRetakeIndex(index);
    completedRef.current = false;
    isCapturingRef.current = false;
    setCurrentStep(index);
    setFaceDetected(false);
    setQuality(INITIAL_QUALITY);
    prevFaceBoundsRef.current = null;
    flashAnim.setValue(0);
    checkAnim.setValue(0);
    setPhase('scanning');
  }, [flashAnim, checkAnim]);

  // ── Retake all ──────────────────────────────────────────────

  const handleRetakeAll = useCallback(() => {
    setImages([]);
    setRetakeIndex(null);
    isCapturingRef.current = false;
    completedRef.current = false;
    setCurrentStep(0);
    setFaceDetected(false);
    setQuality(INITIAL_QUALITY);
    prevFaceBoundsRef.current = null;
    flashAnim.setValue(0);
    checkAnim.setValue(0);
    setPhase('scanning');
  }, [flashAnim, checkAnim]);

  // ── Confirm (from review) ──────────────────────────────────

  const handleConfirm = useCallback(() => {
    onComplete(images);
  }, [onComplete, images]);

  // ── Retry from error ────────────────────────────────────────

  const handleRetry = useCallback(() => {
    setImages([]);
    setRetakeIndex(null);
    isCapturingRef.current = false;
    completedRef.current = false;
    setCurrentStep(0);
    setFaceDetected(false);
    setQuality(INITIAL_QUALITY);
    prevFaceBoundsRef.current = null;
    flashAnim.setValue(0);
    checkAnim.setValue(0);
    setPhase('scanning');
  }, [flashAnim, checkAnim]);

  // ── Frame processor — STABLE (never recreated) ─────────────
  // handleFacesDetected has [] deps so runOnJs is created once.
  // frameProcessor depends only on detectFaces (from hook, stable)
  // and runOnJs (stable). This means the camera never needs to
  // detach/reattach the processor, eliminating the gray flash.

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
  const isScanning = phase === 'scanning';
  const isReview = phase === 'review';

  if (!hasPermission) {
    return (
      <View style={s.root}>
        <StatusBar barStyle="light-content" />
        <View style={s.noCameraContainer}>
          <Text variant="body" color="#FFFFFF" align="center">
            Camera permission is required
          </Text>
          <TouchableOpacity
            onPress={requestPermission}
            style={s.retryButton}
          >
            <Text variant="body" weight="600" color="#FFFFFF" align="center">
              Grant Permission
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

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

  const ovalStroke = isComplete
    ? '#22C55E'
    : faceDetected
      ? '#22C55E'
      : 'rgba(255,255,255,0.3)';

  const stepLabel = retakeIndex !== null
    ? `Retake: ${STEP_LABELS[retakeIndex]}`
    : `Step ${currentStep + 1} of ${captureCount}`;

  // Dynamic thumbnail height to fit screen without scrolling
  // Layout: topPad + header(50) + grid(3 rows) + footer(88) + botPad
  const topPad = insets.top + 12;
  const botPad = Math.max(insets.bottom, 16) + 8;
  const headerArea = 50;   // title + subtitle
  const footerArea = 88;   // confirm + retake all
  const gridGaps = THUMB_GAP * 2; // 2 gaps between 3 rows
  const gridMargins = 12;  // spacing above/below grid
  const availableGridH = SH - topPad - headerArea - gridGaps - gridMargins - footerArea - botPad;
  const thumbH = Math.min(availableGridH / 3, THUMB_W * 1.35);

  return (
    <View style={s.root}>
      <StatusBar barStyle="light-content" />

      {/* Camera — always mounted with stable frameProcessor */}
      <Camera
        ref={cameraRef}
        style={s.camera}
        device={device}
        isActive={!isError}
        photo={true}
        frameProcessor={frameProcessor}
        pixelFormat="yuv"
      />

      {/* ═══════════════════════════════════════════════════════════ */}
      {/* REVIEW PHASE — opaque overlay, no scroll, fits screen     */}
      {/* ═══════════════════════════════════════════════════════════ */}

      {isReview && (
        <View style={[s.reviewOverlay, { paddingTop: topPad, paddingBottom: botPad }]}>
          {/* Header */}
          <View style={s.reviewHeader}>
            <Text variant="h3" weight="700" color="#FFFFFF" align="center">
              {strings.register.faceInstructions.reviewTitle}
            </Text>
            <Text variant="caption" color="rgba(255,255,255,0.45)" align="center">
              Tap any photo to retake it
            </Text>
          </View>

          {/* Thumbnails grid — fills available space */}
          <View style={s.thumbGrid}>
            {images.map((uri, i) => (
              <TouchableOpacity
                key={`${i}-${uri}`}
                style={[s.thumbCard, { width: THUMB_W, height: thumbH }]}
                onPress={() => handleRetakePhoto(i)}
                activeOpacity={0.7}
              >
                <Image source={{ uri }} style={s.thumbImage} />
                <View style={s.thumbRetakeIcon}>
                  <RotateCcw size={14} color="#FFFFFF" strokeWidth={2.5} />
                </View>
                <View style={s.thumbLabelWrap}>
                  <Text variant="caption" weight="600" color="#FFFFFF">
                    {STEP_LABELS[i] || `Photo ${i + 1}`}
                  </Text>
                </View>
              </TouchableOpacity>
            ))}
          </View>

          {/* Actions */}
          <View style={s.reviewFooter}>
            <TouchableOpacity
              style={s.confirmButton}
              onPress={handleConfirm}
              activeOpacity={0.7}
            >
              <Check size={20} color="#FFFFFF" strokeWidth={2.5} />
              <Text variant="body" weight="700" color="#FFFFFF" style={s.confirmText}>
                {strings.register.faceInstructions.looksGood}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={s.retakeAllButton}
              onPress={handleRetakeAll}
              activeOpacity={0.7}
            >
              <RotateCcw size={14} color="rgba(255,255,255,0.5)" strokeWidth={2} />
              <Text variant="caption" color="rgba(255,255,255,0.5)" style={s.retakeAllText}>
                Retake All
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* ═══════════════════════════════════════════════════════════ */}
      {/* SCANNING / COMPLETE / ERROR — camera overlay UI            */}
      {/* ═══════════════════════════════════════════════════════════ */}

      {!isReview && (
        <>
          {/* SVG: dark mask + oval border */}
          <View style={s.svgLayer} pointerEvents="none">
            <Svg width={SW} height={SH}>
              <Path
                d={MASK_PATH}
                fill="rgba(0,0,0,0.75)"
                fillRule="evenodd"
              />
              <Ellipse
                cx={OVAL_CX}
                cy={OVAL_CY}
                rx={OVAL_RX}
                ry={OVAL_RY}
                stroke={ovalStroke}
                strokeWidth={3}
                fill="none"
              />
            </Svg>
          </View>

          {/* UI overlay */}
          <View style={s.uiLayer} pointerEvents="box-none">
            {/* Top section */}
            <View style={[s.topSection, { paddingTop: insets.top + 12 }]}>
              <Text variant="h3" weight="600" color="#FFFFFF" align="center">
                {strings.register.faceInstructions.scanLabel}
              </Text>
              {isScanning && (
                <Text
                  variant="caption"
                  color="rgba(255,255,255,0.5)"
                  align="center"
                  style={s.stepCounter}
                >
                  {stepLabel}
                </Text>
              )}
            </View>

            {/* Bottom section */}
            <View style={[s.bottomSection, { paddingBottom: Math.max(insets.bottom, 16) + 16 }]}>
              {isComplete ? (
                <View style={s.completionContainer}>
                  <Animated.View
                    style={[
                      s.checkWrapper,
                      {
                        transform: [{ scale: checkAnim }],
                        opacity: checkAnim,
                      },
                    ]}
                  >
                    <View style={s.checkCircle}>
                      <Check size={48} color="#FFFFFF" strokeWidth={3} />
                    </View>
                  </Animated.View>
                  <Text
                    variant="h3"
                    weight="700"
                    color="#22C55E"
                    align="center"
                    style={s.doneText}
                  >
                    {strings.register.faceInstructions.done}
                  </Text>
                </View>
              ) : isError ? (
                <View style={s.errorContainer}>
                  <Text
                    variant="body"
                    color="rgba(255,255,255,0.6)"
                    align="center"
                    style={s.errorText}
                  >
                    {strings.register.faceInstructions.failed}
                  </Text>
                  <TouchableOpacity onPress={handleRetry} style={s.retryButton}>
                    <Text variant="body" weight="600" color="#FFFFFF" align="center">
                      {strings.register.faceInstructions.tapToRetry}
                    </Text>
                  </TouchableOpacity>
                </View>
              ) : (
                <>
                  {/* Angle guide (direction indicator) */}
                  <AngleGuide
                    step={currentStep}
                    isAligned={faceDetected && quality.alignmentOk}
                  />

                  {/* Quality bar */}
                  <FaceQualityBar
                    faceDetected={faceDetected}
                    faceSizeOk={quality.faceSizeOk}
                    stabilityOk={quality.stabilityOk}
                    alignmentOk={quality.alignmentOk}
                    eyesOpenOk={quality.eyesOpenOk}
                  />

                  {/* Instruction */}
                  <Text
                    variant="h3"
                    weight="600"
                    color="#FFFFFF"
                    align="center"
                    style={s.instruction}
                  >
                    {STEP_INSTRUCTIONS[currentStep]}
                  </Text>

                  {/* Step indicator (replaces simple dots) */}
                  <StepIndicator
                    totalSteps={captureCount}
                    currentStep={currentStep}
                    completedSteps={
                      retakeIndex !== null
                        ? Array.from({ length: images.length }, (_, i) => i).filter(i => i !== retakeIndex)
                        : Array.from({ length: currentStep }, (_, i) => i)
                    }
                    retakeIndex={retakeIndex}
                  />

                  {/* Shutter button */}
                  <TouchableOpacity
                    style={[
                      s.shutterOuter,
                      faceDetected ? s.shutterEnabled : s.shutterDisabled,
                    ]}
                    onPress={handleCapture}
                    disabled={!faceDetected}
                    activeOpacity={0.7}
                  >
                    <View
                      style={[
                        s.shutterInner,
                        faceDetected ? s.shutterInnerEnabled : s.shutterInnerDisabled,
                      ]}
                    />
                  </TouchableOpacity>

                  {!faceDetected && (
                    <Text
                      variant="caption"
                      color="rgba(255,255,255,0.4)"
                      align="center"
                      style={s.hint}
                    >
                      {strings.register.faceInstructions.noFace}
                    </Text>
                  )}
                </>
              )}
            </View>
          </View>

          {/* Flash */}
          <Animated.View
            style={[s.flash, { opacity: flashAnim }]}
            pointerEvents="none"
          />
        </>
      )}
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
    ...StyleSheet.absoluteFillObject,
  },
  svgLayer: {
    ...StyleSheet.absoluteFillObject,
  },
  uiLayer: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'space-between',
  },

  // Top
  topSection: {
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  stepCounter: {
    marginTop: 4,
  },

  // Bottom
  bottomSection: {
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  instruction: {
    marginBottom: 16,
    textShadowColor: 'rgba(0,0,0,0.8)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 6,
  },

  // Shutter button
  shutterOuter: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 4,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  shutterEnabled: {
    borderColor: '#FFFFFF',
  },
  shutterDisabled: {
    borderColor: 'rgba(255,255,255,0.15)',
  },
  shutterInner: {
    width: 56,
    height: 56,
    borderRadius: 28,
  },
  shutterInnerEnabled: {
    backgroundColor: '#FFFFFF',
  },
  shutterInnerDisabled: {
    backgroundColor: 'rgba(255,255,255,0.08)',
  },

  hint: {
    marginTop: 4,
  },

  // Completion
  completionContainer: {
    alignItems: 'center',
  },
  checkWrapper: {
    marginBottom: 12,
  },
  checkCircle: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: 'rgba(34,197,94,0.85)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  doneText: {
    marginTop: 4,
  },

  // Error
  errorContainer: {
    alignItems: 'center',
  },
  errorText: {
    marginBottom: 16,
  },
  retryButton: {
    paddingVertical: 14,
    paddingHorizontal: 36,
    borderRadius: 28,
    borderWidth: 1.5,
    borderColor: 'rgba(255,255,255,0.4)',
  },

  // Flash
  flash: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#FFFFFF',
  },

  // No camera
  noCameraContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },

  // ── Review phase (no scroll, fits screen) ─────────────────

  reviewOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#000',
    paddingHorizontal: REVIEW_H_PAD,
  },
  reviewHeader: {
    alignItems: 'center',
    gap: 4,
    marginBottom: 6,
  },

  // Thumbnails — flex grid, centered
  thumbGrid: {
    flex: 1,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: THUMB_GAP,
    justifyContent: 'center',
    alignContent: 'center',
  },
  thumbCard: {
    borderRadius: 10,
    overflow: 'hidden',
    backgroundColor: 'rgba(255,255,255,0.06)',
  },
  thumbImage: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  thumbRetakeIcon: {
    position: 'absolute',
    top: 6,
    right: 6,
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: 'rgba(0,0,0,0.5)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  thumbLabelWrap: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingVertical: 4,
    backgroundColor: 'rgba(0,0,0,0.55)',
    alignItems: 'center',
  },

  // Review footer
  reviewFooter: {
    alignItems: 'center',
    gap: 10,
    marginTop: 6,
  },
  confirmButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    width: '100%',
    paddingVertical: 14,
    borderRadius: 28,
    backgroundColor: '#22C55E',
  },
  confirmText: {
    marginLeft: 8,
  },
  retakeAllButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
  },
  retakeAllText: {
    marginLeft: 6,
  },
});
