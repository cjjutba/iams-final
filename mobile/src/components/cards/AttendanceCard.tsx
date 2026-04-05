/**
 * AttendanceCard Component
 *
 * Displays attendance information for a class/schedule.
 * Compact flat card with 1px border.
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
        <View style={styles.mainInfo}>
          <Text variant="caption" color={theme.colors.text.tertiary}>
            {schedule.subject_code}
          </Text>
          <Text variant="bodySmall" weight="600" numberOfLines={1} style={styles.subject}>
            {schedule.subject_name}
          </Text>
          <Text variant="caption" color={theme.colors.text.secondary}>
            {formatTime(schedule.start_time)} - {formatTime(schedule.end_time)} {'\u2022'} {schedule.room_name}
          </Text>
          {(displayStatus || displayScore !== undefined) && (
            <View style={styles.statusRow}>
              {displayStatus && <Badge status={displayStatus} size="sm" />}
              {displayScore !== undefined && (
                <Text variant="caption" color={theme.colors.text.secondary} style={styles.score}>
                  {formatPercentage(displayScore)} present
                </Text>
              )}
            </View>
          )}
        </View>

        {onPress && (
          <ChevronRight size={18} color={theme.colors.text.tertiary} />
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
    justifyContent: 'space-between',
  },
  mainInfo: {
    flex: 1,
    gap: 2,
  },
  subject: {
    marginBottom: 2,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: theme.spacing[1],
  },
  score: {
    marginLeft: theme.spacing[2],
  },
});
