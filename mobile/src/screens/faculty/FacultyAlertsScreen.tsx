/**
 * Faculty Alerts Screen
 *
 * Shows early leave alerts with filtering
 */

import React, { useState } from 'react';
import { View, StyleSheet, FlatList, ScrollView, TouchableOpacity } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { theme, strings } from '../../constants';
import type { FacultyStackParamList, EarlyLeaveEvent } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text } from '../../components/ui';
import { AlertCard } from '../../components/cards';

type FacultyAlertsNavigationProp = StackNavigationProp<FacultyStackParamList, 'FacultyTabs'>;

const FILTERS = [
  { label: 'Today', value: 'today' },
  { label: 'This Week', value: 'week' },
  { label: 'All', value: 'all' },
];

// Mock data
const MOCK_ALERTS: EarlyLeaveEvent[] = [
  {
    id: '1',
    attendanceId: 'att1',
    studentName: 'John Doe',
    detectedAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    consecutiveMisses: 3,
    notified: true,
  },
  {
    id: '2',
    attendanceId: 'att2',
    studentName: 'Jane Smith',
    detectedAt: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
    consecutiveMisses: 3,
    notified: true,
  },
];

export const FacultyAlertsScreen: React.FC = () => {
  const navigation = useNavigation<FacultyAlertsNavigationProp>();

  const [selectedFilter, setSelectedFilter] = useState('today');
  const alerts = MOCK_ALERTS; // Replace with real data

  const handleAlertPress = (event: EarlyLeaveEvent) => {
    navigation.navigate('StudentDetail', {
      studentId: event.id,
      scheduleId: event.attendanceId,
    });
  };

  const renderFilterButton = (filter: typeof FILTERS[0]) => {
    const isSelected = filter.value === selectedFilter;

    return (
      <TouchableOpacity
        key={filter.value}
        style={[styles.filterButton, isSelected && styles.filterButtonSelected]}
        onPress={() => setSelectedFilter(filter.value)}
        activeOpacity={theme.interaction.activeOpacity}
      >
        <Text
          variant="bodySmall"
          weight={isSelected ? 'semibold' : 'regular'}
          color={isSelected ? theme.colors.background : theme.colors.text.secondary}
        >
          {filter.label}
        </Text>
      </TouchableOpacity>
    );
  };

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Text variant="body" color={theme.colors.text.secondary} align="center">
        {strings.faculty.noAlertsToday}
      </Text>
    </View>
  );

  return (
    <ScreenLayout safeArea padded={false}>
      <Header title={strings.faculty.alerts} />

      {/* Filters */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.filterList}
        style={styles.filterContainer}
      >
        {FILTERS.map(renderFilterButton)}
      </ScrollView>

      {/* Alerts list */}
      <FlatList
        data={alerts}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <AlertCard event={item} onPress={() => handleAlertPress(item)} />
        )}
        ListEmptyComponent={renderEmpty}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
      />
    </ScreenLayout>
  );
};

const styles = StyleSheet.create({
  filterContainer: {
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  filterList: {
    paddingHorizontal: theme.spacing[4],
    paddingVertical: theme.spacing[4],
  },
  filterButton: {
    paddingHorizontal: theme.spacing[4],
    paddingVertical: theme.spacing[2],
    marginRight: theme.spacing[2],
    borderRadius: theme.borderRadius.full,
    backgroundColor: theme.colors.backgroundSecondary,
  },
  filterButtonSelected: {
    backgroundColor: theme.colors.primary,
  },
  listContent: {
    padding: theme.spacing[4],
  },
  emptyContainer: {
    paddingVertical: theme.spacing[12],
  },
});
