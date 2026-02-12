/**
 * Register Step 3 – Face Registration
 *
 * Minimal, automated face scanning inspired by GoTyme / Wise.
 * Three phases: intro → camera (auto-capture 5 angles) → complete.
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  View,
  StyleSheet,
  Animated,
  Dimensions,
  Pressable,
  StatusBar,
  Modal,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RouteProp } from '@react-navigation/native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { Image } from 'expo-image';
import { theme, config } from '../../constants';
import type { AuthStackParamList } from '../../types';
import { Text, Button } from '../../components/ui';

// ── Types ────────────────────────────────────────────────────────

type Nav = StackNavigationProp<AuthStackParamList, 'RegisterStep3'>;
type Rte = RouteProp<AuthStackParamList, 'RegisterStep3'>;
type Phase = 'intro' | 'positioning' | 'holding' | 'captured' | 'complete';

// ── Constants ────────────────────────────────────────────────────

const { width: SW } = Dimensions.get('window');
const TOTAL = config.REQUIRED_FACE_IMAGES;

// Camera frame
const FRAME_W = SW * 0.64;
const FRAME_H = FRAME_W * 1.3;
const CAM_CORNER = 32;
const CAM_THICK = 3;
const CAM_RADIUS = 12;

// Intro illustration
const ILL_W = 170;
const ILL_H = 220;
const ILL_CORNER = 24;
const ILL_THICK = 2.5;
const ILL_RADIUS = 9;

// Timing
const DETECT_MS = 2500;
const HOLD_MS = 2000;
const PAUSE_MS = 1600;

// Thumbnail grid
const THUMB_GAP = 10;
const THUMB_COLS = 3;
const THUMB_SIZE = (SW - theme.spacing[6] * 2 - THUMB_GAP * (THUMB_COLS - 1)) / THUMB_COLS;

const ANGLES = [
  'Look straight',
  'Turn left',
  'Turn right',
  'Tilt up',
  'Tilt down',
];

// ── Reusable corner-bracket frame ────────────────────────────────

interface FrameProps {
  w: number;
  h: number;
  corner: number;
  thick: number;
  radius: number;
  color: string;
}

const FrameCorners = ({ w, h, corner, thick, radius, color }: FrameProps) => {
  const b = { position: 'absolute' as const, width: corner, height: corner, borderColor: color };
  return (
    <View style={{ width: w, height: h }}>
      <View style={[b, { top: 0, left: 0, borderTopWidth: thick, borderLeftWidth: thick, borderTopLeftRadius: radius }]} />
      <View style={[b, { top: 0, right: 0, borderTopWidth: thick, borderRightWidth: thick, borderTopRightRadius: radius }]} />
      <View style={[b, { bottom: 0, left: 0, borderBottomWidth: thick, borderLeftWidth: thick, borderBottomLeftRadius: radius }]} />
      <View style={[b, { bottom: 0, right: 0, borderBottomWidth: thick, borderRightWidth: thick, borderBottomRightRadius: radius }]} />
    </View>
  );
};

// ── Main Component ───────────────────────────────────────────────

export const RegisterStep3Screen: React.FC = () => {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Rte>();
  const insets = useSafeAreaInsets();
  const cameraRef = useRef<CameraView>(null);
  const { studentInfo, accountInfo } = route.params;

  const [permission, requestPermission] = useCameraPermissions();
  const [phase, setPhase] = useState<Phase>('intro');
  const [angle, setAngle] = useState(0);
  const [images, setImages] = useState<string[]>([]);
  const [previewIdx, setPreviewIdx] = useState<number | null>(null);

  // Animations
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const scanAnim = useRef(new Animated.Value(0)).current;
  const flashAnim = useRef(new Animated.Value(0)).current;

  // Timer ref
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clear = useCallback(() => {
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
  }, []);
  useEffect(() => clear, []);

  // ── Phase: positioning ──────────────────────────────────────

  useEffect(() => {
    if (phase !== 'positioning') { pulseAnim.setValue(1); return; }
    clear();

    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 0.4, duration: 900, useNativeDriver: false }),
        Animated.timing(pulseAnim, { toValue: 1, duration: 900, useNativeDriver: false }),
      ]),
    );
    pulse.start();
    timer.current = setTimeout(() => setPhase('holding'), DETECT_MS);

    return () => { pulse.stop(); clear(); };
  }, [phase]);

  // ── Phase: holding ──────────────────────────────────────────

  useEffect(() => {
    if (phase !== 'holding') return;
    clear();
    scanAnim.setValue(0);
    Animated.timing(scanAnim, { toValue: 1, duration: HOLD_MS, useNativeDriver: false }).start();
    timer.current = setTimeout(() => capture(), HOLD_MS);
    return clear;
  }, [phase]);

  // ── Phase: captured ─────────────────────────────────────────

  useEffect(() => {
    if (phase !== 'captured') return;
    clear();
    flashAnim.setValue(0.35);
    Animated.timing(flashAnim, { toValue: 0, duration: 350, useNativeDriver: false }).start();

    timer.current = setTimeout(() => {
      const next = angle + 1;
      if (next >= TOTAL) {
        setPhase('complete');
      } else {
        setAngle(next);
        setPhase('positioning');
      }
    }, PAUSE_MS);
    return clear;
  }, [phase, angle]);

  // ── Capture ─────────────────────────────────────────────────

  const capture = useCallback(async () => {
    if (!cameraRef.current) return;
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: config.FACE_IMAGE_QUALITY,
        base64: true,
      });
      if (photo?.uri) {
        setImages(prev => [...prev, photo.uri]);
        setPhase('captured');
      } else {
        setPhase('positioning');
      }
    } catch {
      setPhase('positioning');
    }
  }, []);

  // ── Handlers ────────────────────────────────────────────────

  const handleStart = useCallback(async () => {
    let granted = permission?.granted;
    if (!granted) {
      const res = await requestPermission();
      granted = res.granted;
    }
    if (granted) setPhase('positioning');
  }, [permission]);

  const handleSkip = useCallback(() => {
    navigation.navigate('RegisterReview', { studentInfo, accountInfo, faceImages: [] });
  }, [studentInfo, accountInfo]);

  const handleDone = useCallback(() => {
    navigation.navigate('RegisterReview', { studentInfo, accountInfo, faceImages: images });
  }, [images, studentInfo, accountInfo]);

  const handleRetake = useCallback(() => {
    setImages([]);
    setAngle(0);
    setPhase('positioning');
  }, []);

  // ═══════════════════════════════════════════════════════════════
  // INTRO
  // ═══════════════════════════════════════════════════════════════

  if (phase === 'intro') {
    return (
      <View style={[s.introRoot, { paddingTop: insets.top }]}>
        <StatusBar barStyle="dark-content" />

        {/* Back */}
        <Pressable onPress={() => navigation.goBack()} style={s.backBtn} hitSlop={16}>
          <View style={s.chevron} />
        </Pressable>

        {/* Center */}
        <View style={s.introCenter}>
          <View style={s.illWrap}>
            <FrameCorners w={ILL_W} h={ILL_H} corner={ILL_CORNER} thick={ILL_THICK} radius={ILL_RADIUS} color={theme.colors.foreground} />
            {/* Face features */}
            <View style={s.faceFeatures}>
              <View style={s.eyeRow}>
                <View style={s.eyeDash} />
                <View style={s.eyeDash} />
              </View>
              <View style={s.mouthDash} />
            </View>
          </View>

          <Text variant="h2" weight="700" align="center" style={s.introTitle}>
            Set up Face ID
          </Text>
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            Scan your face to verify your identity
          </Text>
        </View>

        {/* Bottom */}
        <View style={[s.introBottom, { paddingBottom: Math.max(insets.bottom, 24) + 16 }]}>
          <Button variant="primary" size="lg" fullWidth onPress={handleStart}>
            Get started
          </Button>
          <Pressable onPress={handleSkip} style={s.skipBtn} hitSlop={8}>
            <Text variant="body" color={theme.colors.text.tertiary}>Not now</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  // ═══════════════════════════════════════════════════════════════
  // COMPLETE
  // ═══════════════════════════════════════════════════════════════

  if (phase === 'complete') {
    return (
      <View style={[s.doneRoot, { paddingTop: insets.top }]}>
        <StatusBar barStyle="dark-content" />

        {/* Header */}
        <View style={s.doneHeader}>
          <Text variant="h2" weight="700" align="center">
            Review your photos
          </Text>
          <Text variant="body" color={theme.colors.text.secondary} align="center" style={s.doneSubtitle}>
            Tap any photo to preview. {TOTAL} angles captured.
          </Text>
        </View>

        {/* Photo grid */}
        <View style={s.thumbGrid}>
          {images.map((uri, i) => (
            <Pressable key={i} onPress={() => setPreviewIdx(i)} style={s.thumbWrap}>
              <Image source={{ uri }} style={s.thumb} contentFit="cover" />
              <View style={s.thumbLabel}>
                <Text variant="caption" color={theme.colors.text.secondary}>
                  {ANGLES[i]}
                </Text>
              </View>
            </Pressable>
          ))}
        </View>

        {/* Bottom */}
        <View style={[s.doneBottom, { paddingBottom: Math.max(insets.bottom, 24) + 16 }]}>
          <Button variant="primary" size="lg" fullWidth onPress={handleDone}>
            Continue
          </Button>
          <Pressable onPress={handleRetake} style={s.skipBtn} hitSlop={8}>
            <Text variant="body" color={theme.colors.text.tertiary}>Retake all</Text>
          </Pressable>
        </View>

        {/* Full-screen preview modal */}
        <Modal visible={previewIdx !== null} transparent animationType="fade">
          <Pressable style={s.modalBg} onPress={() => setPreviewIdx(null)}>
            <View style={[s.modalTop, { paddingTop: insets.top + 12 }]}>
              <Pressable onPress={() => setPreviewIdx(null)} hitSlop={16}>
                <Text variant="body" weight="600" color="#FAFAFA">Close</Text>
              </Pressable>
            </View>
            <View style={s.modalCenter}>
              {previewIdx !== null && (
                <Image
                  source={{ uri: images[previewIdx] }}
                  style={s.modalImage}
                  contentFit="contain"
                />
              )}
            </View>
            <View style={s.modalLabel}>
              <Text variant="body" weight="600" color="#FAFAFA" align="center">
                {previewIdx !== null ? ANGLES[previewIdx] : ''}
              </Text>
              <Text variant="caption" color="rgba(255,255,255,0.5)" align="center">
                {previewIdx !== null ? `${previewIdx + 1} of ${TOTAL}` : ''}
              </Text>
            </View>
          </Pressable>
        </Modal>
      </View>
    );
  }

  // ═══════════════════════════════════════════════════════════════
  // CAMERA
  // ═══════════════════════════════════════════════════════════════

  const isHolding = phase === 'holding';
  const isCaptured = phase === 'captured';
  const cornerColor = isCaptured ? theme.colors.success : '#FFFFFF';

  return (
    <View style={s.camRoot}>
      <StatusBar barStyle="light-content" />
      <CameraView ref={cameraRef} style={s.cam} facing="front" />

      <View style={s.camOverlay} pointerEvents="box-none">
        {/* Top */}
        <View style={[s.camTop, { paddingTop: insets.top + 16 }]}>
          <Text variant="h3" weight="600" color="#fff" align="center" style={s.shadowText}>
            {isHolding ? 'Hold still' : ANGLES[angle]}
          </Text>
        </View>

        {/* Frame */}
        <View style={s.camFrameWrap}>
          <Animated.View style={{ opacity: isCaptured ? 1 : pulseAnim }}>
            <FrameCorners
              w={FRAME_W} h={FRAME_H} corner={CAM_CORNER} thick={CAM_THICK} radius={CAM_RADIUS}
              color={cornerColor}
            />
          </Animated.View>

          {/* Scan progress bar */}
          {isHolding && (
            <View style={s.scanTrack}>
              <Animated.View
                style={[
                  s.scanFill,
                  {
                    width: scanAnim.interpolate({
                      inputRange: [0, 1],
                      outputRange: ['0%', '100%'],
                    }),
                  },
                ]}
              />
            </View>
          )}
        </View>

        {/* Flash */}
        <Animated.View style={[s.flash, { opacity: flashAnim }]} pointerEvents="none" />

        {/* Bottom */}
        <View style={[s.camBottom, { paddingBottom: Math.max(insets.bottom, 24) + 16 }]}>
          <View style={s.segRow}>
            {Array.from({ length: TOTAL }).map((_, i) => (
              <View
                key={i}
                style={[
                  s.seg,
                  i < images.length
                    ? s.segDone
                    : i === angle
                      ? s.segActive
                      : s.segPending,
                ]}
              />
            ))}
          </View>
          <Text variant="caption" color="rgba(255,255,255,0.45)" align="center">
            {images.length} of {TOTAL}
          </Text>
        </View>
      </View>
    </View>
  );
};

// ── Styles ───────────────────────────────────────────────────────

const s = StyleSheet.create({
  // ─ Intro ─
  introRoot: {
    flex: 1,
    backgroundColor: theme.colors.background,
    paddingHorizontal: theme.spacing[6],
  },
  backBtn: {
    marginTop: 12,
    width: 44,
    height: 44,
    justifyContent: 'center',
  },
  chevron: {
    width: 11,
    height: 11,
    borderLeftWidth: 2,
    borderBottomWidth: 2,
    borderColor: theme.colors.foreground,
    transform: [{ rotate: '45deg' }],
  },
  introCenter: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  illWrap: {
    width: ILL_W,
    height: ILL_H,
    marginBottom: 36,
  },
  faceFeatures: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 10,
  },
  eyeRow: {
    flexDirection: 'row',
    gap: 34,
    marginBottom: 30,
  },
  eyeDash: {
    width: 16,
    height: 2.5,
    backgroundColor: theme.colors.foreground,
    borderRadius: 2,
  },
  mouthDash: {
    width: 22,
    height: 2.5,
    backgroundColor: theme.colors.foreground,
    borderRadius: 2,
  },
  introTitle: {
    marginBottom: 8,
  },
  introBottom: {
    alignItems: 'center',
    gap: 16,
  },
  skipBtn: {
    paddingVertical: 8,
  },

  // ─ Complete ─
  doneRoot: {
    flex: 1,
    backgroundColor: theme.colors.background,
    paddingHorizontal: theme.spacing[6],
  },
  doneHeader: {
    marginTop: 24,
    marginBottom: 20,
    alignItems: 'center',
  },
  doneSubtitle: {
    marginTop: 6,
  },
  thumbGrid: {
    flex: 1,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: THUMB_GAP,
  },
  thumbWrap: {
    width: THUMB_SIZE,
    borderRadius: 12,
    overflow: 'hidden',
    backgroundColor: theme.colors.muted,
  },
  thumb: {
    width: THUMB_SIZE,
    height: THUMB_SIZE * 1.25,
    borderRadius: 12,
  },
  thumbLabel: {
    paddingVertical: 6,
    alignItems: 'center',
  },
  doneBottom: {
    alignItems: 'center',
    gap: 16,
    paddingTop: 12,
  },

  // ─ Preview modal ─
  modalBg: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.92)',
    justifyContent: 'space-between',
  },
  modalTop: {
    alignItems: 'flex-end',
    paddingHorizontal: theme.spacing[6],
  },
  modalCenter: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: theme.spacing[4],
  },
  modalImage: {
    width: SW - theme.spacing[4] * 2,
    height: (SW - theme.spacing[4] * 2) * 1.35,
    borderRadius: 16,
  },
  modalLabel: {
    paddingBottom: 40,
    alignItems: 'center',
    gap: 4,
  },

  // ─ Camera ─
  camRoot: {
    flex: 1,
    backgroundColor: '#000',
  },
  cam: {
    flex: 1,
  },
  camOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'space-between',
  },
  camTop: {
    paddingHorizontal: theme.spacing[6],
    paddingBottom: theme.spacing[3],
    alignItems: 'center',
  },
  shadowText: {
    textShadowColor: 'rgba(0,0,0,0.8)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 6,
  },
  camFrameWrap: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  scanTrack: {
    width: FRAME_W * 0.5,
    height: 3,
    borderRadius: 2,
    backgroundColor: 'rgba(255,255,255,0.15)',
    marginTop: 20,
    overflow: 'hidden',
  },
  scanFill: {
    height: '100%',
    borderRadius: 2,
    backgroundColor: '#FFFFFF',
  },
  flash: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#FFFFFF',
  },
  camBottom: {
    paddingHorizontal: theme.spacing[6],
    alignItems: 'center',
    gap: 10,
  },
  segRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
  },
  seg: {
    width: 36,
    height: 3,
    borderRadius: 2,
  },
  segDone: {
    backgroundColor: '#FFFFFF',
  },
  segActive: {
    backgroundColor: 'rgba(255,255,255,0.5)',
  },
  segPending: {
    backgroundColor: 'rgba(255,255,255,0.15)',
  },
});
