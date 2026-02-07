/**
 * Faculty Reports Screen
 *
 * Generate and view attendance reports. Uses real schedules
 * fetched from the API for class selection. Report generation
 * fetches real attendance summary stats. Export options
 * show a "coming soon" notice until file sharing is implemented.
 */

import React, { useEffect, useState, useCallback } from 'react';
import { View, StyleSheet, Alert, ActivityIndicator, ScrollView } from 'react-native';
import { useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import { useForm } from 'react-hook-form';
import { Download, BarChart3, RefreshCw } from 'lucide-react-native';
import { api } from '../../utils/api';
import { useSchedule } from '../../hooks';
import { attendanceService } from '../../services';
import { theme, strings } from '../../constants';
import { formatPercentage, getErrorMessage } from '../../utils';
import type {
  FacultyStackParamList,
  AttendanceSummary,
  ApiResponse,
  Schedule,
} from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Button, Card } from '../../components/ui';
import { FormSelect } from '../../components/forms';

type ReportsRouteProp = RouteProp<FacultyStackParamList, 'Reports'>;

const REPORT_TYPE_OPTIONS = [
  { label: 'Summary Report', value: 'summary' },
  { label: 'Detailed Report', value: 'detailed' },
];

interface ReportFormData {
  classId: string;
  reportType: string;
}

export const FacultyReportsScreen: React.FC = () => {
  const route = useRoute<ReportsRouteProp>();
  const initialScheduleId = route.params?.scheduleId || '';

  const { schedules, isLoading: schedulesLoading, fetchMySchedules } = useSchedule();

  const [isGenerating, setIsGenerating] = useState(false);
  const [reportSummary, setReportSummary] = useState<AttendanceSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Build class options from real schedules
  const classOptions = schedules.map((s: Schedule) => ({
    label: `${s.subject_code} - ${s.subject_name}`,
    value: s.id,
  }));

  const { control, handleSubmit, watch } = useForm<ReportFormData>({
    defaultValues: {
      classId: initialScheduleId,
      reportType: 'summary',
    },
  });

  const selectedClassId = watch('classId');

  // Fetch schedules on mount if not loaded
  useEffect(() => {
    if (schedules.length === 0 && !schedulesLoading) {
      fetchMySchedules();
    }
  }, []);

  // ---------- generate report ----------

  const onGenerate = async (data: ReportFormData) => {
    if (!data.classId) {
      Alert.alert('Selection Required', 'Please select a class first.');
      return;
    }

    setIsGenerating(true);
    setError(null);
    setReportSummary(null);

    try {
      const response = await api.get<ApiResponse<AttendanceSummary>>(
        '/attendance/summary',
        {
          params: {
            schedule_id: data.classId,
          },
        }
      );

      if (response.data?.data) {
        setReportSummary(response.data.data);
      } else {
        setReportSummary({
          total: 0,
          present: 0,
          late: 0,
          absent: 0,
          early_leave: 0,
          attendance_rate: 0,
          start_date: '',
          end_date: '',
        });
      }
    } catch (err) {
      setError(getErrorMessage(err));
      Alert.alert('Error', getErrorMessage(err));
    } finally {
      setIsGenerating(false);
    }
  };

  // ---------- export handlers ----------

  const handleExportCSV = () => {
    Alert.alert(
      'Export CSV',
      'CSV export will be available in a future update. The attendance data shown above reflects real-time records from the system.'
    );
  };

  const handleExportPDF = () => {
    Alert.alert(
      'Export PDF',
      'PDF export will be available in a future update. The attendance data shown above reflects real-time records from the system.'
    );
  };

  // Find selected class name
  const selectedClass = schedules.find((s: Schedule) => s.id === selectedClassId);
  const selectedClassName = selectedClass
    ? `${selectedClass.subject_code} - ${selectedClass.subject_name}`
    : '';

  return (
    <ScreenLayout safeArea padded={false}>
      <Header showBack title={strings.faculty.reports} />

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.container}>
          {/* Generate report card */}
          <Card>
            <Text variant="h4" weight="600" style={styles.cardTitle}>
              Generate Report
            </Text>

            {schedulesLoading ? (
              <View style={styles.loadingClasses}>
                <ActivityIndicator size="small" color={theme.colors.primary} />
                <Text
                  variant="bodySmall"
                  color={theme.colors.text.secondary}
                  style={styles.loadingText}
                >
                  Loading classes...
                </Text>
              </View>
            ) : (
              <FormSelect
                name="classId"
                control={control}
                label="Select Class"
                options={classOptions}
                placeholder={
                  classOptions.length === 0
                    ? 'No classes available'
                    : 'Choose a class'
                }
              />
            )}

            <FormSelect
              name="reportType"
              control={control}
              label="Report Type"
              options={REPORT_TYPE_OPTIONS}
              placeholder="Select report type"
            />

            <Button
              variant="primary"
              size="lg"
              fullWidth
              onPress={handleSubmit(onGenerate)}
              loading={isGenerating}
              disabled={classOptions.length === 0}
              style={styles.generateButton}
            >
              {strings.faculty.generateReport}
            </Button>
          </Card>

          {/* Report results */}
          {reportSummary && (
            <Card style={styles.resultsCard}>
              <View style={styles.resultsHeader}>
                <BarChart3 size={24} color={theme.colors.primary} />
                <Text variant="h4" weight="600" style={styles.resultsTitle}>
                  Report Results
                </Text>
              </View>

              {selectedClassName ? (
                <Text
                  variant="bodySmall"
                  color={theme.colors.text.secondary}
                  style={styles.resultsSubtitle}
                >
                  {selectedClassName}
                </Text>
              ) : null}

              <View style={styles.statsGrid}>
                <StatItem
                  label="Total Sessions"
                  value={reportSummary.total.toString()}
                />
                <StatItem
                  label="Present"
                  value={reportSummary.present.toString()}
                  color={theme.colors.status.present.fg}
                />
                <StatItem
                  label="Late"
                  value={reportSummary.late.toString()}
                  color={theme.colors.status.late.fg}
                />
                <StatItem
                  label="Absent"
                  value={reportSummary.absent.toString()}
                  color={theme.colors.status.absent.fg}
                />
              </View>

              <View style={styles.attendanceRate}>
                <Text variant="bodySmall" color={theme.colors.text.tertiary}>
                  Overall Attendance Rate
                </Text>
                <Text
                  variant="h2"
                  weight="700"
                  color={
                    reportSummary.attendance_rate >= 80
                      ? theme.colors.status.present.fg
                      : reportSummary.attendance_rate >= 60
                      ? theme.colors.status.late.fg
                      : theme.colors.status.absent.fg
                  }
                >
                  {formatPercentage(reportSummary.attendance_rate)}
                </Text>
              </View>

              {reportSummary.start_date && reportSummary.end_date && (
                <Text
                  variant="caption"
                  color={theme.colors.text.tertiary}
                  align="center"
                  style={styles.dateRange}
                >
                  {reportSummary.start_date} to {reportSummary.end_date}
                </Text>
              )}
            </Card>
          )}

          {/* Export options */}
          <Card style={styles.exportCard}>
            <Text variant="h4" weight="600" style={styles.cardTitle}>
              Export Options
            </Text>

            <Button
              variant="outline"
              size="md"
              fullWidth
              onPress={handleExportCSV}
              leftIcon={<Download size={20} color={theme.colors.primary} />}
              style={styles.exportButton}
            >
              {strings.faculty.exportCsv}
            </Button>

            <Button
              variant="outline"
              size="md"
              fullWidth
              onPress={handleExportPDF}
              leftIcon={<Download size={20} color={theme.colors.primary} />}
            >
              {strings.faculty.exportPdf}
            </Button>
          </Card>
        </View>
      </ScrollView>
    </ScreenLayout>
  );
};

const StatItem: React.FC<{ label: string; value: string; color?: string }> = ({
  label,
  value,
  color,
}) => (
  <View style={styles.statItem}>
    <Text variant="h3" weight="700" style={color ? { color } : undefined}>
      {value}
    </Text>
    <Text variant="caption" color={theme.colors.text.tertiary}>
      {label}
    </Text>
  </View>
);

const styles = StyleSheet.create({
  scrollContent: {
    flexGrow: 1,
  },
  container: {
    padding: theme.spacing[4],
    paddingBottom: theme.spacing[8],
  },
  cardTitle: {
    marginBottom: theme.spacing[4],
  },
  loadingClasses: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: theme.spacing[4],
  },
  loadingText: {
    marginLeft: theme.spacing[3],
  },
  generateButton: {
    marginTop: theme.spacing[4],
  },
  resultsCard: {
    marginTop: theme.spacing[4],
  },
  resultsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: theme.spacing[2],
  },
  resultsTitle: {
    marginLeft: theme.spacing[3],
  },
  resultsSubtitle: {
    marginBottom: theme.spacing[4],
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-around',
    marginBottom: theme.spacing[4],
  },
  statItem: {
    alignItems: 'center',
    width: '45%',
    marginBottom: theme.spacing[4],
  },
  attendanceRate: {
    alignItems: 'center',
    paddingTop: theme.spacing[4],
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
  },
  dateRange: {
    marginTop: theme.spacing[3],
  },
  exportCard: {
    marginTop: theme.spacing[4],
  },
  exportButton: {
    marginBottom: theme.spacing[3],
  },
});
