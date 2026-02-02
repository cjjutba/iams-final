/**
 * Student Home Screen
 *
 * Dashboard showing:
 * - Greeting
 * - Today's date
 * - Today's classes with attendance status
 * - Current class highlight (if ongoing)
 */

import React, { useEffect } from 'react';
import { View, StyleSheet, FlatList, RefreshControl } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { Bell } from 'lucide-react-native';
import { useAuth, useSchedule } from '../../hooks';
import { theme, strings } from '../../constants';
import { formatDate } from '../../utils';
import type { StudentStackParamList, ScheduleWithAttendance } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text } from '../../components/ui';
import { AttendanceCard } from '../../components/cards';

type StudentHomeNavigationProp = StackNavigationProp<StudentStackParamList, 'StudentTabs'>;

export const StudentHomeScreen: React.FC = () => {
  const navigation = useNavigation<StudentHomeNavigationProp>();
  const { fullName } = useAuth();
  const { todaySchedules, isLoading, fetchMySchedules, getCurrentClass } = useSchedule();

  const currentClass = getCurrentClass();

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
    navigation.navigate('AttendanceDetail', { scheduleId: schedule.id });
  };

  const renderHeader = () => (
    <View style={styles.headerContent}>
      {/* Greeting */}
      <Text variant="h2" weight="bold" style={styles.greeting}>
        {getGreeting()}, {fullName}!
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
          <Text variant="h3" weight="semibold" style={styles.currentClassName}>
            {currentClass.subjectName}
          </Text>
          <Text variant="bodySmall" color={theme.colors.text.secondary}>
            {currentClass.roomName} • Ongoing
          </Text>
        </View>
      )}

      {/* Section title */}
      <Text variant="h3" weight="semibold" style={styles.sectionTitle}>
        {strings.schedule.todayClasses}
      </Text>
    </View>
  );

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Text variant="body" color={theme.colors.text.secondary} align="center">
        {strings.empty.noClasses}
      </Text>
    </View>
  );

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
        renderItem={({ item }) => (
          <AttendanceCard
            schedule={item}
            status={item.todayStatus}
            presenceScore={item.presenceScore}
            onPress={() => handleCardPress(item)}
          />
        )}
        ListHeaderComponent={renderHeader}
        ListEmptyComponent={renderEmpty}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={fetchMySchedules}
            colors={[theme.colors.primary]}
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
    backgroundColor: theme.colors.backgroundSecondary,
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
  emptyContainer: {
    paddingVertical: theme.spacing[12],
  },
});
