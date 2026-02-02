/**
 * Student Attendance Detail Screen
 *
 * Shows detailed attendance information:
 * - Subject and date
 * - Status badge
 * - Check-in/out times
 * - Presence score
 * - Presence timeline with logs
 */

import React, { useEffect, useState } from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import { useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import { Clock, TrendingUp } from 'lucide-react-native';
import { attendanceService } from '../../services';
import { theme, strings } from '../../constants';
import { formatDate, formatTime, formatPercentage } from '../../utils';
import type { StudentStackParamList, AttendanceRecord, PresenceLog } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Badge, Divider, Loader } from '../../components/ui';

type AttendanceDetailRouteProp = RouteProp<StudentStackParamList, 'AttendanceDetail'>;

export const StudentAttendanceDetailScreen: React.FC = () => {
  const route = useRoute<AttendanceDetailRouteProp>();
  const { attendanceId, scheduleId } = route.params;

  const [attendance, setAttendance] = useState<AttendanceRecord | null>(null);
  const [logs, setLogs] = useState<PresenceLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadDetails();
  }, []);

  const loadDetails = async () => {
    try {
      setIsLoading(true);

      if (attendanceId) {
        const [attendanceData, logsData] = await Promise.all([
          attendanceService.getAttendanceDetail(attendanceId),
          attendanceService.getPresenceLogs(attendanceId),
        ]);
        setAttendance(attendanceData);
        setLogs(logsData);
      } else if (scheduleId) {
        const attendanceData = await attendanceService.getTodayAttendance(scheduleId);
        if (attendanceData) {
          setAttendance(attendanceData);
          const logsData = await attendanceService.getPresenceLogs(attendanceData.id);
          setLogs(logsData);
        }
      }
    } catch (error) {
      console.error('Failed to load attendance details:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title="Attendance Details" />
        <Loader fullScreen message="Loading..." />
      </ScreenLayout>
    );
  }

  if (!attendance) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title="Attendance Details" />
        <View style={styles.emptyContainer}>
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            No attendance record found
          </Text>
        </View>
      </ScreenLayout>
    );
  }

  return (
    <ScreenLayout safeArea scrollable>
      <Header showBack title={formatDate(attendance.date, 'MMM d, yyyy')} />

      <View style={styles.container}>
        {/* Subject info */}
        <Card style={styles.card}>
          <Text variant="body" weight="semibold" style={styles.subjectName}>
            {attendance.subjectName || 'Subject'}
          </Text>
          <Text variant="caption" color={theme.colors.text.tertiary}>
            {attendance.subjectCode || ''}
          </Text>
        </Card>

        {/* Status */}
        <View style={styles.statusContainer}>
          <Badge status={attendance.status} size="md" />
        </View>

        {/* Stats */}
        <View style={styles.statsRow}>
          {attendance.checkInTime && (
            <Card variant="outlined" style={styles.statCard}>
              <Clock size={20} color={theme.colors.text.tertiary} style={styles.statIcon} />
              <Text variant="caption" color={theme.colors.text.tertiary}>
                Check-in
              </Text>
              <Text variant="body" weight="semibold">
                {formatTime(attendance.checkInTime)}
              </Text>
            </Card>
          )}

          {attendance.presenceScore !== undefined && (
            <Card variant="outlined" style={styles.statCard}>
              <TrendingUp size={20} color={theme.colors.text.tertiary} style={styles.statIcon} />
              <Text variant="caption" color={theme.colors.text.tertiary}>
                Presence Score
              </Text>
              <Text variant="body" weight="semibold">
                {formatPercentage(attendance.presenceScore)}
              </Text>
            </Card>
          )}
        </View>

        <Divider spacing="lg" />

        {/* Presence timeline */}
        <Text variant="h4" weight="semibold" style={styles.sectionTitle}>
          {strings.attendance.presenceTimeline}
        </Text>

        {logs.length > 0 ? (
          <Card variant="outlined">
            {logs.map((log, index) => (
              <View key={log.id}>
                <View style={styles.logItem}>
                  <View style={styles.logIndicator}>
                    <View
                      style={[
                        styles.logDot,
                        {
                          backgroundColor: log.detected
                            ? theme.colors.status.success
                            : theme.colors.status.error,
                        },
                      ]}
                    />
                    {index < logs.length - 1 && <View style={styles.logLine} />}
                  </View>

                  <View style={styles.logContent}>
                    <View style={styles.logHeader}>
                      <Text variant="body" weight="medium">
                        Scan #{log.scanNumber}
                      </Text>
                      <Text variant="caption" color={theme.colors.text.tertiary}>
                        {formatTime(log.scanTime)}
                      </Text>
                    </View>

                    <Text
                      variant="bodySmall"
                      color={
                        log.detected ? theme.colors.status.success : theme.colors.status.error
                      }
                    >
                      {log.detected ? strings.attendance.detected : strings.attendance.notDetected}
                    </Text>

                    {log.confidence && (
                      <Text variant="caption" color={theme.colors.text.tertiary}>
                        Confidence: {formatPercentage(log.confidence)}
                      </Text>
                    )}
                  </View>
                </View>
              </View>
            ))}
          </Card>
        ) : (
          <Card variant="outlined">
            <Text variant="bodySmall" color={theme.colors.text.secondary} align="center">
              No presence logs available
            </Text>
          </Card>
        )}
      </View>
    </ScreenLayout>
  );
};

const styles = StyleSheet.create({
  container: {
    padding: theme.spacing[4],
  },
  card: {
    marginBottom: theme.spacing[4],
  },
  subjectName: {
    marginBottom: theme.spacing[1],
  },
  statusContainer: {
    alignItems: 'center',
    marginBottom: theme.spacing[6],
  },
  statsRow: {
    flexDirection: 'row',
    marginBottom: theme.spacing[6],
    gap: theme.spacing[3],
  },
  statCard: {
    flex: 1,
    alignItems: 'center',
  },
  statIcon: {
    marginBottom: theme.spacing[2],
  },
  sectionTitle: {
    marginBottom: theme.spacing[4],
  },
  logItem: {
    flexDirection: 'row',
    paddingVertical: theme.spacing[3],
  },
  logIndicator: {
    alignItems: 'center',
    marginRight: theme.spacing[4],
  },
  logDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  logLine: {
    width: 2,
    flex: 1,
    backgroundColor: theme.colors.border,
    marginTop: theme.spacing[2],
  },
  logContent: {
    flex: 1,
  },
  logHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: theme.spacing[1],
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
