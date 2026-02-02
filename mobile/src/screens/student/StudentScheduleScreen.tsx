/**
 * Student Schedule Screen
 *
 * Shows weekly schedule with day selector
 * Displays all classes for selected day
 */

import React, { useState } from 'react';
import { View, StyleSheet, FlatList, ScrollView, TouchableOpacity } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { useSchedule } from '../../hooks';
import { theme, strings } from '../../constants';
import { getDayName, getShortDayName } from '../../utils';
import type { StudentStackParamList, ScheduleWithAttendance } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text } from '../../components/ui';
import { ScheduleCard } from '../../components/cards';

type StudentScheduleNavigationProp = StackNavigationProp<StudentStackParamList, 'StudentTabs'>;

const DAYS = [0, 1, 2, 3, 4, 5, 6]; // Sunday to Saturday

export const StudentScheduleScreen: React.FC = () => {
  const navigation = useNavigation<StudentScheduleNavigationProp>();
  const { getSchedulesByDay } = useSchedule();

  const [selectedDay, setSelectedDay] = useState(new Date().getDay());
  const schedules = getSchedulesByDay(selectedDay);

  const handleCardPress = (schedule: ScheduleWithAttendance) => {
    navigation.navigate('AttendanceDetail', { scheduleId: schedule.id });
  };

  const renderDayButton = (day: number) => {
    const isSelected = day === selectedDay;
    const isToday = day === new Date().getDay();

    return (
      <TouchableOpacity
        key={day}
        style={[
          styles.dayButton,
          isSelected && styles.dayButtonSelected,
        ]}
        onPress={() => setSelectedDay(day)}
        activeOpacity={theme.interaction.activeOpacity}
      >
        <Text
          variant="caption"
          weight={isSelected ? 'semibold' : 'regular'}
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
      <Text variant="bodySmall" color={theme.colors.text.tertiary} align="center" style={styles.emptySubtext}>
        No classes scheduled for {getDayName(selectedDay)}
      </Text>
    </View>
  );

  return (
    <ScreenLayout safeArea padded={false}>
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
        data={schedules}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <ScheduleCard schedule={item} onPress={() => handleCardPress(item)} />
        )}
        ListEmptyComponent={renderEmpty}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
      />
    </ScreenLayout>
  );
};

const styles = StyleSheet.create({
  daySelectorContainer: {
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
    backgroundColor: theme.colors.backgroundSecondary,
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
