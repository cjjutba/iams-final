/**
 * Faculty Analytics Dashboard Screen
 *
 * Dashboard showing analytics overview for faculty:
 * - Per-class attendance rate cards with horizontal bar visualization
 * - At-risk student count card
 * - Anomaly alert count card
 * - Tappable cards for future navigation to detail views
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
  ActivityIndicator,
} from 'react-native';
import { AlertTriangle, Users, TrendingDown, BarChart3 } from 'lucide-react-native';
import { useSchedule } from '../../hooks';
import { analyticsService } from '../../services/analyticsService';
import { theme } from '../../constants';
import type { ClassOverview, AtRiskStudent, AnomalyItem } from '../../types';
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

/** Get border color for attendance rate bar fill */
const getAttendanceBarBorder = (rate: number): string => {
  if (rate >= 80) return theme.colors.status.present.border;
  if (rate >= 60) return theme.colors.status.late.border;
  return theme.colors.status.absent.border;
};

/** Get risk level color */
const getRiskColor = (level: string): string => {
  switch (level) {
    case 'critical':
      return theme.colors.status.absent.fg;
    case 'high':
      return theme.colors.status.early_leave.fg;
    case 'medium':
      return theme.colors.status.late.fg;
    default:
      return theme.colors.text.secondary;
  }
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const FacultyAnalyticsDashboardScreen: React.FC = () => {
  const { schedules, isLoading: schedulesLoading } = useSchedule();

  const [classOverviews, setClassOverviews] = useState<ClassOverview[]>([]);
  const [atRiskStudents, setAtRiskStudents] = useState<AtRiskStudent[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ---------- data fetching ----------

  const fetchAnalytics = useCallback(async () => {
    try {
      setError(null);

      // Fetch at-risk students and anomalies in parallel
      const [atRiskResult, anomalyResult] = await Promise.allSettled([
        analyticsService.getAtRiskStudents(),
        analyticsService.getAnomalies(),
      ]);

      if (atRiskResult.status === 'fulfilled') {
        setAtRiskStudents(atRiskResult.value);
      }
      if (anomalyResult.status === 'fulfilled') {
        setAnomalies(anomalyResult.value.filter((a) => !a.resolved));
      }

      // Fetch class overviews for each schedule
      if (schedules && schedules.length > 0) {
        const overviewPromises = schedules.map((schedule) =>
          analyticsService
            .getClassOverview(schedule.id)
            .catch(() => null),
        );
        const results = await Promise.allSettled(overviewPromises);
        const overviews = results
          .filter(
            (r): r is PromiseFulfilledResult<ClassOverview | null> =>
              r.status === 'fulfilled',
          )
          .map((r) => r.value)
          .filter((v): v is ClassOverview => v !== null);

        setClassOverviews(overviews);
      }
    } catch {
      setError('Failed to load analytics data.');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [schedules]);

  useEffect(() => {
    if (!schedulesLoading) {
      fetchAnalytics();
    }
  }, [fetchAnalytics, schedulesLoading]);

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    fetchAnalytics();
  }, [fetchAnalytics]);

  // ---------- loading state ----------

  if (isLoading && !isRefreshing) {
    return (
      <ScreenLayout safeArea safeAreaEdges={['top']} padded={false}>
        <Header title="Analytics" />
        <View style={styles.centerContainer}>
          <Loader size="large" />
          <Text
            variant="body"
            color={theme.colors.text.secondary}
            style={styles.loadingText}
          >
            Loading analytics...
          </Text>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- error state ----------

  if (error && classOverviews.length === 0) {
    return (
      <ScreenLayout safeArea safeAreaEdges={['top']} padded={false}>
        <Header title="Analytics" />
        <View style={styles.centerContainer}>
          <BarChart3 size={40} color={theme.colors.text.tertiary} />
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

  const unresolvedAnomalyCount = anomalies.length;
  const atRiskCount = atRiskStudents.length;
  const highRiskCount = atRiskStudents.filter(
    (s) => s.risk_level === 'critical' || s.risk_level === 'high',
  ).length;

  // ---------- main render ----------

  return (
    <ScreenLayout safeArea safeAreaEdges={['top']} padded={false}>
      <Header title="Analytics" />

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
        {/* Summary cards row */}
        <View style={styles.summaryRow}>
          {/* At-Risk Students Card */}
          <TouchableOpacity
            style={styles.summaryCardWrapper}
            activeOpacity={theme.interaction.activeOpacity}
          >
            <Card style={styles.summaryCard}>
              <View style={styles.summaryIconContainer}>
                <TrendingDown
                  size={20}
                  color={atRiskCount > 0 ? theme.colors.status.absent.fg : theme.colors.text.tertiary}
                />
              </View>
              <Text variant="h2" weight="700" style={styles.summaryNumber}>
                {atRiskCount}
              </Text>
              <Text
                variant="caption"
                color={theme.colors.text.secondary}
                numberOfLines={1}
              >
                At-Risk Students
              </Text>
              {highRiskCount > 0 && (
                <Text
                  variant="caption"
                  color={theme.colors.status.absent.fg}
                  style={styles.summarySubtext}
                >
                  {highRiskCount} high/critical
                </Text>
              )}
            </Card>
          </TouchableOpacity>

          {/* Anomaly Alerts Card */}
          <TouchableOpacity
            style={styles.summaryCardWrapper}
            activeOpacity={theme.interaction.activeOpacity}
          >
            <Card style={styles.summaryCard}>
              <View style={styles.summaryIconContainer}>
                <AlertTriangle
                  size={20}
                  color={
                    unresolvedAnomalyCount > 0
                      ? theme.colors.status.late.fg
                      : theme.colors.text.tertiary
                  }
                />
              </View>
              <Text variant="h2" weight="700" style={styles.summaryNumber}>
                {unresolvedAnomalyCount}
              </Text>
              <Text
                variant="caption"
                color={theme.colors.text.secondary}
                numberOfLines={1}
              >
                Anomaly Alerts
              </Text>
              {unresolvedAnomalyCount > 0 && (
                <Text
                  variant="caption"
                  color={theme.colors.status.late.fg}
                  style={styles.summarySubtext}
                >
                  Unresolved
                </Text>
              )}
            </Card>
          </TouchableOpacity>
        </View>

        {/* Class Attendance Section */}
        <Text variant="h3" weight="600" style={styles.sectionTitle}>
          Class Attendance
        </Text>

        {classOverviews.length === 0 ? (
          <Card style={styles.emptyCard}>
            <Text
              variant="body"
              color={theme.colors.text.secondary}
              align="center"
            >
              No class data available yet.
            </Text>
            <Text
              variant="caption"
              color={theme.colors.text.tertiary}
              align="center"
              style={styles.emptySubtext}
            >
              Analytics will appear after classes have sessions recorded.
            </Text>
          </Card>
        ) : (
          classOverviews.map((overview) => (
            <ClassOverviewCard key={overview.schedule_id} overview={overview} />
          ))
        )}

        {/* At-Risk Students List */}
        {atRiskStudents.length > 0 && (
          <>
            <Text variant="h3" weight="600" style={styles.sectionTitle}>
              At-Risk Students
            </Text>
            {atRiskStudents.slice(0, 5).map((student) => (
              <AtRiskStudentCard key={`${student.student_id}-${student.schedule_id}`} student={student} />
            ))}
            {atRiskStudents.length > 5 && (
              <TouchableOpacity
                style={styles.viewAllButton}
                activeOpacity={theme.interaction.activeOpacity}
              >
                <Text
                  variant="bodySmall"
                  weight="600"
                  color={theme.colors.primary}
                >
                  View All {atRiskStudents.length} At-Risk Students
                </Text>
              </TouchableOpacity>
            )}
          </>
        )}

        {/* Anomaly Alerts List */}
        {anomalies.length > 0 && (
          <>
            <Text variant="h3" weight="600" style={styles.sectionTitle}>
              Recent Anomalies
            </Text>
            {anomalies.slice(0, 3).map((anomaly) => (
              <AnomalyCard key={anomaly.id} anomaly={anomaly} />
            ))}
            {anomalies.length > 3 && (
              <TouchableOpacity
                style={styles.viewAllButton}
                activeOpacity={theme.interaction.activeOpacity}
              >
                <Text
                  variant="bodySmall"
                  weight="600"
                  color={theme.colors.primary}
                >
                  View All {anomalies.length} Anomalies
                </Text>
              </TouchableOpacity>
            )}
          </>
        )}
      </ScrollView>
    </ScreenLayout>
  );
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Card showing class overview with attendance rate bar */
const ClassOverviewCard: React.FC<{ overview: ClassOverview }> = ({ overview }) => {
  const rate = Math.round(overview.average_attendance_rate);
  const barColor = getAttendanceBarBg(rate);
  const barBorder = getAttendanceBarBorder(rate);
  const textColor = getAttendanceColor(rate);

  return (
    <TouchableOpacity activeOpacity={theme.interaction.activeOpacity}>
      <Card style={styles.classCard}>
        {/* Header: subject name + rate */}
        <View style={styles.classCardHeader}>
          <View style={styles.classCardTitleContainer}>
            <Text variant="bodySmall" weight="600" numberOfLines={1}>
              {overview.subject_name}
            </Text>
            <Text variant="caption" color={theme.colors.text.tertiary}>
              {overview.subject_code}
            </Text>
          </View>
          <Text variant="h3" weight="700" color={textColor}>
            {rate}%
          </Text>
        </View>

        {/* Attendance rate bar */}
        <View style={styles.barContainer}>
          <View style={styles.barBackground}>
            <View
              style={[
                styles.barFill,
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

        {/* Stats row */}
        <View style={styles.statsRow}>
          <StatItem
            label="Sessions"
            value={String(overview.total_sessions)}
          />
          <StatItem
            label="Enrolled"
            value={String(overview.total_enrolled)}
            icon={<Users size={12} color={theme.colors.text.tertiary} />}
          />
          <StatItem
            label="Early Leaves"
            value={String(overview.early_leave_count)}
          />
          {overview.anomaly_count > 0 && (
            <StatItem
              label="Anomalies"
              value={String(overview.anomaly_count)}
              highlight
            />
          )}
        </View>
      </Card>
    </TouchableOpacity>
  );
};

/** Small stat display used inside class cards */
const StatItem: React.FC<{
  label: string;
  value: string;
  icon?: React.ReactNode;
  highlight?: boolean;
}> = ({ label, value, icon, highlight = false }) => (
  <View style={styles.statItem}>
    <View style={styles.statValueRow}>
      {icon && <View style={styles.statIcon}>{icon}</View>}
      <Text
        variant="bodySmall"
        weight="600"
        color={highlight ? theme.colors.status.late.fg : theme.colors.text.primary}
      >
        {value}
      </Text>
    </View>
    <Text variant="caption" color={theme.colors.text.tertiary}>
      {label}
    </Text>
  </View>
);

/** Card for an at-risk student */
const AtRiskStudentCard: React.FC<{ student: AtRiskStudent }> = ({ student }) => {
  const riskColor = getRiskColor(student.risk_level);

  return (
    <TouchableOpacity activeOpacity={theme.interaction.activeOpacity}>
      <Card style={styles.atRiskCard}>
        <View style={styles.atRiskHeader}>
          <View style={styles.atRiskInfo}>
            <Text variant="bodySmall" weight="600" numberOfLines={1}>
              {student.student_name}
            </Text>
            <Text variant="caption" color={theme.colors.text.tertiary}>
              {student.subject_name} ({student.subject_code})
            </Text>
          </View>
          <View style={styles.atRiskRight}>
            <Text variant="bodySmall" weight="700" color={riskColor}>
              {Math.round(student.attendance_rate)}%
            </Text>
            <View
              style={[styles.riskBadge, { backgroundColor: riskColor + '20' }]}
            >
              <Text
                variant="caption"
                weight="600"
                color={riskColor}
                style={styles.riskBadgeText}
              >
                {student.risk_level.toUpperCase()}
              </Text>
            </View>
          </View>
        </View>

        {/* Attendance bar */}
        <View style={styles.barContainer}>
          <View style={styles.barBackground}>
            <View
              style={[
                styles.barFill,
                {
                  width: `${Math.min(student.attendance_rate, 100)}%`,
                  backgroundColor: getAttendanceBarBg(student.attendance_rate),
                  borderColor: getAttendanceBarBorder(student.attendance_rate),
                  borderWidth: 1,
                },
              ]}
            />
          </View>
        </View>

        <Text variant="caption" color={theme.colors.text.tertiary}>
          {student.sessions_missed} of {student.sessions_total} sessions missed
        </Text>
      </Card>
    </TouchableOpacity>
  );
};

/** Card for an anomaly alert */
const AnomalyCard: React.FC<{ anomaly: AnomalyItem }> = ({ anomaly }) => {
  const severityColor =
    anomaly.severity === 'high'
      ? theme.colors.status.absent.fg
      : anomaly.severity === 'medium'
        ? theme.colors.status.late.fg
        : theme.colors.text.secondary;

  const detectedDate = new Date(anomaly.detected_at);
  const formattedDate = `${detectedDate.toLocaleDateString()} ${detectedDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;

  return (
    <TouchableOpacity activeOpacity={theme.interaction.activeOpacity}>
      <Card style={styles.anomalyCard}>
        <View style={styles.anomalyHeader}>
          <AlertTriangle size={16} color={severityColor} />
          <View style={styles.anomalyInfo}>
            <Text variant="bodySmall" weight="600" numberOfLines={2}>
              {anomaly.description}
            </Text>
            <Text variant="caption" color={theme.colors.text.tertiary}>
              {anomaly.subject_name && `${anomaly.subject_name} - `}
              {formattedDate}
            </Text>
          </View>
          <View
            style={[styles.severityBadge, { backgroundColor: severityColor + '20' }]}
          >
            <Text variant="caption" weight="600" color={severityColor}>
              {anomaly.severity.toUpperCase()}
            </Text>
          </View>
        </View>
      </Card>
    </TouchableOpacity>
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

  // Summary row
  summaryRow: {
    flexDirection: 'row',
    gap: theme.spacing[3],
    marginBottom: theme.spacing[6],
  },
  summaryCardWrapper: {
    flex: 1,
  },
  summaryCard: {
    alignItems: 'center',
    paddingVertical: theme.spacing[4],
  },
  summaryIconContainer: {
    marginBottom: theme.spacing[2],
  },
  summaryNumber: {
    marginBottom: theme.spacing[1],
  },
  summarySubtext: {
    marginTop: theme.spacing[1],
  },

  // Section titles
  sectionTitle: {
    marginBottom: theme.spacing[3],
    marginTop: theme.spacing[2],
  },

  // Class cards
  classCard: {
    marginBottom: theme.spacing[3],
  },
  classCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: theme.spacing[3],
  },
  classCardTitleContainer: {
    flex: 1,
    marginRight: theme.spacing[3],
  },

  // Attendance bar
  barContainer: {
    marginBottom: theme.spacing[3],
  },
  barBackground: {
    height: 8,
    backgroundColor: theme.colors.secondary,
    borderRadius: theme.borderRadius.full,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    borderRadius: theme.borderRadius.full,
    minWidth: 4,
  },

  // Stats row
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  statItem: {
    alignItems: 'center',
  },
  statValueRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statIcon: {
    marginRight: theme.spacing[1],
  },

  // At-risk cards
  atRiskCard: {
    marginBottom: theme.spacing[3],
  },
  atRiskHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: theme.spacing[3],
  },
  atRiskInfo: {
    flex: 1,
    marginRight: theme.spacing[3],
  },
  atRiskRight: {
    alignItems: 'flex-end',
  },
  riskBadge: {
    paddingHorizontal: theme.spacing[2],
    paddingVertical: 2,
    borderRadius: theme.borderRadius.sm,
    marginTop: theme.spacing[1],
  },
  riskBadgeText: {
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },

  // Anomaly cards
  anomalyCard: {
    marginBottom: theme.spacing[3],
  },
  anomalyHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  anomalyInfo: {
    flex: 1,
    marginLeft: theme.spacing[3],
    marginRight: theme.spacing[2],
  },
  severityBadge: {
    paddingHorizontal: theme.spacing[2],
    paddingVertical: 2,
    borderRadius: theme.borderRadius.sm,
  },

  // Empty state
  emptyCard: {
    paddingVertical: theme.spacing[8],
  },
  emptySubtext: {
    marginTop: theme.spacing[2],
  },

  // View all
  viewAllButton: {
    alignItems: 'center',
    paddingVertical: theme.spacing[3],
    marginBottom: theme.spacing[2],
  },
});
