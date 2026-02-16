/**
 * Faculty Schedule Screen
 *
 * Shows weekly teaching schedule with day selector
 * Similar to student schedule but for faculty
 */

import React, { useState, useCallback } from 'react';
import { View, StyleSheet, FlatList, ScrollView, TouchableOpacity, RefreshControl } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { useSchedule } from '../../hooks';
import { theme, strings } from '../../constants';
import { getDayName, getShortDayName } from '../../utils';
import type { FacultyStackParamList, ScheduleWithAttendance } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text } from '../../components/ui';
import { ScheduleCard } from '../../components/cards';

type FacultyScheduleNavigationProp = StackNavigationProp<FacultyStackParamList, 'FacultyTabs'>;

const DAYS = [0, 1, 2, 3, 4, 5, 6];

/**
 * Convert JS Date.getDay() (0=Sunday) to backend day_of_week (0=Monday).
 */
const jsDayToScheduleDay = (jsDay: number): number => {
  return jsDay === 0 ? 6 : jsDay - 1;
};

export const FacultyScheduleScreen: React.FC = () => {
  const navigation = useNavigation<FacultyScheduleNavigationProp>();
  const { schedules: allSchedules, isLoading, fetchMySchedules, clearError } = useSchedule();

  const [selectedDay, setSelectedDay] = useState(jsDayToScheduleDay(new Date().getDay()));
  // Filter directly using backend day format (selectedDay is 0=Monday)
  const schedules = allSchedules.filter(
    (s) => s.day_of_week === selectedDay && s.is_active
  );

  const handleCardPress = (schedule: ScheduleWithAttendance) => {
    navigation.navigate('ClassDetail', { scheduleId: schedule.id, date: new Date().toISOString() });
  };

  const handleRefresh = useCallback(() => {
    clearError();
    fetchMySchedules();
  }, [fetchMySchedules, clearError]);

  const renderDayButton = (day: number) => {
    const isSelected = day === selectedDay;
    const isToday = day === jsDayToScheduleDay(new Date().getDay());

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
          color={isSelected ? theme.colors.background : theme.colors.text.secondary}
          style={styles.dayText}
        >
          {getShortDayName(day)}
        </Text>
        {isToday && !isSelected && <View style={styles.todayIndicator} />}
      </TouchableOpacity>
    );
  };

  const renderEmpty = () => (
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

  return (
    <ScreenLayout safeArea padded={false}>
      <Header title={strings.schedule.mySchedule} />

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.daySelector}
        style={styles.daySelectorContainer}
      >
        {DAYS.map(renderDayButton)}
      </ScrollView>

      <FlatList
        data={schedules}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <ScheduleCard schedule={item} onPress={() => handleCardPress(item)} />
        )}
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
  emptyContainer: {
    paddingVertical: theme.spacing[12],
  },
  emptySubtext: {
    marginTop: theme.spacing[2],
  },
});
