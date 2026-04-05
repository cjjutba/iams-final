/**
 * AlertCard Component
 *
 * Displays early leave alert information.
 * Compact flat card with 1px border.
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
        <View style={styles.iconContainer}>
          <AlertTriangle size={18} color={theme.colors.warning} />
        </View>

        <View style={styles.info}>
          <Text variant="bodySmall" weight="600" numberOfLines={1}>
            {event.student_name}
          </Text>
          <Text variant="caption" color={theme.colors.text.secondary}>
            Left early {'\u00B7'} {formatTimeAgo(event.detected_at)}
          </Text>
        </View>

        {event.consecutive_misses > 0 && (
          <View style={styles.badge}>
            <Text variant="caption" weight="600" color={theme.colors.warning}>
              {event.consecutive_misses}
            </Text>
          </View>
        )}
      </View>
    </Card>
  );
};

const styles = StyleSheet.create({
  card: {
    marginBottom: theme.spacing[2],
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  iconContainer: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: theme.colors.warningLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: theme.spacing[3],
  },
  info: {
    flex: 1,
    marginRight: theme.spacing[2],
    gap: 2,
  },
  badge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: theme.colors.warningLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
