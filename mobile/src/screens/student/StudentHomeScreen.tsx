/**
 * Student Home Screen
 *
 * Dashboard showing:
 * - Greeting with student's name
 * - Today's date
 * - Current class highlight (if ongoing)
 * - Today's classes with attendance status
 * - Loading, error, and empty states
 */

import React, { useCallback, useEffect } from 'react';
import { View, StyleSheet, FlatList, RefreshControl, ActivityIndicator } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { RefreshCw } from 'lucide-react-native';
import { useAuth, useSchedule } from '../../hooks';
import { useToast } from '../../hooks/useToast';
import { theme, strings } from '../../constants';
import { formatDate, formatTime, formatTimeRange } from '../../utils';
import type { StudentStackParamList, ScheduleWithAttendance } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Badge, Button } from '../../components/ui';

type StudentHomeNavigationProp = StackNavigationProp<StudentStackParamList, 'StudentTabs'>;

export const StudentHomeScreen: React.FC = () => {
  const navigation = useNavigation<StudentHomeNavigationProp>();
  const { fullName } = useAuth();
  const {
    todaySchedules,
    isLoading,
    error,
    fetchMySchedules,
    getCurrentClass,
    clearError,
  } = useSchedule();

  const { showError } = useToast();

  const currentClass = getCurrentClass();

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
    // Navigate to attendance detail if there is a today_attendance record,
    // otherwise pass schedule info so the detail screen can look up by scheduleId
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
  }, [fetchMySchedules, clearError]);

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

      {/* Section title */}
      <Text variant="h3" weight="600" style={styles.sectionTitle}>
        {strings.schedule.todayClasses}
      </Text>
    </View>
  );

  // ---------- empty state ----------

  const renderEmpty = () => {
    if (isLoading) return null;

    return (
      <View style={styles.emptyContainer}>
        <Text variant="body" color={theme.colors.text.secondary} align="center">
          {strings.empty.noClasses}
        </Text>
        <Text
          variant="bodySmall"
          color={theme.colors.text.tertiary}
          align="center"
          style={styles.emptySubtext}
        >
          {strings.schedule.noClassesToday}
        </Text>
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
  emptyContainer: {
    paddingVertical: theme.spacing[12],
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
