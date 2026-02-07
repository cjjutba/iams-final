/**
 * Student Attendance Detail Screen
 *
 * Shows detailed attendance information:
 * - Subject and date info
 * - Status badge
 * - Check-in/out times
 * - Presence score with scan counts
 * - Presence timeline with logs
 * - Loading, error, and empty states with retry
 */

import React, { useEffect, useState, useCallback } from 'react';
import { View, StyleSheet, ScrollView, RefreshControl } from 'react-native';
import { useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import { Clock, TrendingUp, RefreshCw } from 'lucide-react-native';
import { attendanceService } from '../../services';
import { theme, strings } from '../../constants';
import { formatDate, formatTime, formatPercentage, getErrorMessage } from '../../utils';
import type { StudentStackParamList, AttendanceRecord, PresenceLog } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Badge, Divider, Loader, Button } from '../../components/ui';

type AttendanceDetailRouteProp = RouteProp<StudentStackParamList, 'AttendanceDetail'>;

export const StudentAttendanceDetailScreen: React.FC = () => {
  const route = useRoute<AttendanceDetailRouteProp>();
  const { attendanceId, scheduleId, date } = route.params;

  const [attendance, setAttendance] = useState<AttendanceRecord | null>(null);
  const [logs, setLogs] = useState<PresenceLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ---------- data fetching ----------

  const loadDetails = useCallback(
    async (silent = false) => {
      if (!silent) setIsLoading(true);
      setError(null);

      try {
        if (attendanceId) {
          // Fetch by attendance ID (from history or direct link)
          const [attendanceData, logsData] = await Promise.all([
            attendanceService.getAttendanceDetail(attendanceId),
            attendanceService.getPresenceLogs(attendanceId),
          ]);
          setAttendance(attendanceData);
          setLogs(logsData);
        } else if (scheduleId) {
          // Fetch today's attendance for this schedule (API returns an array)
          const attendanceArr = await attendanceService.getTodayAttendance(scheduleId);
          const firstRecord = attendanceArr?.[0] ?? null;
          if (firstRecord) {
            setAttendance(firstRecord);
            const logsData = await attendanceService.getPresenceLogs(firstRecord.id);
            setLogs(logsData);
          } else {
            // No attendance record yet for today
            setAttendance(null);
            setLogs([]);
          }
        }
      } catch (err) {
        console.error('Failed to load attendance details:', err);
        setError(getErrorMessage(err));
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [attendanceId, scheduleId]
  );

  useEffect(() => {
    loadDetails();
  }, [loadDetails]);

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    loadDetails(true);
  }, [loadDetails]);

  // ---------- loading state ----------

  if (isLoading) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title="Attendance Details" />
        <Loader fullScreen message={strings.common.loading} />
      </ScreenLayout>
    );
  }

  // ---------- error state ----------

  if (error) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title="Attendance Details" />
        <View style={styles.errorContainer}>
          <RefreshCw size={40} color={theme.colors.text.tertiary} style={styles.errorIcon} />
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            {error}
          </Text>
          <Button
            variant="secondary"
            size="md"
            onPress={() => loadDetails()}
            style={styles.retryButton}
          >
            {strings.common.retry}
          </Button>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- empty state (no record found) ----------

  if (!attendance) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title="Attendance Details" />
        <View style={styles.emptyContainer}>
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            No attendance record found
          </Text>
          <Text
            variant="bodySmall"
            color={theme.colors.text.tertiary}
            align="center"
            style={styles.emptySubtext}
          >
            Attendance has not been recorded yet for this class
          </Text>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- header title ----------

  const headerTitle = date
    ? formatDate(date, 'MMM d, yyyy')
    : formatDate(attendance.date, 'MMM d, yyyy');

  // ---------- main render ----------

  return (
    <ScreenLayout safeArea padded={false}>
      <Header showBack title={headerTitle} />

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleRefresh}
            colors={[theme.colors.primary]}
            tintColor={theme.colors.primary}
          />
        }
      >
        <View style={styles.container}>
          {/* Status */}
          <View style={styles.statusContainer}>
            <Badge status={attendance.status} size="md" />
          </View>

          {/* Stats row */}
          <View style={styles.statsRow}>
            {/* Check-in time */}
            {attendance.check_in_time && (
              <Card variant="outlined" style={styles.statCard}>
                <Clock
                  size={20}
                  color={theme.colors.text.tertiary}
                  style={styles.statIcon}
                />
                <Text variant="caption" color={theme.colors.text.tertiary}>
                  {strings.attendance.checkInTime}
                </Text>
                <Text variant="body" weight="600">
                  {formatTime(attendance.check_in_time)}
                </Text>
              </Card>
            )}

            {/* Presence score */}
            {attendance.presence_score !== undefined && attendance.presence_score !== null && (
              <Card variant="outlined" style={styles.statCard}>
                <TrendingUp
                  size={20}
                  color={theme.colors.text.tertiary}
                  style={styles.statIcon}
                />
                <Text variant="caption" color={theme.colors.text.tertiary}>
                  {strings.attendance.presenceScore}
                </Text>
                <Text variant="body" weight="600">
                  {formatPercentage(attendance.presence_score)}
                </Text>
              </Card>
            )}
          </View>

          {/* Scan counts */}
          {attendance.total_scans !== undefined && attendance.total_scans !== null && (
            <Card variant="outlined" style={styles.scanCard}>
              <View style={styles.scanRow}>
                <View style={styles.scanItem}>
                  <Text variant="caption" color={theme.colors.text.tertiary}>
                    {strings.attendance.totalScans}
                  </Text>
                  <Text variant="h3" weight="700">
                    {attendance.total_scans}
                  </Text>
                </View>
                <View style={styles.scanDivider} />
                <View style={styles.scanItem}>
                  <Text variant="caption" color={theme.colors.text.tertiary}>
                    {strings.attendance.scansPresent}
                  </Text>
                  <Text variant="h3" weight="700">
                    {attendance.scans_present ?? 0}
                  </Text>
                </View>
              </View>
            </Card>
          )}

          {/* Remarks */}
          {attendance.remarks && (
            <Card variant="outlined" style={styles.remarksCard}>
              <Text variant="caption" color={theme.colors.text.tertiary} style={styles.remarksLabel}>
                Remarks
              </Text>
              <Text variant="bodySmall" color={theme.colors.text.secondary}>
                {attendance.remarks}
              </Text>
            </Card>
          )}

          <Divider spacing={6} />

          {/* Presence timeline */}
          <Text variant="h4" weight="600" style={styles.sectionTitle}>
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
                              ? theme.colors.success
                              : theme.colors.error,
                          },
                        ]}
                      />
                      {index < logs.length - 1 && <View style={styles.logLine} />}
                    </View>

                    <View style={styles.logContent}>
                      <View style={styles.logHeader}>
                        <Text variant="body" weight="500">
                          Scan #{log.scan_number}
                        </Text>
                        <Text variant="caption" color={theme.colors.text.tertiary}>
                          {formatTime(log.scan_time)}
                        </Text>
                      </View>

                      <Text
                        variant="bodySmall"
                        color={log.detected ? theme.colors.success : theme.colors.error}
                      >
                        {log.detected
                          ? strings.attendance.detected
                          : strings.attendance.notDetected}
                      </Text>

                      {log.confidence !== undefined && log.confidence !== null && (
                        <Text variant="caption" color={theme.colors.text.tertiary}>
                          {strings.attendance.confidence}: {formatPercentage(log.confidence * 100)}
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
      </ScrollView>
    </ScreenLayout>
  );
};

const styles = StyleSheet.create({
  scrollContent: {
    flexGrow: 1,
  },
  container: {
    padding: theme.spacing[4],
  },
  statusContainer: {
    alignItems: 'center',
    marginBottom: theme.spacing[6],
  },
  statsRow: {
    flexDirection: 'row',
    marginBottom: theme.spacing[4],
    gap: theme.spacing[3],
  },
  statCard: {
    flex: 1,
    alignItems: 'center',
  },
  statIcon: {
    marginBottom: theme.spacing[2],
  },
  scanCard: {
    marginBottom: theme.spacing[4],
  },
  scanRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  scanItem: {
    flex: 1,
    alignItems: 'center',
  },
  scanDivider: {
    width: 1,
    height: 40,
    backgroundColor: theme.colors.border,
  },
  remarksCard: {
    marginBottom: theme.spacing[4],
  },
  remarksLabel: {
    marginBottom: theme.spacing[1],
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
    paddingHorizontal: theme.spacing[6],
  },
  emptySubtext: {
    marginTop: theme.spacing[2],
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: theme.spacing[6],
  },
  errorIcon: {
    marginBottom: theme.spacing[4],
  },
  retryButton: {
    marginTop: theme.spacing[4],
  },
});
