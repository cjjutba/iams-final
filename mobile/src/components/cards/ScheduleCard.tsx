/**
 * ScheduleCard Component
 *
 * Displays schedule/class information with time, subject, room, and faculty.
 * Clean flat card with 1px border.
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import type { Schedule } from '../../types';
import { theme } from '../../constants';
import { formatTime } from '../../utils';
import { Card, Text } from '../ui';

interface ScheduleCardProps {
  schedule: Schedule;
  onPress?: () => void;
}

export const ScheduleCard: React.FC<ScheduleCardProps> = ({ schedule, onPress }) => {
  return (
    <Card onPress={onPress} style={styles.card}>
      <Text variant="body" weight="700">
        {formatTime(schedule.start_time)}
      </Text>
      <Text variant="body" weight="600" numberOfLines={1} style={styles.subject}>
        {schedule.subject_name}
      </Text>
      <Text variant="caption" color={theme.colors.text.tertiary}>
        {schedule.subject_code}
      </Text>
      <View style={styles.metaRow}>
        <Text variant="bodySmall" color={theme.colors.text.secondary}>
          {schedule.room_name}
        </Text>
        {schedule.faculty_name && (
          <Text variant="bodySmall" color={theme.colors.text.secondary}>
            {' \u2022 '}{schedule.faculty_name}
          </Text>
        )}
      </View>
    </Card>
  );
};

const styles = StyleSheet.create({
  card: {
    marginBottom: theme.spacing[2],
  },
  subject: {
    marginTop: theme.spacing[1],
    marginBottom: 2,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: theme.spacing[2],
  },
});
