/**
 * Faculty Student Detail Screen
 *
 * Shows detailed student information and attendance history
 * fetched from the API. Displays real stats (present/late/absent
 * counts, attendance rate) and recent attendance records.
 */

import React, { useEffect, useState, useCallback } from 'react';
import { View, StyleSheet, ScrollView, RefreshControl } from 'react-native';
import { useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import { RefreshCw } from 'lucide-react-native';
import { api } from '../../utils/api';
import { attendanceService } from '../../services';
import { useToast } from '../../hooks/useToast';
import { theme, strings } from '../../constants';
import { formatDate, formatPercentage, getErrorMessage } from '../../utils';
import type {
  FacultyStackParamList,
  AttendanceRecord,
  AttendanceSummary,
  ApiResponse,
  User,
} from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Avatar, Badge, Skeleton, Button } from '../../components/ui';

type StudentDetailRouteProp = RouteProp<FacultyStackParamList, 'StudentDetail'>;

export const FacultyStudentDetailScreen: React.FC = () => {
  const route = useRoute<StudentDetailRouteProp>();
  const { studentId, scheduleId } = route.params;
  const { showError } = useToast();

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [student, setStudent] = useState<User | null>(null);
  const [summary, setSummary] = useState<AttendanceSummary | null>(null);
  const [recentRecords, setRecentRecords] = useState<AttendanceRecord[]>([]);

  // ---------- data fetching ----------

  const loadStudentDetails = useCallback(
    async (silent = false) => {
      if (!silent) setIsLoading(true);
      setError(null);

      try {
        // Fetch student info, attendance summary, and recent records in parallel
        const [studentRes, summaryRes, historyRes] = await Promise.all([
          api.get<ApiResponse<User>>(`/auth/users/${studentId}`).catch(() => null),
          api.get<ApiResponse<AttendanceSummary>>('/attendance/summary', {
            params: { student_id: studentId, schedule_id: scheduleId },
          }).catch(() => null),
          api.get<ApiResponse<AttendanceRecord[]>>('/attendance/history', {
            params: {
              student_id: studentId,
              schedule_id: scheduleId,
              limit: 10,
            },
          }).catch(() => null),
        ]);

        if (studentRes?.data?.data) {
          setStudent(studentRes.data.data);
        }

        if (summaryRes?.data?.data) {
          setSummary(summaryRes.data.data);
        }

        if (historyRes?.data?.data) {
          setRecentRecords(
            Array.isArray(historyRes.data.data)
              ? historyRes.data.data
              : []
          );
        }
      } catch (err) {
        setError(getErrorMessage(err));
        showError(getErrorMessage(err), 'Load Failed');
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [studentId, scheduleId]
  );

  useEffect(() => {
    loadStudentDetails();
  }, [loadStudentDetails]);

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    loadStudentDetails(true);
  }, [loadStudentDetails]);

  // ---------- error state ----------

  if (error && !isRefreshing && !student && !summary) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title={strings.faculty.studentDetail} />
        <View style={styles.errorContainer}>
          <RefreshCw size={40} color={theme.colors.text.tertiary} style={styles.errorIcon} />
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            Unable to load student details. Please try again.
          </Text>
          <Button
            variant="secondary"
            size="md"
            onPress={() => loadStudentDetails()}
            style={styles.retryButton}
          >
            {strings.common.retry}
          </Button>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- loading state ----------

  if (isLoading && !student) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title={strings.faculty.studentDetail} />
        <View style={{ padding: theme.spacing[4], paddingTop: theme.spacing[6] }}>
          {/* Avatar + name skeleton */}
          <View style={{ alignItems: 'center', marginBottom: theme.spacing[8] }}>
            <Skeleton width={80} height={80} borderRadius={40} />
            <View style={{ height: 16 }} />
            <Skeleton width={140} height={20} />
            <View style={{ height: 8 }} />
            <Skeleton width={80} height={14} />
            <View style={{ height: 4 }} />
            <Skeleton width={120} height={12} />
          </View>

          {/* Stats card skeleton */}
          <View style={{ borderWidth: 1, borderColor: '#E5E5E5', borderRadius: 12, padding: 12, marginBottom: theme.spacing[6] }}>
            <Skeleton width={140} height={16} style={{ marginBottom: 16 }} />
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-around' }}>
              {[1, 2, 3, 4].map((i) => (
                <View key={i} style={{ alignItems: 'center', width: '45%', marginBottom: 16 }}>
                  <Skeleton width={28} height={22} />
                  <View style={{ height: 4 }} />
                  <Skeleton width={60} height={10} />
                </View>
              ))}
            </View>
            <View style={{ height: 1, backgroundColor: '#E5E5E5', marginBottom: 12 }} />
            <View style={{ alignItems: 'center' }}>
              <Skeleton width={80} height={10} />
              <View style={{ height: 4 }} />
              <Skeleton width={50} height={22} />
            </View>
          </View>

          {/* Recent attendance skeleton */}
          <Skeleton width={140} height={16} style={{ marginBottom: 16 }} />
          {[1, 2, 3].map((i) => (
            <View key={i} style={{ borderWidth: 1, borderColor: '#E5E5E5', borderRadius: 12, padding: 12, marginBottom: 12 }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <Skeleton width="40%" height={14} />
                <Skeleton width={56} height={22} borderRadius={12} />
              </View>
              <Skeleton width="50%" height={12} />
            </View>
          ))}
        </View>
      </ScreenLayout>
    );
  }

  // Derive display values from fetched data
  const displayName = student
    ? `${student.first_name} ${student.last_name}`
    : studentId;
  const displayFirstName = student?.first_name || '';
  const displayLastName = student?.last_name || '';
  const displayStudentId = student?.student_id || studentId;

  const overallStats = summary
    ? {
        totalClasses: summary.total,
        present: summary.present,
        late: summary.late,
        absent: summary.absent,
        attendanceRate: summary.attendance_rate,
      }
    : {
        totalClasses: 0,
        present: 0,
        late: 0,
        absent: 0,
        attendanceRate: 0,
      };

  return (
    <ScreenLayout safeArea padded={false}>
      <Header showBack title={strings.faculty.studentDetail} />

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        alwaysBounceVertical={true}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleRefresh}
            colors={[theme.colors.primary]}
            tintColor={theme.colors.primary}
          />
        }
      >
        {/* Student header */}
        <View style={styles.studentHeader}>
          <Avatar
            firstName={displayFirstName}
            lastName={displayLastName}
            size="xl"
          />
          <Text variant="h2" weight="700" align="center" style={styles.name}>
            {displayName}
          </Text>
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            {displayStudentId}
          </Text>
          {student?.email && (
            <Text
              variant="bodySmall"
              color={theme.colors.text.tertiary}
              align="center"
              style={styles.email}
            >
              {student.email}
            </Text>
          )}
        </View>

        {/* Overall stats */}
        <Card style={styles.card}>
          <Text variant="h4" weight="600" style={styles.cardTitle}>
            {strings.faculty.attendanceSummary}
          </Text>

          <View style={styles.statsGrid}>
            <StatItem
              label="Total Classes"
              value={overallStats.totalClasses.toString()}
            />
            <StatItem
              label="Present"
              value={overallStats.present.toString()}
              color={theme.colors.status.present.fg}
            />
            <StatItem
              label="Late"
              value={overallStats.late.toString()}
              color={theme.colors.status.late.fg}
            />
            <StatItem
              label="Absent"
              value={overallStats.absent.toString()}
              color={theme.colors.status.absent.fg}
            />
          </View>

          <View style={styles.attendanceRate}>
            <Text variant="bodySmall" color={theme.colors.text.tertiary}>
              Attendance Rate
            </Text>
            <Text
              variant="h3"
              weight="700"
              color={
                overallStats.attendanceRate >= 80
                  ? theme.colors.status.present.fg
                  : overallStats.attendanceRate >= 60
                  ? theme.colors.status.late.fg
                  : theme.colors.status.absent.fg
              }
            >
              {formatPercentage(overallStats.attendanceRate)}
            </Text>
          </View>
        </Card>

        {/* Recent attendance */}
        <Text variant="h4" weight="600" style={styles.sectionTitle}>
          {strings.faculty.recentAttendance}
        </Text>

        {recentRecords.length > 0 ? (
          recentRecords.map((record) => (
            <Card key={record.id} variant="outlined" style={styles.recordCard}>
              <View style={styles.recordHeader}>
                <Text variant="body" weight="500">
                  {formatDate(record.date, 'MMM d, yyyy')}
                </Text>
                <Badge status={record.status} size="sm" />
              </View>

              {record.check_in_time && (
                <Text variant="bodySmall" color={theme.colors.text.secondary}>
                  Check-in: {record.check_in_time}
                </Text>
              )}

              {record.presence_score !== undefined && (
                <Text
                  variant="bodySmall"
                  color={theme.colors.text.secondary}
                  style={styles.presenceText}
                >
                  Presence: {formatPercentage(record.presence_score)}
                </Text>
              )}
            </Card>
          ))
        ) : (
          <Card variant="outlined">
            <Text variant="bodySmall" color={theme.colors.text.secondary} align="center">
              No recent records
            </Text>
          </Card>
        )}
      </ScrollView>
    </ScreenLayout>
  );
};

const StatItem: React.FC<{ label: string; value: string; color?: string }> = ({
  label,
  value,
  color,
}) => (
  <View style={styles.statItem}>
    <Text variant="h3" weight="700" style={color ? { color } : undefined}>
      {value}
    </Text>
    <Text variant="caption" color={theme.colors.text.tertiary}>
      {label}
    </Text>
  </View>
);

const styles = StyleSheet.create({
  scrollContent: {
    padding: theme.spacing[4],
    paddingBottom: theme.spacing[8],
  },
  studentHeader: {
    alignItems: 'center',
    marginBottom: theme.spacing[8],
  },
  name: {
    marginTop: theme.spacing[4],
    marginBottom: theme.spacing[2],
  },
  email: {
    marginTop: theme.spacing[1],
  },
  card: {
    marginBottom: theme.spacing[6],
  },
  cardTitle: {
    marginBottom: theme.spacing[4],
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-around',
    marginBottom: theme.spacing[4],
  },
  statItem: {
    alignItems: 'center',
    width: '45%',
    marginBottom: theme.spacing[4],
  },
  attendanceRate: {
    alignItems: 'center',
    paddingTop: theme.spacing[4],
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
  },
  sectionTitle: {
    marginBottom: theme.spacing[4],
  },
  recordCard: {
    marginBottom: theme.spacing[3],
  },
  recordHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing[2],
  },
  presenceText: {
    marginTop: theme.spacing[1],
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
