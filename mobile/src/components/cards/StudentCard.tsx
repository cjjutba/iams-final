/**
 * StudentCard Component
 *
 * Displays student information in live attendance view.
 * Shows avatar, name, student ID, status badge, and detection indicator.
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import type { LiveAttendanceStudent } from '../../types';
import { theme } from '../../constants';
import { formatTimeAgo, formatName } from '../../utils';
import { Card, Text, Avatar, Badge } from '../ui';

interface StudentCardProps {
  student: LiveAttendanceStudent;
  onPress?: () => void;
}

export const StudentCard: React.FC<StudentCardProps> = ({ student, onPress }) => {
  const isCurrentlyDetected = student.consecutiveMisses === 0;
  const firstName = student.name.split(' ')[0];
  const lastName = student.name.split(' ').slice(1).join(' ');

  return (
    <Card onPress={onPress} style={styles.card}>
      <View style={styles.content}>
        {/* Avatar */}
        <Avatar
          firstName={firstName}
          lastName={lastName}
          size="md"
          style={styles.avatar}
        />

        {/* Info */}
        <View style={styles.info}>
          {/* Name and detection indicator */}
          <View style={styles.nameRow}>
            <Text variant="body" weight="semibold" numberOfLines={1} style={styles.name}>
              {student.name}
            </Text>
            {isCurrentlyDetected && <View style={styles.detectionDot} />}
          </View>

          {/* Student ID */}
          <Text variant="bodySmall" color={theme.colors.text.secondary} style={styles.studentId}>
            {student.studentId}
          </Text>

          {/* Last seen */}
          {student.lastSeen && !isCurrentlyDetected && (
            <Text variant="caption" color={theme.colors.text.tertiary}>
              Last seen {formatTimeAgo(student.lastSeen)}
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
    backgroundColor: theme.colors.status.success,
    marginLeft: theme.spacing[2], // 8px
  },
  studentId: {
    marginBottom: theme.spacing[1], // 4px
  },
});
