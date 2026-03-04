/**
 * FaceQualityBar -- Horizontal quality indicator bar for face scanning.
 *
 * Displays 4 quality factors as pill/badge indicators that transition
 * from gray (unmet) to green (satisfied). When all 4 are satisfied,
 * a "Ready" label appears. Designed to overlay the camera with white
 * text on a semi-transparent dark background.
 */

import React, { useMemo } from 'react';
import { View, StyleSheet } from 'react-native';
import { Text } from '../ui';

// ── Types ──────────────────────────────────────────────────────

export interface FaceQualityBarProps {
  faceDetected: boolean;
  faceSizeOk: boolean;
  stabilityOk: boolean;
  alignmentOk: boolean;
  eyesOpenOk: boolean;
}

// ── Quality factor definitions ─────────────────────────────────

interface QualityFactor {
  key: string;
  label: string;
}

const QUALITY_FACTORS: QualityFactor[] = [
  { key: 'faceSize', label: 'Size' },
  { key: 'stability', label: 'Steady' },
  { key: 'alignment', label: 'Align' },
  { key: 'eyesOpen', label: 'Eyes' },
];

const COLOR_OK = '#22C55E';
const COLOR_PENDING = 'rgba(255,255,255,0.2)';
const TEXT_OK = '#FFFFFF';
const TEXT_PENDING = 'rgba(255,255,255,0.5)';

// ── Component ──────────────────────────────────────────────────

export const FaceQualityBar: React.FC<FaceQualityBarProps> = ({
  faceDetected,
  faceSizeOk,
  stabilityOk,
  alignmentOk,
  eyesOpenOk,
}) => {
  const factorStates = useMemo(() => ({
    faceSize: faceDetected && faceSizeOk,
    stability: faceDetected && stabilityOk,
    alignment: faceDetected && alignmentOk,
    eyesOpen: faceDetected && eyesOpenOk,
  }), [faceDetected, faceSizeOk, stabilityOk, alignmentOk, eyesOpenOk]);

  const allReady = factorStates.faceSize
    && factorStates.stability
    && factorStates.alignment
    && factorStates.eyesOpen;

  return (
    <View style={s.container}>
      <View style={s.pillRow}>
        {QUALITY_FACTORS.map((factor) => {
          const ok = factorStates[factor.key as keyof typeof factorStates];
          return (
            <View
              key={factor.key}
              style={[s.pill, { backgroundColor: ok ? COLOR_OK : COLOR_PENDING }]}
            >
              <Text
                variant="caption"
                weight="600"
                color={ok ? TEXT_OK : TEXT_PENDING}
                style={s.pillText}
              >
                {factor.label}
              </Text>
            </View>
          );
        })}
      </View>

      {allReady && (
        <View style={s.readyBadge}>
          <Text variant="caption" weight="700" color={COLOR_OK}>
            Ready
          </Text>
        </View>
      )}
    </View>
  );
};

// ── Styles ──────────────────────────────────────────────────────

const s = StyleSheet.create({
  container: {
    alignItems: 'center',
    marginBottom: 12,
  },
  pillRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  pill: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  pillText: {
    fontSize: 11,
    lineHeight: 14,
  },
  readyBadge: {
    marginTop: 6,
  },
});
