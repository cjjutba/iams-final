/**
 * StudentCard Component
 *
 * Displays student information in live attendance view.
 * Compact flat card with 1px border.
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import type { StudentAttendanceStatus } from '../../types';
import { theme } from '../../constants';
import { formatTimeAgo } from '../../utils';
import { Card, Text, Avatar, Badge } from '../ui';

interface StudentCardProps {
  student: StudentAttendanceStatus;
  onPress?: () => void;
}

export const StudentCard: React.FC<StudentCardProps> = ({ student, onPress }) => {
  const isCurrentlyDetected = (student.consecutive_misses ?? 0) === 0;
  const nameParts = (student.student_name ?? '').split(' ');
  const firstName = nameParts[0] ?? '';
  const lastName = nameParts.slice(1).join(' ');

  return (
    <Card onPress={onPress} style={styles.card}>
      <View style={styles.content}>
        <Avatar firstName={firstName} lastName={lastName} size="md" />

        <View style={styles.info}>
          <View style={styles.nameRow}>
            <Text variant="bodySmall" weight="600" numberOfLines={1} style={styles.name}>
              {student.student_name}
            </Text>
            {isCurrentlyDetected && <View style={styles.detectionDot} />}
          </View>
          <Text variant="caption" color={theme.colors.text.secondary}>
            {student.student_id}
          </Text>
          {student.last_seen_at && !isCurrentlyDetected && (
            <Text variant="caption" color={theme.colors.text.tertiary}>
              Last seen {formatTimeAgo(student.last_seen_at)}
            </Text>
          )}
        </View>

        <Badge status={student.status} size="sm" />
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
    gap: theme.spacing[3],
  },
  info: {
    flex: 1,
    gap: 2,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  name: {
    flex: 1,
  },
  detectionDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: theme.colors.success,
    marginLeft: theme.spacing[2],
  },
});
