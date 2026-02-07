/**
 * Faculty Home Screen
 *
 * Dashboard showing:
 * - Greeting
 * - Current ongoing class (if any) with quick stats
 * - Today's teaching schedule
 */

import React from 'react';
import { View, StyleSheet, FlatList, RefreshControl, TouchableOpacity } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { Bell, Users } from 'lucide-react-native';
import { useAuth, useSchedule } from '../../hooks';
import { theme, strings } from '../../constants';
import { formatDate, formatTime } from '../../utils';
import type { FacultyStackParamList, ScheduleWithAttendance } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Button } from '../../components/ui';
import { ScheduleCard } from '../../components/cards';

type FacultyHomeNavigationProp = StackNavigationProp<FacultyStackParamList, 'FacultyTabs'>;

export const FacultyHomeScreen: React.FC = () => {
  const navigation = useNavigation<FacultyHomeNavigationProp>();
  const { fullName } = useAuth();
  const { todaySchedules, isLoading, fetchMySchedules, getCurrentClass } = useSchedule();

  const currentClass = getCurrentClass();

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

  const handleCardPress = (schedule: ScheduleWithAttendance) => {
    navigation.navigate('ClassDetail', { scheduleId: schedule.id, date: new Date().toISOString() });
  };

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

      {/* Current class card */}
      {currentClass && (
        <View style={styles.currentClassCard}>
          <View style={styles.currentClassHeader}>
            <View style={styles.currentClassInfo}>
              <Text variant="caption" color={theme.colors.primary} style={styles.currentClassLabel}>
                {strings.schedule.currentClass}
              </Text>
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
            >
              <Users size={20} color={theme.colors.text.secondary} />
              <Text variant="caption" color={theme.colors.text.secondary}>
                View
              </Text>
            </TouchableOpacity>
          </View>

          <Button
            variant="primary"
            size="md"
            fullWidth
            onPress={handleViewLiveAttendance}
            style={styles.liveButton}
          >
            {strings.faculty.viewLiveAttendance}
          </Button>
        </View>
      )}

      {/* Section title */}
      <Text variant="h3" weight="600" style={styles.sectionTitle}>
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
        title={strings.faculty.home}
        showNotification
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
    backgroundColor: theme.colors.secondary,
    padding: theme.spacing[4],
    borderRadius: theme.borderRadius.lg,
    borderLeftWidth: 4,
    borderLeftColor: theme.colors.primary,
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
  currentClassLabel: {
    marginBottom: theme.spacing[1],
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
  liveButton: {
    // No additional styles
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
