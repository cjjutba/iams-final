/**
 * Register Step 3 – Face Registration
 *
 * Two phases:
 *   1. Intro — "Set up Face ID" illustration with Get started / Skip buttons
 *   2. Scanning — Full-screen FaceScanCamera (iPhone Face ID-style continuous capture)
 */

import React, { useState, useCallback } from 'react';
import {
  View,
  StyleSheet,
  Pressable,
  StatusBar,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RouteProp } from '@react-navigation/native';
import { useCameraPermissions } from 'expo-camera';
import { theme } from '../../constants';
import type { AuthStackParamList } from '../../types';
import { Text, Button } from '../../components/ui';
import { FaceScanCamera } from '../../components/face';

// ── Types ────────────────────────────────────────────────────

type Nav = StackNavigationProp<AuthStackParamList, 'RegisterStep3'>;
type Rte = RouteProp<AuthStackParamList, 'RegisterStep3'>;
type Phase = 'intro' | 'scanning';

// ── Intro illustration frame ─────────────────────────────────

const ILL_W = 170;
const ILL_H = 220;
const ILL_CORNER = 24;
const ILL_THICK = 2.5;
const ILL_RADIUS = 9;

interface FrameProps {
  w: number; h: number; corner: number; thick: number; radius: number; color: string;
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

// ── Main Component ───────────────────────────────────────────

export const RegisterStep3Screen: React.FC = () => {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Rte>();
  const insets = useSafeAreaInsets();
  const { studentInfo, accountInfo } = route.params;

  const [permission, requestPermission] = useCameraPermissions();
  const [phase, setPhase] = useState<Phase>('intro');

  // ── Handlers ──────────────────────────────────────────────

  const handleStart = useCallback(async () => {
    let granted = permission?.granted;
    if (!granted) {
      const res = await requestPermission();
      granted = res.granted;
    }
    if (granted) setPhase('scanning');
  }, [permission]);

  const handleSkip = useCallback(() => {
    navigation.navigate('RegisterReview', { studentInfo, accountInfo, faceImages: [] });
  }, [studentInfo, accountInfo]);

  const handleScanComplete = useCallback((images: string[]) => {
    navigation.navigate('RegisterReview', { studentInfo, accountInfo, faceImages: images });
  }, [studentInfo, accountInfo]);

  // ═══════════════════════════════════════════════════════════
  // SCANNING — full-screen FaceScanCamera
  // ═══════════════════════════════════════════════════════════

  if (phase === 'scanning') {
    return <FaceScanCamera onComplete={handleScanComplete} />;
  }

  // ═══════════════════════════════════════════════════════════
  // INTRO
  // ═══════════════════════════════════════════════════════════

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
          <FrameCorners
            w={ILL_W} h={ILL_H}
            corner={ILL_CORNER} thick={ILL_THICK} radius={ILL_RADIUS}
            color={theme.colors.foreground}
          />
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
};

// ── Styles ───────────────────────────────────────────────────

const s = StyleSheet.create({
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
});
