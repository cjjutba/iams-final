/**
 * AttendanceOverviewCard Component
 *
 * Displays a segmented horizontal bar chart showing attendance breakdown
 * with proportional width segments for each status (present, late, absent,
 * early_leave), along with a large overall attendance percentage.
 *
 * Pure View-based implementation -- no third-party chart library.
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import { theme } from '../../constants';
import { Card, Text } from '../ui';

interface AttendanceOverviewCardProps {
  present: number;
  late: number;
  absent: number;
  earlyLeave: number;
  attendanceRate: number;
}

/** Segment definition for the horizontal bar */
interface Segment {
  key: string;
  label: string;
  count: number;
  bg: string;
  fg: string;
}

export const AttendanceOverviewCard: React.FC<AttendanceOverviewCardProps> = ({
  present,
  late,
  absent,
  earlyLeave,
  attendanceRate,
}) => {
  const total = present + late + absent + earlyLeave;

  const segments: Segment[] = [
    {
      key: 'present',
      label: 'Present',
      count: present,
      bg: theme.colors.status.present.bg,
      fg: theme.colors.status.present.fg,
    },
    {
      key: 'late',
      label: 'Late',
      count: late,
      bg: theme.colors.status.late.bg,
      fg: theme.colors.status.late.fg,
    },
    {
      key: 'absent',
      label: 'Absent',
      count: absent,
      bg: theme.colors.status.absent.bg,
      fg: theme.colors.status.absent.fg,
    },
    {
      key: 'early_leave',
      label: 'Early Leave',
      count: earlyLeave,
      bg: theme.colors.status.early_leave.bg,
      fg: theme.colors.status.early_leave.fg,
    },
  ];

  // Only render segments that have a non-zero count
  const activeSegments = segments.filter((s) => s.count > 0);

  return (
    <Card variant="outlined" style={styles.card}>
      {/* Header row: title + large percentage */}
      <View style={styles.headerRow}>
        <Text variant="bodySmall" weight="600" color={theme.colors.text.secondary}>
          Attendance Overview
        </Text>
        <Text variant="h2" weight="700">
          {attendanceRate.toFixed(1)}%
        </Text>
      </View>

      {/* Segmented horizontal bar */}
      <View style={styles.barContainer}>
        {total === 0 ? (
          // Empty state: single gray bar
          <View style={[styles.barSegment, styles.emptyBar, { flex: 1 }]} />
        ) : (
          activeSegments.map((segment, index) => (
            <View
              key={segment.key}
              style={[
                styles.barSegment,
                {
                  flex: segment.count,
                  backgroundColor: segment.bg,
                },
                // Round left corners on first segment
                index === 0 && styles.barFirstSegment,
                // Round right corners on last segment
                index === activeSegments.length - 1 && styles.barLastSegment,
              ]}
            />
          ))
        )}
      </View>

      {/* Legend row with counts */}
      <View style={styles.legendRow}>
        {segments.map((segment) => (
          <View key={segment.key} style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: segment.fg }]} />
            <View style={styles.legendTextWrap}>
              <Text variant="caption" color={theme.colors.text.tertiary}>
                {segment.label}
              </Text>
              <Text variant="bodySmall" weight="600">
                {segment.count}
              </Text>
            </View>
          </View>
        ))}
      </View>
    </Card>
  );
};

const BAR_HEIGHT = 12;

const styles = StyleSheet.create({
  card: {
    marginBottom: theme.spacing[4],
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing[3],
  },
  barContainer: {
    flexDirection: 'row',
    height: BAR_HEIGHT,
    borderRadius: BAR_HEIGHT / 2,
    overflow: 'hidden',
    marginBottom: theme.spacing[4],
  },
  barSegment: {
    height: BAR_HEIGHT,
  },
  barFirstSegment: {
    borderTopLeftRadius: BAR_HEIGHT / 2,
    borderBottomLeftRadius: BAR_HEIGHT / 2,
  },
  barLastSegment: {
    borderTopRightRadius: BAR_HEIGHT / 2,
    borderBottomRightRadius: BAR_HEIGHT / 2,
  },
  emptyBar: {
    backgroundColor: theme.colors.secondary,
    borderRadius: BAR_HEIGHT / 2,
  },
  legendRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: theme.spacing[3],
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing[1],
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  legendTextWrap: {
    gap: 1,
  },
});
