/**
 * Faculty Home Screen
 *
 * Dashboard showing:
 * - Greeting
 * - Current ongoing class (if any) with session controls
 * - Session status indicator (active/inactive)
 * - Start/Stop session button
 * - Today's teaching schedule
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  RefreshControl,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { Users, Play, Square, Camera, BookOpen, CalendarOff } from 'lucide-react-native';
import { useAuth, useSchedule, useSession } from '../../hooks';
import { useToast } from '../../hooks/useToast';
import { useNotificationStore } from '../../stores/notificationStore';
import { theme, strings } from '../../constants';
import { formatDate, formatTime, getDayName } from '../../utils';
import type { FacultyStackParamList, ScheduleWithAttendance } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Button, Skeleton, ScheduleCardSkeleton } from '../../components/ui';
import { ScheduleCard } from '../../components/cards';

type FacultyHomeNavigationProp = StackNavigationProp<FacultyStackParamList, 'FacultyTabs'>;

const CurrentClassCardSkeleton: React.FC = () => (
  <View style={styles.currentClassCard}>
    <View style={styles.sessionStatusRow}>
      <Skeleton width={8} height={8} borderRadius={4} style={{ marginRight: theme.spacing[2] }} />
      <Skeleton width={110} height={12} />
    </View>
    <View style={{ height: theme.spacing[2] }} />
    <Skeleton width="65%" height={18} />
    <View style={{ height: theme.spacing[2] }} />
    <Skeleton width="50%" height={14} />
    <View style={{ height: theme.spacing[4] }} />
    <Skeleton width="100%" height={42} borderRadius={theme.borderRadius.md} />
  </View>
);

export const FacultyHomeScreen: React.FC = () => {
  const navigation = useNavigation<FacultyHomeNavigationProp>();
  const { fullName } = useAuth();
  const { todaySchedules, isLoading, fetchMySchedules, getCurrentClass, getNextDayWithClasses, totalSchedules } = useSchedule();
  const {
    isSessionActive,
    startSession,
    endSession,
    isLoading: sessionLoading,
    refreshActiveSessions,
  } = useSession();
  const { showError, showSuccess } = useToast();
  const { unreadCount, fetchUnreadCount } = useNotificationStore();

  // Track whether the initial data fetch has completed
  const [initialLoadDone, setInitialLoadDone] = useState(false);
  const wasLoading = useRef(false);

  useEffect(() => {
    if (isLoading) {
      wasLoading.current = true;
    } else if (wasLoading.current) {
      setInitialLoadDone(true);
    }
  }, [isLoading]);

  useEffect(() => {
    fetchUnreadCount();
  }, [fetchUnreadCount]);

  const currentClass = getCurrentClass();
  const sessionActive = currentClass ? isSessionActive(currentClass.id) : false;

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return strings.student.greeting.morning;
    if (hour < 18) return strings.student.greeting.afternoon;
    return strings.student.greeting.evening;
  };

  const handleNotificationPress = () => {
    navigation.navigate('Notifications');
  };

  const handleViewLiveAttendance = () => {
    if (currentClass) {
      navigation.navigate('LiveAttendance', {
        scheduleId: currentClass.id,
        subjectCode: currentClass.subject_code,
        subjectName: currentClass.subject_name,
      });
    }
  };

  const handleViewLiveFeed = () => {
    if (currentClass) {
      navigation.navigate('LiveFeed', {
        scheduleId: currentClass.id,
        roomId: currentClass.room_id || '',
        subjectName: currentClass.subject_name,
      });
    }
  };

  const handleStartSession = useCallback(async () => {
    if (!currentClass) return;
    const result = await startSession(currentClass.id);
    if (result) {
      showSuccess(`Session started with ${result.student_count} students`);
    } else {
      showError('Failed to start session');
    }
  }, [currentClass, startSession, showSuccess, showError]);

  const handleEndSession = useCallback(async () => {
    if (!currentClass) return;

    Alert.alert(
      'End Session',
      `End the session for ${currentClass.subject_name}? Final attendance scores will be calculated.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'End Session',
          style: 'destructive',
          onPress: async () => {
            const result = await endSession(currentClass.id);
            if (result) {
              showSuccess(
                `Session ended. ${result.present_count}/${result.total_students} present.`,
              );
            } else {
              showError('Failed to end session');
            }
          },
        },
      ],
    );
  }, [currentClass, endSession, showSuccess, showError]);

  const handleCardPress = (schedule: ScheduleWithAttendance) => {
    navigation.navigate('ClassDetail', { scheduleId: schedule.id, date: new Date().toISOString() });
  };

  const handleRefresh = useCallback(() => {
    fetchMySchedules();
    refreshActiveSessions();
  }, [fetchMySchedules, refreshActiveSessions]);

  const renderHeader = () => (
    <View style={styles.headerContent}>
      {/* Greeting */}
      <Text variant="h2" weight="700" style={styles.greeting}>
        {getGreeting()}, {fullName}!
      </Text>

      {/* Date */}
      <Text variant="body" color={theme.colors.text.secondary} style={styles.date}>
        {formatDate(new Date(), 'EEEE, MMMM d, yyyy')}
      </Text>

      {/* Current class card — skeleton while loading, actual card when ready */}
      {!initialLoadDone ? (
        <CurrentClassCardSkeleton />
      ) : currentClass ? (
        <View style={styles.currentClassCard}>
          <View style={styles.currentClassHeader}>
            <View style={styles.currentClassInfo}>
              {/* Session status indicator */}
              <View style={styles.sessionStatusRow}>
                <View
                  style={[
                    styles.statusDot,
                    sessionActive ? styles.statusDotActive : styles.statusDotInactive,
                  ]}
                />
                <Text
                  variant="caption"
                  color={sessionActive ? theme.colors.success : theme.colors.text.tertiary}
                  style={styles.statusText}
                >
                  {sessionActive ? 'Session Active' : 'Session Inactive'}
                </Text>
              </View>

              <Text variant="h3" weight="600" style={styles.currentClassName}>
                {currentClass.subject_name}
              </Text>
              <Text variant="bodySmall" color={theme.colors.text.secondary}>
                {currentClass.room_name} • {formatTime(currentClass.start_time)} -{' '}
                {formatTime(currentClass.end_time)}
              </Text>
            </View>

            <TouchableOpacity
              style={styles.studentsButton}
              onPress={handleViewLiveAttendance}
              disabled={!sessionActive}
            >
              <Users
                size={20}
                color={sessionActive ? theme.colors.text.secondary : theme.colors.text.tertiary}
              />
              <Text
                variant="caption"
                color={sessionActive ? theme.colors.text.secondary : theme.colors.text.tertiary}
              >
                View
              </Text>
            </TouchableOpacity>
          </View>

          {/* Session control buttons */}
          <View style={styles.buttonRow}>
            {sessionActive ? (
              <>
                <Button
                  variant="secondary"
                  size="md"
                  onPress={handleEndSession}
                  disabled={sessionLoading}
                  style={styles.sessionButton}
                >
                  {sessionLoading ? (
                    <ActivityIndicator size="small" color={theme.colors.text.primary} />
                  ) : (
                    <View style={styles.buttonContent}>
                      <Square size={16} color={theme.colors.text.primary} />
                      <Text variant="bodySmall" weight="600" style={styles.buttonLabel}>
                        End Class
                      </Text>
                    </View>
                  )}
                </Button>
                <Button
                  variant="primary"
                  size="md"
                  onPress={handleViewLiveAttendance}
                  style={styles.liveButton}
                >
                  {strings.faculty.viewLiveAttendance}
                </Button>
              </>
            ) : (
              <Button
                variant="primary"
                size="md"
                fullWidth
                onPress={handleStartSession}
                disabled={sessionLoading}
              >
                {sessionLoading ? (
                  <ActivityIndicator size="small" color={theme.colors.background} />
                ) : (
                  <View style={styles.buttonContent}>
                    <Play size={16} color={theme.colors.background} />
                    <Text
                      variant="bodySmall"
                      weight="600"
                      color={theme.colors.background}
                      style={styles.buttonLabel}
                    >
                      Start Class
                    </Text>
                  </View>
                )}
              </Button>
            )}
          </View>

          {/* Camera feed shortcut when session is active */}
          {sessionActive && (
            <TouchableOpacity style={styles.cameraLink} onPress={handleViewLiveFeed}>
              <Camera size={14} color={theme.colors.primary} />
              <Text variant="caption" color={theme.colors.primary} style={styles.cameraLinkText}>
                View Camera Feed
              </Text>
            </TouchableOpacity>
          )}
        </View>
      ) : null}

      {/* Section title */}
      {!initialLoadDone ? (
        <Skeleton width={140} height={20} style={styles.sectionTitle} />
      ) : (
        <Text variant="h3" weight="600" style={styles.sectionTitle}>
          {strings.schedule.todayClasses}
        </Text>
      )}
    </View>
  );

  const nextDay = getNextDayWithClasses();

  const renderEmpty = () => {
    // Show skeleton cards during initial load
    if (!initialLoadDone) {
      return (
        <View>
          <ScheduleCardSkeleton />
          <ScheduleCardSkeleton />
          <ScheduleCardSkeleton />
        </View>
      );
    }

    // Show empty state after data has loaded
    return (
      <View style={styles.emptyContainer}>
        <View style={styles.emptyIconContainer}>
          {totalSchedules === 0 ? (
            <BookOpen size={48} color={theme.colors.text.tertiary} strokeWidth={1.5} />
          ) : (
            <CalendarOff size={48} color={theme.colors.text.tertiary} strokeWidth={1.5} />
          )}
        </View>

        <Text variant="h3" weight="600" align="center" style={styles.emptyTitle}>
          {totalSchedules === 0 ? 'No Classes Assigned' : strings.schedule.noClassesToday}
        </Text>

        <Text
          variant="body"
          color={theme.colors.text.secondary}
          align="center"
          style={styles.emptySubtitle}
        >
          {totalSchedules === 0
            ? 'You don\'t have any classes assigned yet.\nContact your administrator to set up your schedule.'
            : 'You have no classes scheduled for today. Enjoy your free day!'}
        </Text>

        {/* Show next day with classes */}
        {nextDay && (
          <View style={styles.nextDaySection}>
            <Text
              variant="bodySmall"
              color={theme.colors.text.tertiary}
              align="center"
              style={styles.nextDayLabel}
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
                style={styles.nextDayLabel}
              >
                +{nextDay.schedules.length - 3} more
              </Text>
            )}
          </View>
        )}
      </View>
    );
  };

  return (
    <ScreenLayout safeArea safeAreaEdges={['top']} padded={false}>
      <Header
        title={strings.faculty.home}
        showNotification
        notificationCount={unreadCount}
        onNotificationPress={handleNotificationPress}
      />

      <FlatList
        data={todaySchedules}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <ScheduleCard schedule={item} onPress={() => handleCardPress(item)} />
        )}
        ListHeaderComponent={renderHeader}
        ListEmptyComponent={renderEmpty}
        contentContainerStyle={styles.listContent}
        alwaysBounceVertical={true}
        refreshControl={
          <RefreshControl
            refreshing={isLoading && initialLoadDone}
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
    backgroundColor: theme.colors.card,
    padding: theme.spacing[3],
    borderRadius: 12,
    borderWidth: 1,
    borderColor: theme.colors.border,
    marginBottom: theme.spacing[6],
  },
  currentClassHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: theme.spacing[4],
  },
  currentClassInfo: {
    flex: 1,
  },
  sessionStatusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: theme.spacing[2],
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: theme.spacing[2],
  },
  statusDotActive: {
    backgroundColor: theme.colors.success,
  },
  statusDotInactive: {
    backgroundColor: theme.colors.text.tertiary,
  },
  statusText: {
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  currentClassName: {
    marginBottom: theme.spacing[1],
  },
  studentsButton: {
    alignItems: 'center',
    paddingHorizontal: theme.spacing[3],
  },
  buttonRow: {
    flexDirection: 'row',
    gap: theme.spacing[2],
  },
  sessionButton: {
    flex: 0,
    paddingHorizontal: theme.spacing[4],
  },
  liveButton: {
    flex: 1,
  },
  buttonContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  buttonLabel: {
    marginLeft: theme.spacing[2],
  },
  cameraLink: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: theme.spacing[3],
    paddingTop: theme.spacing[3],
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
  },
  cameraLinkText: {
    marginLeft: theme.spacing[1],
  },
  sectionTitle: {
    marginBottom: theme.spacing[4],
  },
  listContent: {
    paddingHorizontal: theme.spacing[4],
    paddingBottom: theme.spacing[6],
  },
  emptyContainer: {
    paddingVertical: theme.spacing[8],
    alignItems: 'center',
  },
  emptyIconContainer: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: theme.colors.secondary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: theme.spacing[4],
  },
  emptyTitle: {
    marginBottom: theme.spacing[2],
  },
  emptySubtitle: {
    paddingHorizontal: theme.spacing[4],
  },
  nextDaySection: {
    marginTop: theme.spacing[4],
    alignItems: 'center',
    width: '100%',
  },
  nextDayLabel: {
    marginTop: theme.spacing[2],
  },
  nextDayCard: {
    backgroundColor: theme.colors.card,
    paddingVertical: theme.spacing[2],
    paddingHorizontal: theme.spacing[3],
    borderRadius: 12,
    borderWidth: 1,
    borderColor: theme.colors.border,
    marginTop: theme.spacing[2],
    width: '100%',
  },
});
