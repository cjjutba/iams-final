/**
 * Skeleton Component - Loading Placeholder
 *
 * Animated pulse placeholder for loading states.
 * Replaces ActivityIndicator spinners with content-shaped placeholders.
 */

import React, { useEffect, useRef } from 'react';
import { View, Animated, StyleSheet, ViewStyle } from 'react-native';
import { theme } from '../../constants';

// ---------------------------------------------------------------------------
// Base Skeleton
// ---------------------------------------------------------------------------

interface SkeletonProps {
  width?: number | string;
  height?: number;
  borderRadius?: number;
  style?: ViewStyle;
}

const useSkeletonAnimation = () => {
  const animatedValue = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(animatedValue, {
          toValue: 1,
          duration: 800,
          useNativeDriver: false,
        }),
        Animated.timing(animatedValue, {
          toValue: 0,
          duration: 800,
          useNativeDriver: false,
        }),
      ]),
    );
    animation.start();
    return () => animation.stop();
  }, [animatedValue]);

  return animatedValue.interpolate({
    inputRange: [0, 1],
    outputRange: [theme.colors.secondary, theme.colors.border],
  });
};

export const Skeleton: React.FC<SkeletonProps> = ({
  width = '100%',
  height = 14,
  borderRadius = theme.borderRadius.sm,
  style,
}) => {
  const backgroundColor = useSkeletonAnimation();

  return (
    <Animated.View
      style={[
        {
          width: width as any,
          height,
          borderRadius,
          backgroundColor,
        },
        style,
      ]}
    />
  );
};

// ---------------------------------------------------------------------------
// Skeleton Card Wrapper
// ---------------------------------------------------------------------------

const SkeletonCard: React.FC<{ children: React.ReactNode; style?: ViewStyle }> = ({
  children,
  style,
}) => (
  <View style={[styles.card, style]}>
    {children}
  </View>
);

// ---------------------------------------------------------------------------
// Schedule Card Skeleton
// ---------------------------------------------------------------------------

export const ScheduleCardSkeleton: React.FC = () => (
  <SkeletonCard style={styles.mb12}>
    <Skeleton width={80} height={20} borderRadius={theme.borderRadius.sm} />
    <View style={styles.gap8} />
    <Skeleton width="70%" height={16} />
    <View style={styles.gap4} />
    <Skeleton width="40%" height={12} />
    <View style={styles.gap8} />
    <Skeleton width="55%" height={12} />
  </SkeletonCard>
);

// ---------------------------------------------------------------------------
// Alert Card Skeleton
// ---------------------------------------------------------------------------

export const AlertCardSkeleton: React.FC = () => (
  <SkeletonCard style={styles.mb8}>
    <View style={styles.row}>
      <Skeleton width={40} height={40} borderRadius={20} />
      <View style={[styles.flex1, styles.ml12]}>
        <Skeleton width="60%" height={16} />
        <View style={styles.gap4} />
        <Skeleton width="35%" height={12} />
        <View style={styles.gap4} />
        <Skeleton width="25%" height={10} />
      </View>
      <Skeleton width={60} height={24} borderRadius={theme.borderRadius.sm} />
    </View>
  </SkeletonCard>
);

// ---------------------------------------------------------------------------
// Analytics Summary Skeleton
// ---------------------------------------------------------------------------

export const AnalyticsSummarySkeleton: React.FC = () => (
  <View style={styles.summaryRow}>
    <SkeletonCard style={styles.flex1}>
      <View style={styles.center}>
        <Skeleton width={20} height={20} borderRadius={theme.borderRadius.sm} />
        <View style={styles.gap8} />
        <Skeleton width={40} height={28} borderRadius={theme.borderRadius.sm} />
        <View style={styles.gap4} />
        <Skeleton width={80} height={12} />
      </View>
    </SkeletonCard>
    <View style={styles.gap12} />
    <SkeletonCard style={styles.flex1}>
      <View style={styles.center}>
        <Skeleton width={20} height={20} borderRadius={theme.borderRadius.sm} />
        <View style={styles.gap8} />
        <Skeleton width={40} height={28} borderRadius={theme.borderRadius.sm} />
        <View style={styles.gap4} />
        <Skeleton width={80} height={12} />
      </View>
    </SkeletonCard>
  </View>
);

// ---------------------------------------------------------------------------
// Class Overview Card Skeleton
// ---------------------------------------------------------------------------

export const ClassOverviewCardSkeleton: React.FC = () => (
  <SkeletonCard style={styles.mb12}>
    <View style={styles.rowBetween}>
      <View style={styles.flex1}>
        <Skeleton width="65%" height={14} />
        <View style={styles.gap4} />
        <Skeleton width="35%" height={12} />
      </View>
      <Skeleton width={48} height={22} borderRadius={theme.borderRadius.sm} />
    </View>
    <View style={styles.gap12} />
    <Skeleton width="100%" height={8} borderRadius={theme.borderRadius.full} />
    <View style={styles.gap12} />
    <View style={styles.rowBetween}>
      <View style={styles.center}>
        <Skeleton width={24} height={14} />
        <View style={styles.gap4} />
        <Skeleton width={44} height={10} />
      </View>
      <View style={styles.center}>
        <Skeleton width={24} height={14} />
        <View style={styles.gap4} />
        <Skeleton width={44} height={10} />
      </View>
      <View style={styles.center}>
        <Skeleton width={24} height={14} />
        <View style={styles.gap4} />
        <Skeleton width={56} height={10} />
      </View>
    </View>
  </SkeletonCard>
);

// ---------------------------------------------------------------------------
// Profile Skeleton
// ---------------------------------------------------------------------------

export const ProfileSkeleton: React.FC = () => (
  <View style={styles.profileContainer}>
    {/* Avatar */}
    <View style={styles.center}>
      <Skeleton width={80} height={80} borderRadius={40} />
      <View style={styles.gap12} />
      <Skeleton width={140} height={20} />
      <View style={styles.gap4} />
      <Skeleton width={60} height={14} />
    </View>
    <View style={styles.gap24} />
    {/* Info card */}
    <SkeletonCard>
      <View style={styles.rowBetween}>
        <Skeleton width={40} height={12} />
        <Skeleton width={140} height={14} />
      </View>
      <View style={styles.gap12} />
      <View style={styles.rowBetween}>
        <Skeleton width={40} height={12} />
        <Skeleton width={100} height={14} />
      </View>
      <View style={styles.gap12} />
      <View style={styles.rowBetween}>
        <Skeleton width={30} height={12} />
        <Skeleton width={60} height={14} />
      </View>
    </SkeletonCard>
  </View>
);

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  card: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 12,
    padding: theme.spacing[3],
    backgroundColor: theme.colors.card,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  flex1: { flex: 1 },
  center: { alignItems: 'center' },
  ml12: { marginLeft: theme.spacing[3] },
  mb8: { marginBottom: theme.spacing[2] },
  mb12: { marginBottom: theme.spacing[3] },
  gap4: { height: theme.spacing[1] },
  gap8: { height: theme.spacing[2] },
  gap12: { height: theme.spacing[3], width: theme.spacing[3] },
  gap24: { height: theme.spacing[6] },
  summaryRow: {
    flexDirection: 'row',
  },
  profileContainer: {
    paddingHorizontal: theme.spacing[4],
    paddingTop: theme.spacing[6],
  },
});
