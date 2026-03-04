/**
 * AlertCard Component
 *
 * Displays early leave alert information.
 * Shows warning icon, student name, and time detected.
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import { AlertTriangle } from 'lucide-react-native';
import type { EarlyLeaveEvent } from '../../types';
import { theme } from '../../constants';
import { formatTimeAgo } from '../../utils';
import { Card, Text } from '../ui';

interface AlertCardProps {
  event: EarlyLeaveEvent;
  onPress?: () => void;
}

export const AlertCard: React.FC<AlertCardProps> = ({ event, onPress }) => {
  return (
    <Card onPress={onPress} style={styles.card}>
      <View style={styles.content}>
        {/* Warning icon */}
        <View style={styles.iconContainer}>
          <AlertTriangle size={24} color={theme.colors.warning} />
        </View>

        {/* Info */}
        <View style={styles.info}>
          {/* Student name */}
          <Text variant="body" weight="600" numberOfLines={1} style={styles.name}>
            {event.student_name}
          </Text>

          {/* Alert message */}
          <Text variant="bodySmall" color={theme.colors.text.secondary} style={styles.message}>
            Left early
          </Text>

          {/* Time */}
          <Text variant="caption" color={theme.colors.text.tertiary}>
            {formatTimeAgo(event.detected_at)}
          </Text>
        </View>

        {/* Consecutive misses indicator */}
        {event.consecutive_misses > 0 && (
          <View style={styles.badge}>
            <Text variant="caption" weight="600" color={theme.colors.warning}>
              {event.consecutive_misses} misses
            </Text>
          </View>
        )}
      </View>
    </Card>
  );
};

const styles = StyleSheet.create({
  card: {
    marginBottom: theme.spacing[2], // 8px
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  iconContainer: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: theme.colors.warningLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: theme.spacing[3], // 12px
  },
  info: {
    flex: 1,
    marginRight: theme.spacing[3], // 12px
  },
  name: {
    marginBottom: theme.spacing[1], // 4px
  },
  message: {
    marginBottom: theme.spacing[1], // 4px
  },
  badge: {
    paddingHorizontal: theme.spacing[2], // 8px
    paddingVertical: theme.spacing[1], // 4px
    backgroundColor: theme.colors.warningLight,
    borderRadius: theme.borderRadius.sm,
  },
});
