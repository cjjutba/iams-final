/**
 * FacultyScheduleCard Component
 *
 * Enhanced schedule card for faculty showing per-class attendance statistics.
 * Displays subject info, time range, attendance summary badges,
 * attendance rate percentage, and session status indicator.
 */

import React from 'react';
import { View, StyleSheet, TouchableOpacity } from 'react-native';
import { theme } from '../../constants';
import { formatTime } from '../../utils';
import { Text } from '../ui';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface FacultyScheduleCardProps {
  scheduleId: string;
  subjectCode: string;
  subjectName: string;
  startTime: string;
  endTime: string;
  roomName?: string;
  attendanceRate?: number;
  presentCount?: number;
  lateCount?: number;
  absentCount?: number;
  sessionActive?: boolean;
  onPress?: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const FacultyScheduleCard: React.FC<FacultyScheduleCardProps> = ({
  subjectCode,
  subjectName,
  startTime,
  endTime,
  roomName,
  attendanceRate,
  presentCount,
  lateCount,
  absentCount,
  sessionActive = false,
  onPress,
}) => {
  const hasAttendanceData =
    presentCount !== undefined ||
    lateCount !== undefined ||
    absentCount !== undefined;

  const rateValue = attendanceRate ?? 0;

  const content = (
    <View style={styles.card}>
      {/* Left accent bar */}
      <View
        style={[
          styles.accentBar,
          sessionActive ? styles.accentBarActive : styles.accentBarDefault,
        ]}
      />

      <View style={styles.mainContent}>
        {/* Top row: subject info + session status */}
        <View style={styles.topRow}>
          <View style={styles.subjectInfo}>
            <Text variant="caption" color={theme.colors.text.tertiary} style={styles.subjectCode}>
              {subjectCode}
            </Text>
            <Text variant="body" weight="600" numberOfLines={1}>
              {subjectName}
            </Text>
          </View>

          {/* Session status dot */}
          <View style={styles.statusContainer}>
            <View
              style={[
                styles.statusDot,
                sessionActive ? styles.statusDotActive : styles.statusDotInactive,
              ]}
            />
            <Text
              variant="caption"
              color={sessionActive ? theme.colors.success : theme.colors.text.tertiary}
            >
              {sessionActive ? 'Active' : 'Inactive'}
            </Text>
          </View>
        </View>

        {/* Time and room */}
        <Text variant="bodySmall" color={theme.colors.text.secondary} style={styles.timeRow}>
          {formatTime(startTime)} - {formatTime(endTime)}
          {roomName ? ` \u2022 ${roomName}` : ''}
        </Text>

        {/* Attendance stats row */}
        {hasAttendanceData && (
          <View style={styles.statsRow}>
            {/* Attendance badges */}
            <View style={styles.badgesRow}>
              {presentCount !== undefined && (
                <View style={[styles.badge, styles.badgePresent]}>
                  <Text variant="caption" weight="600" color={theme.colors.status.present.fg}>
                    {presentCount} P
                  </Text>
                </View>
              )}
              {lateCount !== undefined && lateCount > 0 && (
                <View style={[styles.badge, styles.badgeLate]}>
                  <Text variant="caption" weight="600" color={theme.colors.status.late.fg}>
                    {lateCount} L
                  </Text>
                </View>
              )}
              {absentCount !== undefined && (
                <View style={[styles.badge, styles.badgeAbsent]}>
                  <Text variant="caption" weight="600" color={theme.colors.status.absent.fg}>
                    {absentCount} A
                  </Text>
                </View>
              )}
            </View>

            {/* Attendance rate */}
            {attendanceRate !== undefined && (
              <Text
                variant="bodySmall"
                weight="700"
                color={
                  rateValue >= 80
                    ? theme.colors.success
                    : rateValue >= 60
                    ? theme.colors.warning
                    : theme.colors.error
                }
              >
                {rateValue.toFixed(0)}%
              </Text>
            )}
          </View>
        )}
      </View>
    </View>
  );

  if (onPress) {
    return (
      <TouchableOpacity
        onPress={onPress}
        activeOpacity={theme.interaction.activeOpacity}
      >
        {content}
      </TouchableOpacity>
    );
  }

  return content;
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    backgroundColor: theme.colors.card,
    borderRadius: theme.borderRadius.lg,
    marginBottom: theme.spacing[3],
    ...theme.shadows.sm,
  },
  accentBar: {
    width: 4,
    borderTopLeftRadius: theme.borderRadius.lg,
    borderBottomLeftRadius: theme.borderRadius.lg,
  },
  accentBarDefault: {
    backgroundColor: theme.colors.primary,
  },
  accentBarActive: {
    backgroundColor: theme.colors.success,
  },
  mainContent: {
    flex: 1,
    padding: theme.spacing[4],
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: theme.spacing[1],
  },
  subjectInfo: {
    flex: 1,
    marginRight: theme.spacing[3],
  },
  subjectCode: {
    marginBottom: theme.spacing[1],
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  statusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: theme.spacing[1],
  },
  statusDotActive: {
    backgroundColor: theme.colors.success,
  },
  statusDotInactive: {
    backgroundColor: theme.colors.text.tertiary,
  },
  timeRow: {
    marginBottom: theme.spacing[3],
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: theme.spacing[3],
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
  },
  badgesRow: {
    flexDirection: 'row',
    gap: theme.spacing[2],
  },
  badge: {
    paddingHorizontal: theme.spacing[2],
    paddingVertical: theme.spacing[1],
    borderRadius: theme.borderRadius.sm,
  },
  badgePresent: {
    backgroundColor: theme.colors.status.present.bg,
  },
  badgeLate: {
    backgroundColor: theme.colors.status.late.bg,
  },
  badgeAbsent: {
    backgroundColor: theme.colors.status.absent.bg,
  },
});
