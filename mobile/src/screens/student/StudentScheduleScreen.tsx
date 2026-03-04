/**
 * Student Schedule Screen
 *
 * Shows weekly schedule with day selector.
 * Displays all classes for the selected day.
 * Includes loading, error, empty states and pull-to-refresh.
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { RefreshCw } from 'lucide-react-native';
import { useSchedule } from '../../hooks';
import { useToast } from '../../hooks/useToast';
import { theme, strings } from '../../constants';
import { getDayName, getShortDayName, formatTime } from '../../utils';
import type { StudentStackParamList, Schedule } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Button, Loader } from '../../components/ui';

type StudentScheduleNavigationProp = StackNavigationProp<StudentStackParamList, 'StudentTabs'>;

/**
 * Day indices aligned with the Schedule type (0=Monday .. 6=Sunday).
 * The getDayName/getShortDayName utilities also use this convention.
 */
const DAYS = [0, 1, 2, 3, 4, 5, 6];

/**
 * Convert JS Date.getDay() (0=Sunday) to our convention (0=Monday).
 */
const jsDayToScheduleDay = (jsDay: number): number => {
  return jsDay === 0 ? 6 : jsDay - 1;
};

export const StudentScheduleScreen: React.FC = () => {
  const navigation = useNavigation<StudentScheduleNavigationProp>();
  const { schedules, isLoading, error, fetchMySchedules, clearError, getSchedulesByDay } =
    useSchedule();

  const { showError } = useToast();

  const [selectedDay, setSelectedDay] = useState(jsDayToScheduleDay(new Date().getDay()));

  useEffect(() => {
    if (error) showError(error, 'Load Failed');
  }, [error]);

  // Filter directly using backend day format (selectedDay is already 0=Monday)
  const daySchedules = schedules.filter(
    (s) => s.day_of_week === selectedDay && s.is_active
  );

  const handleCardPress = (schedule: Schedule) => {
    navigation.navigate('AttendanceDetail', {
      attendanceId: '',
      scheduleId: schedule.id,
      date: new Date().toISOString().split('T')[0],
    });
  };

  const handleRefresh = useCallback(() => {
    clearError();
    fetchMySchedules();
  }, [fetchMySchedules, clearError]);

  // ---------- day selector button ----------

  const renderDayButton = (day: number) => {
    const isSelected = day === selectedDay;
    const todayDay = jsDayToScheduleDay(new Date().getDay());
    const isToday = day === todayDay;

    return (
      <TouchableOpacity
        key={day}
        style={[styles.dayButton, isSelected && styles.dayButtonSelected]}
        onPress={() => setSelectedDay(day)}
        activeOpacity={theme.interaction.activeOpacity}
      >
        <Text
          variant="caption"
          weight={isSelected ? '600' : '400'}
          color={isSelected ? theme.colors.primaryForeground : theme.colors.text.secondary}
          style={styles.dayText}
        >
          {getShortDayName(day)}
        </Text>
        {isToday && !isSelected && <View style={styles.todayIndicator} />}
      </TouchableOpacity>
    );
  };

  // ---------- schedule card ----------

  const renderScheduleCard = ({ item }: { item: Schedule }) => (
    <Card onPress={() => handleCardPress(item)} style={styles.scheduleCard}>
      <View style={styles.cardRow}>
        {/* Accent bar */}
        <View style={styles.accentBar} />

        {/* Content */}
        <View style={styles.cardContent}>
          <Text variant="h3" weight="700" style={styles.cardTime}>
            {formatTime(item.start_time)}
          </Text>

          <Text variant="body" weight="600" numberOfLines={1} style={styles.cardSubject}>
            {item.subject_name}
          </Text>
          <Text variant="caption" color={theme.colors.text.tertiary} style={styles.cardCode}>
            {item.subject_code}
          </Text>

          <View style={styles.cardMeta}>
            <Text variant="bodySmall" color={theme.colors.text.secondary}>
              {formatTime(item.start_time)} - {formatTime(item.end_time)}
            </Text>
            {item.room_name && (
              <>
                <Text variant="bodySmall" color={theme.colors.text.tertiary}>
                  {' \u2022 '}
                </Text>
                <Text variant="bodySmall" color={theme.colors.text.secondary}>
                  {item.room_name}
                </Text>
              </>
            )}
          </View>

          {item.faculty_name && (
            <Text variant="bodySmall" color={theme.colors.text.tertiary} style={styles.cardFaculty}>
              {item.faculty_name}
            </Text>
          )}
        </View>
      </View>
    </Card>
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
          No classes scheduled for {getDayName(selectedDay)}
        </Text>
      </View>
    );
  };

  // ---------- error state (only when no cached schedules) ----------

  if (error && schedules.length === 0 && !isLoading) {
    return (
      <ScreenLayout safeArea safeAreaEdges={['top']} padded={false}>
        <Header title={strings.schedule.mySchedule} />
        <View style={styles.errorContainer}>
          <RefreshCw size={40} color={theme.colors.text.tertiary} style={styles.errorIcon} />
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            Unable to load schedule. Please try again.
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
    <ScreenLayout safeArea safeAreaEdges={['top']} padded={false}>
      <Header title={strings.schedule.mySchedule} />

      {/* Day selector */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.daySelector}
        style={styles.daySelectorContainer}
      >
        {DAYS.map(renderDayButton)}
      </ScrollView>

      {/* Schedule list */}
      <FlatList
        data={daySchedules}
        keyExtractor={(item) => item.id}
        renderItem={renderScheduleCard}
        ListEmptyComponent={renderEmpty}
        style={styles.list}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        alwaysBounceVertical={true}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={handleRefresh}
            colors={[theme.colors.primary]}
            tintColor={theme.colors.primary}
          />
        }
      />
    </ScreenLayout>
  );
};

const styles = StyleSheet.create({
  daySelectorContainer: {
    flexGrow: 0,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  daySelector: {
    paddingHorizontal: theme.spacing[4],
    paddingVertical: theme.spacing[4],
  },
  dayButton: {
    paddingHorizontal: theme.spacing[4],
    paddingVertical: theme.spacing[2],
    marginRight: theme.spacing[2],
    borderRadius: theme.borderRadius.full,
    backgroundColor: theme.colors.secondary,
    minWidth: 48,
    alignItems: 'center',
    position: 'relative',
  },
  dayButtonSelected: {
    backgroundColor: theme.colors.primary,
  },
  dayText: {
    textTransform: 'uppercase',
  },
  todayIndicator: {
    position: 'absolute',
    bottom: 4,
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: theme.colors.primary,
  },
  list: {
    flex: 1,
  },
  listContent: {
    padding: theme.spacing[4],
  },
  scheduleCard: {
    marginBottom: theme.spacing[3],
    paddingLeft: 0,
  },
  cardRow: {
    flexDirection: 'row',
  },
  accentBar: {
    width: 4,
    backgroundColor: theme.colors.primary,
    borderTopLeftRadius: theme.borderRadius.md,
    borderBottomLeftRadius: theme.borderRadius.md,
    marginRight: theme.spacing[4],
  },
  cardContent: {
    flex: 1,
    paddingVertical: theme.spacing[2],
    paddingRight: theme.spacing[4],
  },
  cardTime: {
    marginBottom: theme.spacing[2],
  },
  cardSubject: {
    marginBottom: theme.spacing[1],
  },
  cardCode: {
    marginBottom: theme.spacing[2],
  },
  cardMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  cardFaculty: {
    marginTop: theme.spacing[1],
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
