/**
 * Faculty Student Detail Screen
 *
 * Shows detailed student information and attendance history
 */

import React, { useEffect, useState } from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import { useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import { attendanceService } from '../../services';
import { theme } from '../../constants';
import { formatDate, formatPercentage } from '../../utils';
import type { FacultyStackParamList, AttendanceRecord } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Avatar, Badge, Divider, Loader } from '../../components/ui';

type StudentDetailRouteProp = RouteProp<FacultyStackParamList, 'StudentDetail'>;

export const FacultyStudentDetailScreen: React.FC = () => {
  const route = useRoute<StudentDetailRouteProp>();
  const { studentId, scheduleId } = route.params;

  const [isLoading, setIsLoading] = useState(true);
  const [recentRecords, setRecentRecords] = useState<AttendanceRecord[]>([]);

  useEffect(() => {
    loadStudentDetails();
  }, []);

  const loadStudentDetails = async () => {
    try {
      setIsLoading(true);
      // Mock data - replace with real API call
      setRecentRecords([]);
    } catch (error) {
      console.error('Failed to load student details:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title="Student Details" />
        <Loader fullScreen message="Loading..." />
      </ScreenLayout>
    );
  }

  // Mock student data
  const studentName = "John Doe";
  const overallStats = {
    totalClasses: 20,
    present: 18,
    late: 1,
    absent: 1,
    attendanceRate: 90,
  };

  return (
    <ScreenLayout safeArea scrollable>
      <Header showBack title="Student Details" />

      <View style={styles.container}>
        {/* Student header */}
        <View style={styles.studentHeader}>
          <Avatar firstName="John" lastName="Doe" size="xl" style={styles.avatar} />
          <Text variant="h2" weight="bold" align="center" style={styles.name}>
            {studentName}
          </Text>
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            {studentId}
          </Text>
        </View>

        {/* Overall stats */}
        <Card style={styles.card}>
          <Text variant="h4" weight="semibold" style={styles.cardTitle}>
            Overall Attendance
          </Text>

          <View style={styles.statsGrid}>
            <StatItem label="Total Classes" value={overallStats.totalClasses.toString()} />
            <StatItem label="Present" value={overallStats.present.toString()} color={theme.colors.status.success} />
            <StatItem label="Late" value={overallStats.late.toString()} color={theme.colors.status.warning} />
            <StatItem label="Absent" value={overallStats.absent.toString()} color={theme.colors.status.error} />
          </View>

          <View style={styles.attendanceRate}>
            <Text variant="bodySmall" color={theme.colors.text.tertiary}>
              Attendance Rate
            </Text>
            <Text variant="h3" weight="bold" color={theme.colors.status.success}>
              {formatPercentage(overallStats.attendanceRate)}
            </Text>
          </View>
        </Card>

        {/* Recent attendance */}
        <Text variant="h4" weight="semibold" style={styles.sectionTitle}>
          Recent Attendance
        </Text>

        {recentRecords.length > 0 ? (
          recentRecords.map((record) => (
            <Card key={record.id} variant="outlined" style={styles.recordCard}>
              <View style={styles.recordHeader}>
                <Text variant="body" weight="medium">
                  {formatDate(record.date, 'MMM d, yyyy')}
                </Text>
                <Badge status={record.status} size="sm" />
              </View>

              {record.presenceScore !== undefined && (
                <Text variant="bodySmall" color={theme.colors.text.secondary}>
                  Presence: {formatPercentage(record.presenceScore)}
                </Text>
              )}
            </Card>
          ))
        ) : (
          <Card variant="outlined">
            <Text variant="bodySmall" color={theme.colors.text.secondary} align="center">
              No recent records
            </Text>
          </Card>
        )}
      </View>
    </ScreenLayout>
  );
};

const StatItem: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color }) => (
  <View style={styles.statItem}>
    <Text variant="h3" weight="bold" style={color && { color }}>
      {value}
    </Text>
    <Text variant="caption" color={theme.colors.text.tertiary}>
      {label}
    </Text>
  </View>
);

const styles = StyleSheet.create({
  container: {
    padding: theme.spacing[4],
  },
  studentHeader: {
    alignItems: 'center',
    marginBottom: theme.spacing[8],
  },
  avatar: {
    marginBottom: theme.spacing[4],
  },
  name: {
    marginBottom: theme.spacing[2],
  },
  card: {
    marginBottom: theme.spacing[6],
  },
  cardTitle: {
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
  sectionTitle: {
    marginBottom: theme.spacing[4],
  },
  recordCard: {
    marginBottom: theme.spacing[3],
  },
  recordHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing[2],
  },
});
