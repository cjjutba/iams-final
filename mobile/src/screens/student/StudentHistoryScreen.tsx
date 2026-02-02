/**
 * Student History Screen
 *
 * Shows attendance history with filters
 * Month selector and status filters
 */

import React, { useState, useEffect } from 'react';
import { View, StyleSheet, FlatList, ScrollView, TouchableOpacity } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { ChevronLeft, ChevronRight } from 'lucide-react-native';
import { useAttendance } from '../../hooks';
import { theme, strings } from '../../constants';
import { formatDate } from '../../utils';
import type { StudentStackParamList, AttendanceStatus } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text } from '../../components/ui';
import { AttendanceCard } from '../../components/cards';

type StudentHistoryNavigationProp = StackNavigationProp<StudentStackParamList, 'StudentTabs'>;

const FILTERS: Array<{ label: string; value: AttendanceStatus | 'all' }> = [
  { label: 'All', value: 'all' },
  { label: 'Present', value: 'present' },
  { label: 'Late', value: 'late' },
  { label: 'Absent', value: 'absent' },
];

export const StudentHistoryScreen: React.FC = () => {
  const navigation = useNavigation<StudentHistoryNavigationProp>();
  const { history, fetchMyAttendance } = useAttendance();

  const [selectedMonth, setSelectedMonth] = useState(new Date());
  const [selectedFilter, setSelectedFilter] = useState<AttendanceStatus | 'all'>('all');

  useEffect(() => {
    loadHistory();
  }, [selectedMonth]);

  const loadHistory = () => {
    const startDate = new Date(selectedMonth.getFullYear(), selectedMonth.getMonth(), 1);
    const endDate = new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() + 1, 0);

    fetchMyAttendance(
      startDate.toISOString().split('T')[0],
      endDate.toISOString().split('T')[0]
    );
  };

  const handlePreviousMonth = () => {
    setSelectedMonth(new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() - 1));
  };

  const handleNextMonth = () => {
    setSelectedMonth(new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() + 1));
  };

  const handleCardPress = (attendanceId: string) => {
    navigation.navigate('AttendanceDetail', { attendanceId });
  };

  const filteredHistory = history.filter((record) =>
    selectedFilter === 'all' ? true : record.status === selectedFilter
  );

  const renderFilterButton = (filter: typeof FILTERS[0]) => {
    const isSelected = filter.value === selectedFilter;

    return (
      <TouchableOpacity
        key={filter.value}
        style={[
          styles.filterButton,
          isSelected && styles.filterButtonSelected,
        ]}
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
        {strings.empty.noAttendance}
      </Text>
      <Text variant="bodySmall" color={theme.colors.text.tertiary} align="center" style={styles.emptySubtext}>
        No records found for selected month
      </Text>
    </View>
  );

  return (
    <ScreenLayout safeArea padded={false}>
      <Header title={strings.student.history} />

      <View style={styles.filtersContainer}>
        {/* Month selector */}
        <View style={styles.monthSelector}>
          <TouchableOpacity
            onPress={handlePreviousMonth}
            style={styles.monthButton}
            activeOpacity={theme.interaction.activeOpacity}
          >
            <ChevronLeft size={20} color={theme.colors.text.primary} />
          </TouchableOpacity>

          <Text variant="body" weight="semibold" style={styles.monthText}>
            {formatDate(selectedMonth, 'MMMM yyyy')}
          </Text>

          <TouchableOpacity
            onPress={handleNextMonth}
            style={styles.monthButton}
            activeOpacity={theme.interaction.activeOpacity}
          >
            <ChevronRight size={20} color={theme.colors.text.primary} />
          </TouchableOpacity>
        </View>

        {/* Status filters */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterList}
        >
          {FILTERS.map(renderFilterButton)}
        </ScrollView>
      </View>

      {/* History list */}
      <FlatList
        data={filteredHistory}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <AttendanceCard
            schedule={item as any}
            status={item.status}
            presenceScore={item.presenceScore}
            onPress={() => handleCardPress(item.id)}
          />
        )}
        ListEmptyComponent={renderEmpty}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
      />
    </ScreenLayout>
  );
};

const styles = StyleSheet.create({
  filtersContainer: {
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
    paddingBottom: theme.spacing[4],
  },
  monthSelector: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: theme.spacing[4],
    paddingTop: theme.spacing[4],
    paddingBottom: theme.spacing[3],
  },
  monthButton: {
    padding: theme.spacing[2],
  },
  monthText: {
    flex: 1,
    textAlign: 'center',
  },
  filterList: {
    paddingHorizontal: theme.spacing[4],
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
  emptySubtext: {
    marginTop: theme.spacing[2],
  },
});
