/**
 * ScheduleCard Component
 *
 * Displays schedule/class information with time, subject, room, and faculty.
 * Features a left accent bar for visual emphasis.
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
      <View style={styles.content}>
        {/* Accent bar */}
        <View style={styles.accentBar} />

        {/* Main content */}
        <View style={styles.mainContent}>
          {/* Time */}
          <Text variant="h3" weight="700" style={styles.time}>
            {formatTime(schedule.start_time)}
          </Text>

          {/* Subject */}
          <Text variant="body" weight="600" numberOfLines={1} style={styles.subject}>
            {schedule.subject_name}
          </Text>
          <Text variant="caption" color={theme.colors.text.tertiary} style={styles.code}>
            {schedule.subject_code}
          </Text>

          {/* Meta info */}
          <View style={styles.metaRow}>
            <Text variant="bodySmall" color={theme.colors.text.secondary}>
              {schedule.room_name}
            </Text>
            {schedule.faculty_name && (
              <>
                <Text variant="bodySmall" color={theme.colors.text.tertiary}>
                  {' • '}
                </Text>
                <Text variant="bodySmall" color={theme.colors.text.secondary}>
                  {schedule.faculty_name}
                </Text>
              </>
            )}
          </View>
        </View>
      </View>
    </Card>
  );
};

const styles = StyleSheet.create({
  card: {
    marginBottom: theme.spacing[3], // 12px
    paddingLeft: 0,
  },
  content: {
    flexDirection: 'row',
  },
  accentBar: {
    width: 4,
    backgroundColor: theme.colors.primary,
    borderTopLeftRadius: theme.borderRadius.md,
    borderBottomLeftRadius: theme.borderRadius.md,
    marginRight: theme.spacing[4], // 16px
  },
  mainContent: {
    flex: 1,
    paddingVertical: theme.spacing[2], // 8px
    paddingRight: theme.spacing[4], // 16px
  },
  time: {
    marginBottom: theme.spacing[2], // 8px
  },
  subject: {
    marginBottom: theme.spacing[1], // 4px
  },
  code: {
    marginBottom: theme.spacing[2], // 8px
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
});
