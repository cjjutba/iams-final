/**
 * ActivityFeedItem Component
 *
 * Compact row for displaying a single recent attendance activity entry.
 * Layout: status dot (left) | subject + date (center) | status badge (right)
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import { theme } from '../../constants';
import { Text, Badge } from '../ui';
import { AttendanceStatus } from '../../types';
import { getStatusColor } from '../../utils';

interface ActivityFeedItemProps {
  subjectCode: string;
  subjectName: string;
  date: string; // Human-readable date string (e.g., "Mar 04, 2026")
  status: 'present' | 'late' | 'absent' | 'early_leave';
}

export const ActivityFeedItem: React.FC<ActivityFeedItemProps> = ({
  subjectCode,
  subjectName,
  date,
  status,
}) => {
  const dotColor = getStatusColor(status as AttendanceStatus);

  return (
    <View style={styles.container}>
      {/* Left: colored status dot */}
      <View style={[styles.dot, { backgroundColor: dotColor }]} />

      {/* Center: subject info + date */}
      <View style={styles.centerContent}>
        <Text variant="bodySmall" weight="600" numberOfLines={1}>
          {subjectName}
        </Text>
        <Text variant="caption" color={theme.colors.text.tertiary}>
          {subjectCode} {'\u00B7'} {date}
        </Text>
      </View>

      {/* Right: status badge */}
      <Badge status={status as AttendanceStatus} size="sm" />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: theme.spacing[3],
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: theme.colors.border,
    gap: theme.spacing[3],
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  centerContent: {
    flex: 1,
    gap: 2,
  },
});
