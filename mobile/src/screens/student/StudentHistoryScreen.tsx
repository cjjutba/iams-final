/**
 * Student History Screen
 *
 * Shows attendance history with:
 * - Month navigation (prev/next)
 * - Status filter pills (All/Present/Late/Absent)
 * - Attendance record list with pull-to-refresh
 * - Loading, error, and empty states
 */

import React, { useState, useEffect, useCallback } from 'react';
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
import { ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react-native';
import { useAttendance } from '../../hooks';
import { useToast } from '../../hooks/useToast';
import { theme, strings } from '../../constants';
import { formatDate, formatTime, formatPercentage } from '../../utils';
import type { StudentStackParamList, AttendanceRecord, AttendanceStatus } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Badge, Button, Loader } from '../../components/ui';

type StudentHistoryNavigationProp = StackNavigationProp<StudentStackParamList, 'StudentTabs'>;

const FILTERS: Array<{ label: string; value: AttendanceStatus | 'all' }> = [
  { label: 'All', value: 'all' },
  { label: 'Present', value: 'present' as AttendanceStatus },
  { label: 'Late', value: 'late' as AttendanceStatus },
  { label: 'Absent', value: 'absent' as AttendanceStatus },
];

export const StudentHistoryScreen: React.FC = () => {
  const navigation = useNavigation<StudentHistoryNavigationProp>();
  const { history, isLoading, error, fetchMyAttendance, clearError } = useAttendance();
  const { showError } = useToast();

  const [selectedMonth, setSelectedMonth] = useState(new Date());
  const [selectedFilter, setSelectedFilter] = useState<AttendanceStatus | 'all'>('all');

  // ---------- data fetching ----------

  const loadHistory = useCallback(() => {
    const startDate = new Date(selectedMonth.getFullYear(), selectedMonth.getMonth(), 1);
    const endDate = new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() + 1, 0);

    fetchMyAttendance(
      startDate.toISOString().split('T')[0],
      endDate.toISOString().split('T')[0]
    );
  }, [selectedMonth, fetchMyAttendance]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    if (error) showError(error, 'Load Failed');
  }, [error]);

  const handleRefresh = useCallback(() => {
    clearError();
    loadHistory();
  }, [loadHistory, clearError]);

  // ---------- month navigation ----------

  const handlePreviousMonth = () => {
    setSelectedMonth(new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() - 1));
  };

  const handleNextMonth = () => {
    const nextMonth = new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() + 1);
    // Don't navigate beyond current month
    if (nextMonth <= new Date()) {
      setSelectedMonth(nextMonth);
    }
  };

  // ---------- card press ----------

  const handleCardPress = (record: AttendanceRecord) => {
    navigation.navigate('AttendanceDetail', {
      attendanceId: record.id,
      scheduleId: record.schedule_id,
      date: record.date,
    });
  };

  // ---------- filtering ----------

  const filteredHistory = (history || []).filter((record: AttendanceRecord) =>
    selectedFilter === 'all' ? true : record.status === selectedFilter
  );

  // ---------- filter buttons ----------

  const renderFilterButton = (filter: (typeof FILTERS)[number]) => {
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
          weight={isSelected ? '600' : '400'}
          color={isSelected ? theme.colors.primaryForeground : theme.colors.text.secondary}
        >
          {filter.label}
        </Text>
      </TouchableOpacity>
    );
  };

  // ---------- attendance record card ----------

  const renderHistoryCard = ({ item }: { item: AttendanceRecord }) => (
    <Card onPress={() => handleCardPress(item)} style={styles.historyCard}>
      <View style={styles.cardContent}>
        <View style={styles.cardMainInfo}>
          {/* Date */}
          <Text variant="caption" color={theme.colors.text.tertiary} style={styles.cardDate}>
            {formatDate(item.date, 'EEEE, MMM d')}
          </Text>

          {/* Schedule info -- we only have schedule_id, not subject name in AttendanceRecord */}
          {item.check_in_time && (
            <Text variant="bodySmall" color={theme.colors.text.secondary} style={styles.cardTime}>
              Check-in: {formatTime(item.check_in_time)}
            </Text>
          )}

          {/* Status + presence score */}
          <View style={styles.statusRow}>
            <Badge status={item.status} size="sm" />
            {item.presence_score !== undefined && item.presence_score !== null && (
              <Text
                variant="bodySmall"
                color={theme.colors.text.secondary}
                style={styles.score}
              >
                {formatPercentage(item.presence_score)} present
              </Text>
            )}
          </View>
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
          {strings.empty.noAttendance}
        </Text>
        <Text
          variant="bodySmall"
          color={theme.colors.text.tertiary}
          align="center"
          style={styles.emptySubtext}
        >
          No records found for {formatDate(selectedMonth, 'MMMM yyyy')}
        </Text>
      </View>
    );
  };

  // ---------- error state (full screen, only when no cached data) ----------

  if (error && (!history || history.length === 0) && !isLoading) {
    return (
      <ScreenLayout safeArea safeAreaEdges={['top']} padded={false}>
        <Header title={strings.student.history} />
        <View style={styles.errorContainer}>
          <RefreshCw size={40} color={theme.colors.text.tertiary} style={styles.errorIcon} />
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            Unable to load attendance history. Please try again.
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

          <Text variant="body" weight="600" style={styles.monthText}>
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
        renderItem={renderHistoryCard}
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
  filtersContainer: {
    flexGrow: 0,
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
    backgroundColor: theme.colors.secondary,
  },
  filterButtonSelected: {
    backgroundColor: theme.colors.primary,
  },
  list: {
    flex: 1,
  },
  listContent: {
    padding: theme.spacing[4],
  },
  historyCard: {
    marginBottom: theme.spacing[3],
  },
  cardContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  cardMainInfo: {
    flex: 1,
  },
  cardDate: {
    marginBottom: theme.spacing[1],
  },
  cardTime: {
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
