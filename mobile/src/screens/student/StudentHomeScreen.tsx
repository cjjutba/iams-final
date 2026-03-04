/**
 * Student Home Screen
 *
 * Dashboard showing:
 * - Greeting with student's name
 * - Today's date
 * - Face registration status card
 * - Attendance overview (segmented bar + stats)
 * - Current class highlight (if ongoing)
 * - Upcoming class (if no current class but classes remain today)
 * - Today's classes with attendance status
 * - Recent activity feed (last 5 attendance records)
 * - Loading, error, and empty states
 */

import React, { useCallback, useEffect, useState } from 'react';
import { View, StyleSheet, FlatList, RefreshControl } from 'react-native';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { RefreshCw } from 'lucide-react-native';
import { useAuth, useSchedule } from '../../hooks';
import { useToast } from '../../hooks/useToast';
import { faceService, attendanceService } from '../../services';
import { theme, strings } from '../../constants';
import { formatDate, formatTime, getDayName } from '../../utils';
import type {
  StudentStackParamList,
  ScheduleWithAttendance,
  AttendanceSummary,
  AttendanceRecord,
} from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Badge, Button } from '../../components/ui';
import { FaceStatusCard } from '../../components/cards/FaceStatusCard';
import { AttendanceOverviewCard } from '../../components/cards/AttendanceOverviewCard';
import { ActivityFeedItem } from '../../components/cards/ActivityFeedItem';

type StudentHomeNavigationProp = StackNavigationProp<StudentStackParamList, 'StudentTabs'>;

export const StudentHomeScreen: React.FC = () => {
  const navigation = useNavigation<StudentHomeNavigationProp>();
  const { fullName } = useAuth();
  const {
    schedules,
    todaySchedules,
    isLoading,
    error,
    fetchMySchedules,
    getCurrentClass,
    getNextClass,
    getNextDayWithClasses,
    totalSchedules,
    clearError,
  } = useSchedule();

  const { showError } = useToast();

  const currentClass = getCurrentClass();
  const nextClass = getNextClass();

  // ---------- face registration status ----------

  const [faceStatus, setFaceStatus] = useState<'not_registered' | 'registered' | 'loading'>('loading');
  const [faceRegisteredAt, setFaceRegisteredAt] = useState<string | undefined>(undefined);

  useFocusEffect(
    useCallback(() => {
      setFaceStatus('loading');
      faceService.getFaceStatus()
        .then((status) => {
          setFaceStatus(status.registered ? 'registered' : 'not_registered');
          setFaceRegisteredAt(status.registered_at);
        })
        .catch(() => {
          // On error, hide the card rather than showing a broken state
          setFaceStatus('registered');
        });
    }, []),
  );

  // ---------- attendance summary ----------

  const [summary, setSummary] = useState<AttendanceSummary | null>(null);

  const fetchSummary = useCallback(() => {
    // Fetch summary for the current semester (approximate: last 6 months)
    const endDate = new Date().toISOString().split('T')[0];
    const startDate = new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

    attendanceService.getAttendanceSummary(startDate, endDate)
      .then(setSummary)
      .catch(() => setSummary(null));
  }, []);

  // ---------- recent activity ----------

  const [recentActivity, setRecentActivity] = useState<AttendanceRecord[]>([]);

  const fetchRecentActivity = useCallback(() => {
    attendanceService.getMyAttendance()
      .then((records) => setRecentActivity(records.slice(0, 5)))
      .catch(() => setRecentActivity([]));
  }, []);

  // Fetch summary + activity on focus
  useFocusEffect(
    useCallback(() => {
      fetchSummary();
      fetchRecentActivity();
    }, [fetchSummary, fetchRecentActivity]),
  );

  useEffect(() => {
    if (error) showError(error, 'Load Failed');
  }, [error]);

  // Get greeting based on time of day
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return strings.student.greeting.morning;
    if (hour < 18) return strings.student.greeting.afternoon;
    return strings.student.greeting.evening;
  };

  const handleNotificationPress = () => {
    navigation.navigate('Notifications');
  };

  const handleCardPress = (schedule: ScheduleWithAttendance) => {
    if (schedule.today_attendance?.id) {
      navigation.navigate('AttendanceDetail', {
        attendanceId: schedule.today_attendance.id,
        scheduleId: schedule.id,
        date: new Date().toISOString().split('T')[0],
      });
    } else {
      navigation.navigate('AttendanceDetail', {
        attendanceId: '',
        scheduleId: schedule.id,
        date: new Date().toISOString().split('T')[0],
      });
    }
  };

  const handleRefresh = useCallback(() => {
    clearError();
    fetchMySchedules();
    fetchSummary();
    fetchRecentActivity();
  }, [fetchMySchedules, clearError, fetchSummary, fetchRecentActivity]);

  const handleFaceRegisterPress = useCallback(() => {
    navigation.navigate('FaceRegister', { mode: 'register' });
  }, [navigation]);

  const handleFaceReregisterPress = useCallback(() => {
    navigation.navigate('FaceRegister', { mode: 'reregister' });
  }, [navigation]);

  // ---------- schedule card ----------

  const renderScheduleItem = ({ item }: { item: ScheduleWithAttendance }) => {
    const attendance = item.today_attendance;
    const statusValue = attendance?.status;

    return (
      <Card onPress={() => handleCardPress(item)} style={styles.scheduleCard}>
        <View style={styles.cardContent}>
          <View style={styles.cardMainInfo}>
            {/* Subject code */}
            <Text variant="caption" color={theme.colors.text.tertiary} style={styles.subjectCode}>
              {item.subject_code}
            </Text>

            {/* Subject name */}
            <Text variant="body" weight="600" numberOfLines={1} style={styles.subjectName}>
              {item.subject_name}
            </Text>

            {/* Time and room */}
            <Text variant="bodySmall" color={theme.colors.text.secondary} style={styles.meta}>
              {formatTime(item.start_time)} - {formatTime(item.end_time)}
              {item.room_name ? ` \u2022 ${item.room_name}` : ''}
            </Text>

            {/* Status badge */}
            {statusValue && (
              <View style={styles.statusRow}>
                <Badge status={statusValue as any} size="sm" />
                {attendance?.presence_score !== undefined && attendance.presence_score !== null && (
                  <Text
                    variant="bodySmall"
                    color={theme.colors.text.secondary}
                    style={styles.score}
                  >
                    {attendance.presence_score.toFixed(1)}% present
                  </Text>
                )}
              </View>
            )}
          </View>
        </View>
      </Card>
    );
  };

  // ---------- header content ----------

  const renderHeader = () => (
    <View style={styles.headerContent}>
      {/* Greeting */}
      <Text variant="h2" weight="700" style={styles.greeting}>
        {getGreeting()}, {fullName || 'Student'}!
      </Text>

      {/* Date */}
      <Text variant="body" color={theme.colors.text.secondary} style={styles.date}>
        {formatDate(new Date(), 'EEEE, MMMM d, yyyy')}
      </Text>

      {/* Face status card (replaces old banner) */}
      <FaceStatusCard
        status={faceStatus}
        registeredAt={faceRegisteredAt}
        onRegister={handleFaceRegisterPress}
        onReregister={handleFaceReregisterPress}
      />

      {/* Attendance overview card */}
      {summary && (
        <AttendanceOverviewCard
          present={summary.present}
          late={summary.late}
          absent={summary.absent}
          earlyLeave={summary.early_leave}
          attendanceRate={summary.attendance_rate}
        />
      )}

      {/* Current class highlight */}
      {currentClass && (
        <View style={styles.currentClassCard}>
          <Text variant="caption" color={theme.colors.primary} style={styles.currentClassLabel}>
            {strings.schedule.currentClass}
          </Text>
          <Text variant="h3" weight="600" style={styles.currentClassName}>
            {currentClass.subject_name}
          </Text>
          <Text variant="bodySmall" color={theme.colors.text.secondary}>
            {currentClass.room_name ? `${currentClass.room_name} \u2022 ` : ''}Ongoing
          </Text>
        </View>
      )}

      {/* Upcoming class (shown only when no current class and there is a next class today) */}
      {!currentClass && nextClass && (
        <View style={styles.upcomingClassCard}>
          <Text variant="caption" color={theme.colors.text.secondary} style={styles.upcomingClassLabel}>
            {strings.schedule.upcomingClass}
          </Text>
          <Text variant="h3" weight="600" style={styles.upcomingClassName}>
            {nextClass.subject_name}
          </Text>
          <Text variant="bodySmall" color={theme.colors.text.secondary}>
            {formatTime(nextClass.start_time)} - {formatTime(nextClass.end_time)}
            {nextClass.room_name ? ` \u2022 ${nextClass.room_name}` : ''}
          </Text>
        </View>
      )}

      {/* Section title */}
      <Text variant="h3" weight="600" style={styles.sectionTitle}>
        {strings.schedule.todayClasses}
      </Text>
    </View>
  );

  // ---------- footer content (recent activity) ----------

  const renderFooter = () => {
    if (recentActivity.length === 0) return null;

    return (
      <View style={styles.footerContent}>
        <Text variant="h3" weight="600" style={styles.sectionTitle}>
          Recent Activity
        </Text>
        {recentActivity.map((record) => {
          const info = getScheduleInfoForRecord(record);
          return (
            <ActivityFeedItem
              key={record.id}
              subjectCode={info.subjectCode}
              subjectName={info.subjectName}
              date={formatDate(record.date, 'MMM dd, yyyy')}
              status={record.status}
            />
          );
        })}
      </View>
    );
  };

  /**
   * Resolve schedule info for an attendance record.
   * Matches against the already-loaded schedules from the useSchedule hook;
   * falls back to truncated identifiers if no match is found.
   */
  const getScheduleInfoForRecord = useCallback(
    (record: AttendanceRecord): { subjectName: string; subjectCode: string } => {
      const matched = schedules.find((s) => s.id === record.schedule_id);
      return {
        subjectName: matched?.subject_name ?? `Class ${record.schedule_id.slice(0, 8)}`,
        subjectCode: matched?.subject_code ?? record.schedule_id.slice(0, 8),
      };
    },
    [schedules],
  );

  // ---------- empty state ----------

  const nextDay = getNextDayWithClasses();

  const renderEmpty = () => {
    if (isLoading) return null;

    return (
      <View style={styles.emptyContainer}>
        <Text variant="body" color={theme.colors.text.secondary} align="center">
          {strings.schedule.noClassesToday}
        </Text>

        {/* Show next day with classes */}
        {nextDay && (
          <View style={styles.nextDaySection}>
            <Text
              variant="bodySmall"
              color={theme.colors.text.tertiary}
              align="center"
              style={styles.emptySubtext}
            >
              Next classes on {getDayName(nextDay.backendDay)}
            </Text>

            {nextDay.schedules
              .sort((a, b) => a.start_time.localeCompare(b.start_time))
              .slice(0, 3)
              .map((s) => (
                <View key={s.id} style={styles.nextDayCard}>
                  <Text variant="bodySmall" weight="600" numberOfLines={1}>
                    {s.subject_name}
                  </Text>
                  <Text variant="caption" color={theme.colors.text.secondary}>
                    {formatTime(s.start_time)} - {formatTime(s.end_time)}
                    {s.room_name ? ` \u2022 ${s.room_name}` : ''}
                  </Text>
                </View>
              ))}

            {nextDay.schedules.length > 3 && (
              <Text
                variant="caption"
                color={theme.colors.text.tertiary}
                align="center"
                style={styles.emptySubtext}
              >
                +{nextDay.schedules.length - 3} more
              </Text>
            )}
          </View>
        )}

        {/* No schedules at all */}
        {!nextDay && totalSchedules === 0 && (
          <Text
            variant="bodySmall"
            color={theme.colors.text.tertiary}
            align="center"
            style={styles.emptySubtext}
          >
            {strings.empty.noClasses}
          </Text>
        )}
      </View>
    );
  };

  // ---------- error state (full screen, only when no cached data) ----------

  if (error && todaySchedules.length === 0 && !isLoading) {
    return (
      <ScreenLayout safeArea padded={false}>
        <Header
          title={strings.student.home}
          showNotification
          onNotificationPress={handleNotificationPress}
        />
        <View style={styles.errorContainer}>
          <RefreshCw size={40} color={theme.colors.text.tertiary} style={styles.errorIcon} />
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            Unable to load your schedule. Please try again.
          </Text>
          <Button variant="secondary" size="md" onPress={handleRefresh} style={styles.retryButton}>
            {strings.common.retry}
          </Button>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- main render ----------

  return (
    <ScreenLayout safeArea padded={false}>
      <Header
        title={strings.student.home}
        showNotification
        onNotificationPress={handleNotificationPress}
      />

      <FlatList
        data={todaySchedules}
        keyExtractor={(item) => item.id}
        renderItem={renderScheduleItem}
        ListHeaderComponent={renderHeader}
        ListFooterComponent={renderFooter}
        ListEmptyComponent={renderEmpty}
        contentContainerStyle={styles.listContent}
        alwaysBounceVertical={true}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={handleRefresh}
            colors={[theme.colors.primary]}
            tintColor={theme.colors.primary}
          />
        }
        showsVerticalScrollIndicator={false}
      />
    </ScreenLayout>
  );
};

const styles = StyleSheet.create({
  headerContent: {
    paddingHorizontal: theme.spacing[4],
    paddingTop: theme.spacing[6],
  },
  greeting: {
    marginBottom: theme.spacing[2],
  },
  date: {
    marginBottom: theme.spacing[6],
  },
  currentClassCard: {
    backgroundColor: theme.colors.secondary,
    padding: theme.spacing[4],
    borderRadius: theme.borderRadius.lg,
    borderLeftWidth: 4,
    borderLeftColor: theme.colors.primary,
    marginBottom: theme.spacing[6],
  },
  currentClassLabel: {
    marginBottom: theme.spacing[1],
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  currentClassName: {
    marginBottom: theme.spacing[1],
  },
  upcomingClassCard: {
    backgroundColor: theme.colors.secondary,
    padding: theme.spacing[4],
    borderRadius: theme.borderRadius.lg,
    borderLeftWidth: 4,
    borderLeftColor: theme.colors.border,
    marginBottom: theme.spacing[6],
  },
  upcomingClassLabel: {
    marginBottom: theme.spacing[1],
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  upcomingClassName: {
    marginBottom: theme.spacing[1],
  },
  sectionTitle: {
    marginBottom: theme.spacing[4],
  },
  listContent: {
    paddingHorizontal: theme.spacing[4],
    paddingBottom: theme.spacing[6],
  },
  scheduleCard: {
    marginBottom: theme.spacing[3],
  },
  cardContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  cardMainInfo: {
    flex: 1,
  },
  subjectCode: {
    marginBottom: theme.spacing[1],
  },
  subjectName: {
    marginBottom: theme.spacing[2],
  },
  meta: {
    marginBottom: theme.spacing[2],
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  score: {
    marginLeft: theme.spacing[2],
  },
  footerContent: {
    paddingTop: theme.spacing[6],
  },
  emptyContainer: {
    paddingVertical: theme.spacing[8],
  },
  emptySubtext: {
    marginTop: theme.spacing[2],
  },
  nextDaySection: {
    marginTop: theme.spacing[4],
    alignItems: 'center',
  },
  nextDayCard: {
    backgroundColor: theme.colors.secondary,
    paddingVertical: theme.spacing[3],
    paddingHorizontal: theme.spacing[4],
    borderRadius: theme.borderRadius.md,
    marginTop: theme.spacing[2],
    width: '100%',
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
