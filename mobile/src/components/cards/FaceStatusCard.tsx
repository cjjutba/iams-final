/**
 * FaceStatusCard Component
 *
 * Unified card handling three face registration states:
 * 1. not_registered - Warning style with CTA to register
 * 2. registered - Shows registration date with re-register option
 * 3. loading - Shimmer/placeholder effect
 *
 * Replaces the inline face registration banner on the student home screen
 * with a more informative, self-contained card.
 */

import React, { useEffect, useRef } from 'react';
import { View, StyleSheet, Animated, TouchableOpacity } from 'react-native';
import { Camera, CheckCircle, AlertTriangle } from 'lucide-react-native';
import { theme } from '../../constants';
import { formatDate } from '../../utils';
import { Card, Text, Button } from '../ui';

interface FaceStatusCardProps {
  status: 'not_registered' | 'registered' | 'loading';
  registeredAt?: string; // ISO date
  onRegister?: () => void;
  onReregister?: () => void;
}

// ---------------------------------------------------------------------------
// Shimmer placeholder for loading state
// ---------------------------------------------------------------------------

const ShimmerPlaceholder: React.FC = () => {
  const animatedValue = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(animatedValue, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: false,
        }),
        Animated.timing(animatedValue, {
          toValue: 0,
          duration: 1000,
          useNativeDriver: false,
        }),
      ]),
    );
    animation.start();
    return () => animation.stop();
  }, [animatedValue]);

  const backgroundColor = animatedValue.interpolate({
    inputRange: [0, 1],
    outputRange: [theme.colors.secondary, theme.colors.border],
  });

  return (
    <View style={shimmerStyles.container}>
      <Animated.View style={[shimmerStyles.iconPlaceholder, { backgroundColor }]} />
      <View style={shimmerStyles.textWrap}>
        <Animated.View style={[shimmerStyles.lineLong, { backgroundColor }]} />
        <Animated.View style={[shimmerStyles.lineShort, { backgroundColor }]} />
      </View>
    </View>
  );
};

const shimmerStyles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing[3],
  },
  iconPlaceholder: {
    width: 40,
    height: 40,
    borderRadius: theme.borderRadius.md,
  },
  textWrap: {
    flex: 1,
    gap: theme.spacing[2],
  },
  lineLong: {
    height: 14,
    borderRadius: theme.borderRadius.sm,
    width: '70%',
  },
  lineShort: {
    height: 10,
    borderRadius: theme.borderRadius.sm,
    width: '45%',
  },
});

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export const FaceStatusCard: React.FC<FaceStatusCardProps> = ({
  status,
  registeredAt,
  onRegister,
  onReregister,
}) => {
  // ----- Loading state -----
  if (status === 'loading') {
    return (
      <Card variant="outlined" style={styles.card}>
        <ShimmerPlaceholder />
      </Card>
    );
  }

  // ----- Not registered -----
  if (status === 'not_registered') {
    return (
      <Card variant="outlined" style={[styles.card, styles.warningCard]}>
        <View style={styles.row}>
          <View style={[styles.iconWrap, styles.warningIconWrap]}>
            <AlertTriangle size={20} color={theme.colors.warning} />
          </View>
          <View style={styles.textWrap}>
            <Text variant="body" weight="600">
              Face Not Registered
            </Text>
            <Text variant="caption" color={theme.colors.text.secondary}>
              Required for automatic attendance tracking
            </Text>
          </View>
        </View>
        {onRegister && (
          <Button
            variant="primary"
            size="sm"
            fullWidth
            onPress={onRegister}
            leftIcon={<Camera size={16} color={theme.colors.primaryForeground} />}
            style={styles.ctaButton}
          >
            Register Face
          </Button>
        )}
      </Card>
    );
  }

  // ----- Registered -----
  return (
    <Card variant="outlined" style={styles.card}>
      <View style={styles.row}>
        <View style={[styles.iconWrap, styles.successIconWrap]}>
          <CheckCircle size={20} color={theme.colors.success} />
        </View>
        <View style={styles.textWrap}>
          <Text variant="body" weight="600">
            Face Registered
          </Text>
          {registeredAt && (
            <Text variant="caption" color={theme.colors.text.secondary}>
              Registered on {formatDate(registeredAt, 'MMM dd, yyyy')}
            </Text>
          )}
        </View>
      </View>
      {onReregister && (
        <TouchableOpacity
          onPress={onReregister}
          activeOpacity={theme.interaction.activeOpacity}
          style={styles.reregisterLink}
        >
          <Text variant="caption" weight="600" color={theme.colors.text.secondary}>
            Re-register
          </Text>
        </TouchableOpacity>
      )}
    </Card>
  );
};

const styles = StyleSheet.create({
  card: {
    marginBottom: theme.spacing[4],
  },
  warningCard: {
    borderColor: theme.colors.status.late.border,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing[3],
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: theme.borderRadius.md,
    justifyContent: 'center',
    alignItems: 'center',
  },
  warningIconWrap: {
    backgroundColor: theme.colors.warningLight,
  },
  successIconWrap: {
    backgroundColor: theme.colors.successLight,
  },
  textWrap: {
    flex: 1,
    gap: 2,
  },
  ctaButton: {
    marginTop: theme.spacing[3],
  },
  reregisterLink: {
    marginTop: theme.spacing[2],
    alignSelf: 'flex-end',
  },
});
