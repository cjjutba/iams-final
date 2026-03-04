/**
 * Student Analytics Screen
 *
 * Displays the student's personal attendance analytics:
 * - Overall attendance rate (large percentage display)
 * - Current streak and trend indicator
 * - Per-subject breakdown cards with attendance rate bars
 * - Each subject shows: name, rate bar, sessions attended/total
 *
 * Uses pure React Native components with View-based bar charts.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Flame,
  Award,
} from 'lucide-react-native';
import { analyticsService } from '../../services/analyticsService';
import { theme } from '../../constants';
import type { StudentAnalyticsDashboard, SubjectBreakdown } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Loader } from '../../components/ui';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Get color for attendance rate percentage */
const getAttendanceColor = (rate: number): string => {
  if (rate >= 80) return theme.colors.status.present.fg;
  if (rate >= 60) return theme.colors.status.late.fg;
  return theme.colors.status.absent.fg;
};

/** Get background color for attendance rate bar fill */
const getAttendanceBarBg = (rate: number): string => {
  if (rate >= 80) return theme.colors.status.present.bg;
  if (rate >= 60) return theme.colors.status.late.bg;
  return theme.colors.status.absent.bg;
};

/** Get border color for bar fill */
const getAttendanceBarBorder = (rate: number): string => {
  if (rate >= 80) return theme.colors.status.present.border;
  if (rate >= 60) return theme.colors.status.late.border;
  return theme.colors.status.absent.border;
};

/** Get trend icon and label */
const getTrendInfo = (trend: string) => {
  switch (trend) {
    case 'improving':
      return {
        icon: TrendingUp,
        label: 'Improving',
        color: theme.colors.status.present.fg,
      };
    case 'declining':
      return {
        icon: TrendingDown,
        label: 'Declining',
        color: theme.colors.status.absent.fg,
      };
    default:
      return {
        icon: Minus,
        label: 'Stable',
        color: theme.colors.text.secondary,
      };
  }
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const StudentAnalyticsScreen: React.FC = () => {
  const [dashboard, setDashboard] = useState<StudentAnalyticsDashboard | null>(null);
  const [subjects, setSubjects] = useState<SubjectBreakdown[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ---------- data fetching ----------

  const fetchAnalytics = useCallback(async () => {
    try {
      setError(null);

      const [dashboardResult, subjectsResult] = await Promise.allSettled([
        analyticsService.getStudentDashboard(),
        analyticsService.getStudentSubjects(),
      ]);

      if (dashboardResult.status === 'fulfilled') {
        setDashboard(dashboardResult.value);
      } else {
        setError('Failed to load dashboard data.');
      }

      if (subjectsResult.status === 'fulfilled') {
        setSubjects(subjectsResult.value);
      }
    } catch {
      setError('Failed to load analytics data.');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    fetchAnalytics();
  }, [fetchAnalytics]);

  // ---------- loading state ----------

  if (isLoading && !isRefreshing) {
    return (
      <ScreenLayout safeArea padded={false}>
        <Header title="My Analytics" />
        <View style={styles.centerContainer}>
          <Loader size="large" />
          <Text
            variant="body"
            color={theme.colors.text.secondary}
            style={styles.loadingText}
          >
            Loading your analytics...
          </Text>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- error state ----------

  if (error && !dashboard) {
    return (
      <ScreenLayout safeArea padded={false}>
        <Header title="My Analytics" />
        <View style={styles.centerContainer}>
          <Award size={40} color={theme.colors.text.tertiary} />
          <Text
            variant="body"
            color={theme.colors.text.secondary}
            align="center"
            style={styles.errorText}
          >
            {error}
          </Text>
          <TouchableOpacity
            style={styles.retryButton}
            onPress={handleRefresh}
            activeOpacity={theme.interaction.activeOpacity}
          >
            <Text variant="bodySmall" weight="600" color={theme.colors.primary}>
              Tap to Retry
            </Text>
          </TouchableOpacity>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- computed values ----------

  const overallRate = dashboard
    ? Math.round(dashboard.overall_attendance_rate)
    : 0;
  const trendInfo = dashboard ? getTrendInfo(dashboard.trend) : getTrendInfo('stable');
  const TrendIcon = trendInfo.icon;

  // ---------- main render ----------

  return (
    <ScreenLayout safeArea padded={false}>
      <Header title="My Analytics" />

      <ScrollView
        contentContainerStyle={styles.scrollContent}
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
      >
        {/* Overall Attendance Rate - Hero Card */}
        <Card style={styles.heroCard}>
          <Text
            variant="caption"
            color={theme.colors.text.secondary}
            weight="600"
            style={styles.heroLabel}
          >
            OVERALL ATTENDANCE
          </Text>

          {/* Large percentage display */}
          <View style={styles.rateDisplay}>
            <Text
              style={[styles.rateNumber, { color: getAttendanceColor(overallRate) }]}
            >
              {overallRate}
            </Text>
            <Text
              style={[styles.ratePercent, { color: getAttendanceColor(overallRate) }]}
            >
              %
            </Text>
          </View>

          {/* Full-width bar */}
          <View style={styles.heroBarContainer}>
            <View style={styles.heroBarBackground}>
              <View
                style={[
                  styles.heroBarFill,
                  {
                    width: `${Math.min(overallRate, 100)}%`,
                    backgroundColor: getAttendanceBarBg(overallRate),
                    borderColor: getAttendanceBarBorder(overallRate),
                    borderWidth: 1,
                  },
                ]}
              />
            </View>
          </View>

          {/* Stats row under bar */}
          {dashboard && (
            <View style={styles.heroStatsRow}>
              <Text variant="caption" color={theme.colors.text.secondary}>
                {dashboard.total_classes_attended} of {dashboard.total_classes} classes
              </Text>
              <View style={styles.trendContainer}>
                <TrendIcon size={14} color={trendInfo.color} />
                <Text
                  variant="caption"
                  weight="600"
                  color={trendInfo.color}
                  style={styles.trendLabel}
                >
                  {trendInfo.label}
                </Text>
              </View>
            </View>
          )}
        </Card>

        {/* Streak and Rank Row */}
        {dashboard && (
          <View style={styles.metricsRow}>
            {/* Current Streak */}
            <Card style={styles.metricCard}>
              <Flame
                size={20}
                color={
                  dashboard.current_streak > 0
                    ? theme.colors.status.early_leave.fg
                    : theme.colors.text.tertiary
                }
              />
              <Text variant="h2" weight="700" style={styles.metricNumber}>
                {dashboard.current_streak}
              </Text>
              <Text
                variant="caption"
                color={theme.colors.text.secondary}
                align="center"
              >
                Day Streak
              </Text>
              {dashboard.longest_streak > 0 && (
                <Text
                  variant="caption"
                  color={theme.colors.text.tertiary}
                  style={styles.metricSubtext}
                >
                  Best: {dashboard.longest_streak}
                </Text>
              )}
            </Card>

            {/* Class Rank */}
            <Card style={styles.metricCard}>
              <Award size={20} color={theme.colors.text.secondary} />
              <Text variant="h2" weight="700" style={styles.metricNumber}>
                {dashboard.rank_in_class !== null
                  ? `#${dashboard.rank_in_class}`
                  : '--'}
              </Text>
              <Text
                variant="caption"
                color={theme.colors.text.secondary}
                align="center"
              >
                Class Rank
              </Text>
              {dashboard.total_students !== null && (
                <Text
                  variant="caption"
                  color={theme.colors.text.tertiary}
                  style={styles.metricSubtext}
                >
                  of {dashboard.total_students}
                </Text>
              )}
            </Card>

            {/* Early Leaves */}
            <Card style={styles.metricCard}>
              <TrendingDown
                size={20}
                color={
                  dashboard.early_leave_count > 0
                    ? theme.colors.status.early_leave.fg
                    : theme.colors.text.tertiary
                }
              />
              <Text variant="h2" weight="700" style={styles.metricNumber}>
                {dashboard.early_leave_count}
              </Text>
              <Text
                variant="caption"
                color={theme.colors.text.secondary}
                align="center"
                numberOfLines={1}
              >
                Early Leaves
              </Text>
            </Card>
          </View>
        )}

        {/* Subject Breakdown Section */}
        <Text variant="h3" weight="600" style={styles.sectionTitle}>
          Subjects
        </Text>

        {subjects.length === 0 ? (
          <Card style={styles.emptyCard}>
            <Text
              variant="body"
              color={theme.colors.text.secondary}
              align="center"
            >
              No subject data available.
            </Text>
            <Text
              variant="caption"
              color={theme.colors.text.tertiary}
              align="center"
              style={styles.emptySubtext}
            >
              Subject breakdowns will appear after your attendance is recorded.
            </Text>
          </Card>
        ) : (
          subjects.map((subject) => (
            <SubjectCard key={subject.schedule_id} subject={subject} />
          ))
        )}
      </ScrollView>
    </ScreenLayout>
  );
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Card showing per-subject attendance breakdown */
const SubjectCard: React.FC<{ subject: SubjectBreakdown }> = ({ subject }) => {
  const rate = Math.round(subject.attendance_rate);
  const barColor = getAttendanceBarBg(rate);
  const barBorder = getAttendanceBarBorder(rate);
  const textColor = getAttendanceColor(rate);

  return (
    <Card style={styles.subjectCard}>
      {/* Header: subject name + rate */}
      <View style={styles.subjectHeader}>
        <View style={styles.subjectTitleContainer}>
          <Text variant="bodySmall" weight="600" numberOfLines={1}>
            {subject.subject_name}
          </Text>
          <Text variant="caption" color={theme.colors.text.tertiary}>
            {subject.subject_code}
          </Text>
        </View>
        <Text variant="h4" weight="700" color={textColor}>
          {rate}%
        </Text>
      </View>

      {/* Attendance bar */}
      <View style={styles.subjectBarContainer}>
        <View style={styles.subjectBarBackground}>
          <View
            style={[
              styles.subjectBarFill,
              {
                width: `${Math.min(rate, 100)}%`,
                backgroundColor: barColor,
                borderColor: barBorder,
                borderWidth: 1,
              },
            ]}
          />
        </View>
      </View>

      {/* Sessions info */}
      <View style={styles.subjectFooter}>
        <Text variant="caption" color={theme.colors.text.secondary}>
          {subject.sessions_attended} of {subject.sessions_total} sessions
        </Text>
        {subject.last_attended && (
          <Text variant="caption" color={theme.colors.text.tertiary}>
            Last: {new Date(subject.last_attended).toLocaleDateString()}
          </Text>
        )}
      </View>
    </Card>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: theme.spacing[6],
  },
  loadingText: {
    marginTop: theme.spacing[4],
  },
  errorText: {
    marginTop: theme.spacing[4],
  },
  retryButton: {
    marginTop: theme.spacing[4],
    paddingVertical: theme.spacing[2],
    paddingHorizontal: theme.spacing[4],
  },
  scrollContent: {
    padding: theme.spacing[4],
    paddingBottom: theme.spacing[8],
  },

  // Hero card
  heroCard: {
    alignItems: 'center',
    paddingVertical: theme.spacing[6],
    marginBottom: theme.spacing[4],
  },
  heroLabel: {
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: theme.spacing[2],
  },
  rateDisplay: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    marginBottom: theme.spacing[4],
  },
  rateNumber: {
    fontSize: 64,
    fontWeight: '700',
    lineHeight: 72,
  },
  ratePercent: {
    fontSize: 28,
    fontWeight: '600',
    lineHeight: 40,
    marginBottom: 8,
    marginLeft: 2,
  },
  heroBarContainer: {
    width: '100%',
    marginBottom: theme.spacing[3],
  },
  heroBarBackground: {
    height: 10,
    backgroundColor: theme.colors.secondary,
    borderRadius: theme.borderRadius.full,
    overflow: 'hidden',
  },
  heroBarFill: {
    height: '100%',
    borderRadius: theme.borderRadius.full,
    minWidth: 4,
  },
  heroStatsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: '100%',
    alignItems: 'center',
  },
  trendContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  trendLabel: {
    marginLeft: theme.spacing[1],
  },

  // Metrics row
  metricsRow: {
    flexDirection: 'row',
    gap: theme.spacing[3],
    marginBottom: theme.spacing[6],
  },
  metricCard: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: theme.spacing[4],
    paddingHorizontal: theme.spacing[2],
  },
  metricNumber: {
    marginTop: theme.spacing[2],
    marginBottom: theme.spacing[1],
  },
  metricSubtext: {
    marginTop: theme.spacing[1],
  },

  // Section title
  sectionTitle: {
    marginBottom: theme.spacing[3],
  },

  // Subject cards
  subjectCard: {
    marginBottom: theme.spacing[3],
  },
  subjectHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: theme.spacing[3],
  },
  subjectTitleContainer: {
    flex: 1,
    marginRight: theme.spacing[3],
  },
  subjectBarContainer: {
    marginBottom: theme.spacing[2],
  },
  subjectBarBackground: {
    height: 8,
    backgroundColor: theme.colors.secondary,
    borderRadius: theme.borderRadius.full,
    overflow: 'hidden',
  },
  subjectBarFill: {
    height: '100%',
    borderRadius: theme.borderRadius.full,
    minWidth: 4,
  },
  subjectFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },

  // Empty state
  emptyCard: {
    paddingVertical: theme.spacing[8],
  },
  emptySubtext: {
    marginTop: theme.spacing[2],
  },
});
