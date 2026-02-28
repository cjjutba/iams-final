/**
 * Faculty Alerts Screen
 *
 * Shows early leave alerts fetched from the API with filtering.
 * Supports pull-to-refresh, loading/error/empty states, and
 * navigation to student detail on tap.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { AlertTriangle, RefreshCw } from 'lucide-react-native';
import { api } from '../../utils/api';
import { useToast } from '../../hooks/useToast';
import { theme, strings } from '../../constants';
import { getErrorMessage } from '../../utils';
import type { FacultyStackParamList, EarlyLeaveEvent } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Button } from '../../components/ui';
import { AlertCard } from '../../components/cards';

type FacultyAlertsNavigationProp = StackNavigationProp<FacultyStackParamList, 'FacultyTabs'>;

const FILTERS = [
  { label: 'Today', value: 'today' },
  { label: 'This Week', value: 'week' },
  { label: 'All', value: 'all' },
] as const;

type FilterValue = typeof FILTERS[number]['value'];

export const FacultyAlertsScreen: React.FC = () => {
  const navigation = useNavigation<FacultyAlertsNavigationProp>();
  const { showError } = useToast();

  const [selectedFilter, setSelectedFilter] = useState<FilterValue>('today');
  const [alerts, setAlerts] = useState<EarlyLeaveEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ---------- data fetching ----------

  const fetchAlerts = useCallback(
    async (silent = false) => {
      if (!silent) setIsLoading(true);
      setError(null);

      try {
        const response = await api.get<EarlyLeaveEvent[]>(
          '/attendance/alerts',
          { params: { filter: selectedFilter } }
        );
        setAlerts(response.data || []);
      } catch (err) {
        setError(getErrorMessage(err));
        showError(getErrorMessage(err), 'Load Failed');
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [selectedFilter]
  );

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    fetchAlerts(true);
  }, [fetchAlerts]);

  // ---------- navigation ----------

  const handleAlertPress = (event: EarlyLeaveEvent) => {
    navigation.navigate('StudentDetail', {
      studentId: event.student_id,
      scheduleId: event.schedule_id,
    });
  };

  // ---------- filter buttons ----------

  const renderFilterButton = (filter: typeof FILTERS[number]) => {
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

  // ---------- empty state ----------

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <AlertTriangle size={48} color={theme.colors.text.tertiary} style={styles.emptyIcon} />
      <Text variant="body" color={theme.colors.text.secondary} align="center">
        {strings.faculty.noAlertsToday}
      </Text>
      <Text
        variant="bodySmall"
        color={theme.colors.text.tertiary}
        align="center"
        style={styles.emptySubtext}
      >
        No early leave alerts for the selected period
      </Text>
    </View>
  );

  // ---------- error state ----------

  if (error && !isRefreshing && alerts.length === 0) {
    return (
      <ScreenLayout safeArea padded={false}>
        <Header title={strings.faculty.alerts} />
        <View style={styles.errorContainer}>
          <RefreshCw size={40} color={theme.colors.text.tertiary} style={styles.errorIcon} />
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            Unable to load alerts. Please try again.
          </Text>
          <Button
            variant="secondary"
            size="md"
            onPress={() => fetchAlerts()}
            style={styles.retryButton}
          >
            {strings.common.retry}
          </Button>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- loading state ----------

  if (isLoading && alerts.length === 0) {
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

        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <Text
            variant="bodySmall"
            color={theme.colors.text.secondary}
            align="center"
            style={styles.loadingText}
          >
            {strings.common.loading}
          </Text>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- main render ----------

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
        style={styles.list}
        contentContainerStyle={[
          styles.listContent,
          alerts.length === 0 && styles.listContentEmpty,
        ]}
        showsVerticalScrollIndicator={false}
        alwaysBounceVertical={true}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
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
  filterContainer: {
    flexGrow: 0,
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
  listContentEmpty: {
    flexGrow: 1,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: theme.spacing[12],
  },
  emptyIcon: {
    marginBottom: theme.spacing[4],
  },
  emptySubtext: {
    marginTop: theme.spacing[2],
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: theme.spacing[3],
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
