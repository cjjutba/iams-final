/**
 * StepIndicator -- Enhanced step indicator for multi-angle face capture.
 *
 * Replaces the simple progress dots with richer visual states:
 *   - Pending: gray outline circle
 *   - Active: white filled circle with a subtle pulse animation
 *   - Complete: green filled circle with a checkmark icon
 *   - Retake: orange ring around the retake target step
 *
 * Uses React Native Animated for the pulse effect on the active step.
 */

import React, { useEffect, useRef } from 'react';
import { View, StyleSheet, Animated } from 'react-native';
import Svg, { Path } from 'react-native-svg';

// ── Types ──────────────────────────────────────────────────────

export interface StepIndicatorProps {
  totalSteps: number;
  currentStep: number;
  completedSteps: number[];
  retakeIndex: number | null;
}

// ── Constants ──────────────────────────────────────────────────

const DOT_SIZE = 14;
const ACTIVE_SIZE = 18;
const COLOR_COMPLETE = '#22C55E';
const COLOR_ACTIVE = '#FFFFFF';
const COLOR_PENDING = 'rgba(255,255,255,0.2)';
const COLOR_RETAKE = '#F59E0B';

// ── Small checkmark SVG ────────────────────────────────────────

function MiniCheck() {
  return (
    <Svg width={10} height={10} viewBox="0 0 10 10">
      <Path
        d="M2 5.5L4.2 7.5L8 3"
        stroke="#FFFFFF"
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </Svg>
  );
}

// ── Single dot component ───────────────────────────────────────

interface StepDotProps {
  state: 'pending' | 'active' | 'complete' | 'retake';
}

const StepDot: React.FC<StepDotProps> = ({ state }) => {
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (state === 'active') {
      const animation = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.25,
            duration: 800,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 800,
            useNativeDriver: true,
          }),
        ]),
      );
      animation.start();
      return () => animation.stop();
    }

    pulseAnim.setValue(1);
  }, [state, pulseAnim]);

  if (state === 'complete') {
    return (
      <View style={s.completeDot}>
        <MiniCheck />
      </View>
    );
  }

  if (state === 'active') {
    return (
      <Animated.View
        style={[
          s.activeDot,
          { transform: [{ scale: pulseAnim }] },
        ]}
      />
    );
  }

  if (state === 'retake') {
    return <View style={s.retakeDot} />;
  }

  // pending
  return <View style={s.pendingDot} />;
};

// ── Component ──────────────────────────────────────────────────

export const StepIndicator: React.FC<StepIndicatorProps> = ({
  totalSteps,
  currentStep,
  completedSteps,
  retakeIndex,
}) => {
  return (
    <View style={s.container}>
      {Array.from({ length: totalSteps }).map((_, i) => {
        let dotState: StepDotProps['state'];

        if (retakeIndex !== null && i === retakeIndex) {
          dotState = 'retake';
        } else if (completedSteps.includes(i)) {
          dotState = 'complete';
        } else if (i === currentStep) {
          dotState = 'active';
        } else {
          dotState = 'pending';
        }

        return <StepDot key={i} state={dotState} />;
      })}
    </View>
  );
};

// ── Styles ──────────────────────────────────────────────────────

const s = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    marginBottom: 28,
  },
  pendingDot: {
    width: DOT_SIZE,
    height: DOT_SIZE,
    borderRadius: DOT_SIZE / 2,
    borderWidth: 1.5,
    borderColor: COLOR_PENDING,
    backgroundColor: 'transparent',
  },
  activeDot: {
    width: ACTIVE_SIZE,
    height: ACTIVE_SIZE,
    borderRadius: ACTIVE_SIZE / 2,
    backgroundColor: COLOR_ACTIVE,
  },
  completeDot: {
    width: DOT_SIZE,
    height: DOT_SIZE,
    borderRadius: DOT_SIZE / 2,
    backgroundColor: COLOR_COMPLETE,
    alignItems: 'center',
    justifyContent: 'center',
  },
  retakeDot: {
    width: ACTIVE_SIZE,
    height: ACTIVE_SIZE,
    borderRadius: ACTIVE_SIZE / 2,
    borderWidth: 2,
    borderColor: COLOR_RETAKE,
    backgroundColor: 'rgba(245,158,11,0.2)',
  },
});
