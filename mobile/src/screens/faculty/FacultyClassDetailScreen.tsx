/**
 * Faculty Class Detail Screen
 *
 * Shows attendance summary and student list for a specific class session.
 * Fetches attendance data from the API. Includes loading, error, and
 * empty states. Student taps navigate to student detail.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { RefreshCw } from 'lucide-react-native';
import { attendanceService } from '../../services';
import { theme, strings } from '../../constants';
import { formatDate, getErrorMessage } from '../../utils';
import type {
  FacultyStackParamList,
  LiveAttendanceResponse,
  StudentAttendanceStatus,
} from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Loader, Button } from '../../components/ui';

type ClassDetailRouteProp = RouteProp<FacultyStackParamList, 'ClassDetail'>;
type ClassDetailNavigationProp = StackNavigationProp<FacultyStackParamList, 'ClassDetail'>;

export const FacultyClassDetailScreen: React.FC = () => {
  const route = useRoute<ClassDetailRouteProp>();
  const navigation = useNavigation<ClassDetailNavigationProp>();

  const { scheduleId, date } = route.params;

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [classData, setClassData] = useState<LiveAttendanceResponse | null>(null);

  // ---------- data fetching ----------

  const loadClassDetails = useCallback(
    async (silent = false) => {
      if (!silent) setIsLoading(true);
      setError(null);

      try {
        const data = await attendanceService.getLiveAttendance(scheduleId);
        setClassData(data);
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [scheduleId]
  );

  useEffect(() => {
    loadClassDetails();
  }, [loadClassDetails]);

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    loadClassDetails(true);
  }, [loadClassDetails]);

  const handleStudentPress = (studentId: string) => {
    navigation.navigate('StudentDetail', { studentId, scheduleId });
  };

  // ---------- error state ----------

  if (error && !classData) {
    return (
      <ScreenLayout safeArea padded={false}>
        <Header showBack title={strings.faculty.classDetail} />
        <View style={styles.errorContainer}>
          <RefreshCw size={40} color={theme.colors.text.tertiary} style={styles.errorIcon} />
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            {error}
          </Text>
          <Button
            variant="secondary"
            size="md"
            onPress={() => loadClassDetails()}
            style={styles.retryButton}
          >
            {strings.common.retry}
          </Button>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- loading state ----------

  if (isLoading && !classData) {
    return (
      <ScreenLayout safeArea padded={false}>
        <Header showBack title={strings.faculty.classDetail} />
        <Loader fullScreen message={strings.common.loading} />
      </ScreenLayout>
    );
  }

  // Compute summary from API data
  const summary = classData
    ? {
        present: classData.present_count,
        late: classData.late_count,
        absent: classData.absent_count,
        earlyLeave: classData.early_leave_count,
      }
    : { present: 0, late: 0, absent: 0, earlyLeave: 0 };

  const students = classData?.students || [];

  // ---------- render student item ----------

  const renderStudentItem = ({ item }: { item: StudentAttendanceStatus }) => {
    const firstName = item.student_name.split(' ')[0] || '';
    const lastName = item.student_name.split(' ').slice(1).join(' ') || '';

    return (
      <Card
        onPress={() => handleStudentPress(item.student_id)}
        style={styles.studentCard}
      >
        <View style={styles.studentContent}>
          {/* Avatar */}
          <View style={styles.studentAvatar}>
            <Text variant="bodySmall" weight="600" color={theme.colors.text.primary}>
              {firstName.charAt(0).toUpperCase()}
              {lastName.charAt(0).toUpperCase()}
            </Text>
          </View>

          {/* Info */}
          <View style={styles.studentInfo}>
            <Text variant="body" weight="600" numberOfLines={1}>
              {item.student_name}
            </Text>
            <Text variant="bodySmall" color={theme.colors.text.secondary}>
              {item.student_id}
            </Text>
          </View>

          {/* Status badge */}
          <View
            style={[
              styles.statusBadge,
              {
                backgroundColor:
                  item.status === 'present'
                    ? theme.colors.status.present.bg
                    : item.status === 'late'
                    ? theme.colors.status.late.bg
                    : item.status === 'absent'
                    ? theme.colors.status.absent.bg
                    : theme.colors.status.early_leave.bg,
              },
            ]}
          >
            <Text
              variant="caption"
              weight="600"
              color={
                item.status === 'present'
                  ? theme.colors.status.present.fg
                  : item.status === 'late'
                  ? theme.colors.status.late.fg
                  : item.status === 'absent'
                  ? theme.colors.status.absent.fg
                  : theme.colors.status.early_leave.fg
              }
            >
              {item.status === 'early_leave'
                ? 'Left Early'
                : item.status.charAt(0).toUpperCase() + item.status.slice(1)}
            </Text>
          </View>
        </View>
      </Card>
    );
  };

  // ---------- header ----------

  const renderListHeader = () => (
    <>
      {/* Class info */}
      {classData && (
        <Card style={styles.classInfoCard}>
          <Text variant="h4" weight="600" style={styles.className}>
            {classData.subject_name}
          </Text>
          <Text variant="bodySmall" color={theme.colors.text.secondary}>
            {classData.subject_code}
          </Text>
          <Text
            variant="bodySmall"
            color={theme.colors.text.tertiary}
            style={styles.classTime}
          >
            {classData.start_time} - {classData.end_time}
          </Text>
        </Card>
      )}

      {/* Summary card */}
      <Card style={styles.summaryCard}>
        <Text variant="h4" weight="600" style={styles.summaryTitle}>
          {strings.faculty.attendanceSummary}
        </Text>

        <View style={styles.statsRow}>
          <StatItem
            label="Present"
            value={summary.present}
            color={theme.colors.status.present.fg}
          />
          <StatItem
            label="Late"
            value={summary.late}
            color={theme.colors.status.late.fg}
          />
          <StatItem
            label="Absent"
            value={summary.absent}
            color={theme.colors.status.absent.fg}
          />
          <StatItem
            label="Left"
            value={summary.earlyLeave}
            color={theme.colors.status.early_leave.fg}
          />
        </View>
      </Card>

      {/* Section title */}
      <Text variant="h4" weight="600" style={styles.sectionTitle}>
        Students ({students.length})
      </Text>
    </>
  );

  // ---------- empty state ----------

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Text variant="body" color={theme.colors.text.secondary} align="center">
        {strings.empty.noStudents}
      </Text>
    </View>
  );

  return (
    <ScreenLayout safeArea padded={false}>
      <Header showBack title={formatDate(date, 'MMM d, yyyy')} />

      <FlatList
        data={students}
        keyExtractor={(item) => item.student_id}
        renderItem={renderStudentItem}
        ListHeaderComponent={renderListHeader}
        ListEmptyComponent={renderEmpty}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
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

const StatItem: React.FC<{ label: string; value: number; color: string }> = ({
  label,
  value,
  color,
}) => (
  <View style={styles.statItem}>
    <Text variant="h3" weight="700" style={{ color }}>
      {value}
    </Text>
    <Text variant="caption" color={theme.colors.text.tertiary}>
      {label}
    </Text>
  </View>
);

const styles = StyleSheet.create({
  listContent: {
    paddingHorizontal: theme.spacing[4],
    paddingBottom: theme.spacing[6],
  },
  classInfoCard: {
    marginTop: theme.spacing[4],
    marginBottom: theme.spacing[3],
  },
  className: {
    marginBottom: theme.spacing[1],
  },
  classTime: {
    marginTop: theme.spacing[2],
  },
  summaryCard: {
    marginBottom: theme.spacing[4],
  },
  summaryTitle: {
    marginBottom: theme.spacing[4],
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  statItem: {
    alignItems: 'center',
  },
  sectionTitle: {
    marginBottom: theme.spacing[4],
  },
  studentCard: {
    marginBottom: theme.spacing[2],
  },
  studentContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  studentAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: theme.colors.secondary,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: theme.spacing[3],
  },
  studentInfo: {
    flex: 1,
    marginRight: theme.spacing[3],
  },
  statusBadge: {
    paddingHorizontal: theme.spacing[2],
    paddingVertical: theme.spacing[1],
    borderRadius: theme.borderRadius.full,
  },
  emptyContainer: {
    paddingVertical: theme.spacing[12],
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
