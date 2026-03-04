/**
 * AngleGuide -- SVG directional indicator for face angle capture steps.
 *
 * Renders a small visual cue near the oval cutout showing the expected
 * head direction for the current capture step:
 *   0 = center (circle), 1 = left, 2 = right, 3 = up, 4 = down
 *
 * White when pending, green (#22C55E) when the face matches the angle.
 * Uses react-native-svg for crisp vector rendering on all densities.
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';
import { Text } from '../ui';

// ── Types ──────────────────────────────────────────────────────

export interface AngleGuideProps {
  /** 0=center, 1=left, 2=right, 3=up, 4=down */
  step: number;
  /** Turns green when the face matches the expected angle */
  isAligned: boolean;
}

// ── Constants ──────────────────────────────────────────────────

const ICON_SIZE = 40;
const COLOR_PENDING = 'rgba(255,255,255,0.8)';
const COLOR_ALIGNED = '#22C55E';

const STEP_LABELS = ['Center', 'Left', 'Right', 'Up', 'Down'];

// ── SVG icon renderers ─────────────────────────────────────────

function CenterIcon({ color }: { color: string }) {
  return (
    <Svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 40 40">
      <Circle
        cx={20}
        cy={20}
        r={10}
        stroke={color}
        strokeWidth={2.5}
        fill="none"
      />
      <Circle cx={20} cy={20} r={3} fill={color} />
    </Svg>
  );
}

function ArrowLeftIcon({ color }: { color: string }) {
  return (
    <Svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 40 40">
      <Path
        d="M28 20H12M12 20L19 13M12 20L19 27"
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </Svg>
  );
}

function ArrowRightIcon({ color }: { color: string }) {
  return (
    <Svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 40 40">
      <Path
        d="M12 20H28M28 20L21 13M28 20L21 27"
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </Svg>
  );
}

function ArrowUpIcon({ color }: { color: string }) {
  return (
    <Svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 40 40">
      <Path
        d="M20 28V12M20 12L13 19M20 12L27 19"
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </Svg>
  );
}

function ArrowDownIcon({ color }: { color: string }) {
  return (
    <Svg width={ICON_SIZE} height={ICON_SIZE} viewBox="0 0 40 40">
      <Path
        d="M20 12V28M20 28L13 21M20 28L27 21"
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </Svg>
  );
}

const STEP_ICONS = [CenterIcon, ArrowLeftIcon, ArrowRightIcon, ArrowUpIcon, ArrowDownIcon];

// ── Component ──────────────────────────────────────────────────

export const AngleGuide: React.FC<AngleGuideProps> = ({ step, isAligned }) => {
  const color = isAligned ? COLOR_ALIGNED : COLOR_PENDING;
  const StepIcon = STEP_ICONS[step] ?? CenterIcon;

  return (
    <View style={s.container}>
      <View style={[s.iconCircle, isAligned && s.iconCircleAligned]}>
        <StepIcon color={color} />
      </View>
      <Text
        variant="caption"
        weight="600"
        color={color}
        style={s.label}
      >
        {STEP_LABELS[step] ?? 'Center'}
      </Text>
    </View>
  );
};

// ── Styles ──────────────────────────────────────────────────────

const s = StyleSheet.create({
  container: {
    alignItems: 'center',
    marginBottom: 8,
  },
  iconCircle: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: 'rgba(0,0,0,0.35)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: 'rgba(255,255,255,0.15)',
  },
  iconCircleAligned: {
    borderColor: 'rgba(34,197,94,0.5)',
    backgroundColor: 'rgba(34,197,94,0.15)',
  },
  label: {
    marginTop: 4,
    fontSize: 11,
    textShadowColor: 'rgba(0,0,0,0.8)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 4,
  },
});
