/**
 * StudentCard Component
 *
 * Displays student information in live attendance view.
 * Shows avatar, name, student ID, status badge, and detection indicator.
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
        {/* Avatar */}
        <View style={styles.avatar}>
          <Avatar
            firstName={firstName}
            lastName={lastName}
            size="md"
          />
        </View>

        {/* Info */}
        <View style={styles.info}>
          {/* Name and detection indicator */}
          <View style={styles.nameRow}>
            <Text variant="body" weight="600" numberOfLines={1} style={styles.name}>
              {student.student_name}
            </Text>
            {isCurrentlyDetected && <View style={styles.detectionDot} />}
          </View>

          {/* Student ID */}
          <Text variant="bodySmall" color={theme.colors.text.secondary} style={styles.studentId}>
            {student.student_id}
          </Text>

          {/* Last seen */}
          {student.last_seen_at && !isCurrentlyDetected && (
            <Text variant="caption" color={theme.colors.text.tertiary}>
              Last seen {formatTimeAgo(student.last_seen_at)}
            </Text>
          )}
        </View>

        {/* Status badge */}
        <Badge status={student.status} size="sm" />
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
  avatar: {
    marginRight: theme.spacing[3], // 12px
  },
  info: {
    flex: 1,
    marginRight: theme.spacing[3], // 12px
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: theme.spacing[1], // 4px
  },
  name: {
    flex: 1,
  },
  detectionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: theme.colors.success,
    marginLeft: theme.spacing[2], // 8px
  },
  studentId: {
    marginBottom: theme.spacing[1], // 4px
  },
});
