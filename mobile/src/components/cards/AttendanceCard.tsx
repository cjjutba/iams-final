/**
 * AttendanceCard Component
 *
 * Displays attendance information for a class/schedule.
 * Shows subject details, time, room, status, and presence score.
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import { ChevronRight } from 'lucide-react-native';
import type { ScheduleWithAttendance, AttendanceStatus } from '../../types';
import { theme } from '../../constants';
import { formatTime, formatPercentage } from '../../utils';
import { Card, Text, Badge } from '../ui';

interface AttendanceCardProps {
  schedule: ScheduleWithAttendance;
  status?: AttendanceStatus;
  presenceScore?: number;
  onPress?: () => void;
}

export const AttendanceCard: React.FC<AttendanceCardProps> = ({
  schedule,
  status,
  presenceScore,
  onPress,
}) => {
  const displayStatus = status || schedule.today_attendance?.status as AttendanceStatus | undefined;
  const displayScore = presenceScore !== undefined ? presenceScore : schedule.today_attendance?.presence_score;

  return (
    <Card onPress={onPress} style={styles.card}>
      <View style={styles.content}>
        {/* Main info */}
        <View style={styles.mainInfo}>
          {/* Subject */}
          <Text variant="caption" color={theme.colors.text.tertiary} style={styles.code}>
            {schedule.subject_code}
          </Text>
          <Text variant="body" weight="600" numberOfLines={1} style={styles.subject}>
            {schedule.subject_name}
          </Text>

          {/* Time and room */}
          <View style={styles.metaRow}>
            <Text variant="bodySmall" color={theme.colors.text.secondary}>
              {formatTime(schedule.start_time)} - {formatTime(schedule.end_time)}
            </Text>
            <Text variant="bodySmall" color={theme.colors.text.tertiary}>
              {' • '}
            </Text>
            <Text variant="bodySmall" color={theme.colors.text.secondary}>
              {schedule.room_name}
            </Text>
          </View>

          {/* Status and score */}
          <View style={styles.statusRow}>
            {displayStatus && <Badge status={displayStatus} size="sm" />}

            {displayScore !== undefined && (
              <Text
                variant="bodySmall"
                color={theme.colors.text.secondary}
                style={styles.score}
              >
                {formatPercentage(displayScore)} present
              </Text>
            )}
          </View>
        </View>

        {/* Chevron */}
        {onPress && (
          <ChevronRight size={20} color={theme.colors.text.tertiary} style={styles.chevron} />
        )}
      </View>
    </Card>
  );
};

const styles = StyleSheet.create({
  card: {
    marginBottom: theme.spacing[3], // 12px
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  mainInfo: {
    flex: 1,
  },
  code: {
    marginBottom: theme.spacing[1], // 4px
  },
  subject: {
    marginBottom: theme.spacing[2], // 8px
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: theme.spacing[2], // 8px
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  score: {
    marginLeft: theme.spacing[2], // 8px
  },
  chevron: {
    marginLeft: theme.spacing[3], // 12px
  },
});
