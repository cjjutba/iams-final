/**
 * Faculty Class Detail Screen
 *
 * Shows attendance summary and student list for a specific class session
 */

import React, { useEffect, useState } from 'react';
import { View, StyleSheet, FlatList } from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { attendanceService } from '../../services';
import { theme } from '../../constants';
import { formatDate } from '../../utils';
import type { FacultyStackParamList, LiveAttendanceStudent } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Loader } from '../../components/ui';
import { StudentCard } from '../../components/cards';

type ClassDetailRouteProp = RouteProp<FacultyStackParamList, 'ClassDetail'>;
type ClassDetailNavigationProp = StackNavigationProp<FacultyStackParamList, 'ClassDetail'>;

export const FacultyClassDetailScreen: React.FC = () => {
  const route = useRoute<ClassDetailRouteProp>();
  const navigation = useNavigation<ClassDetailNavigationProp>();

  const { scheduleId, date } = route.params;

  const [isLoading, setIsLoading] = useState(true);
  const [students, setStudents] = useState<LiveAttendanceStudent[]>([]);
  const [summary, setSummary] = useState({ present: 0, late: 0, absent: 0, earlyLeave: 0 });

  useEffect(() => {
    loadClassDetails();
  }, []);

  const loadClassDetails = async () => {
    try {
      setIsLoading(true);
      const data = await attendanceService.getLiveAttendance(scheduleId);
      setStudents(data.students);

      const stats = {
        present: data.students.filter((s) => s.status === 'present').length,
        late: data.students.filter((s) => s.status === 'late').length,
        absent: data.students.filter((s) => s.status === 'absent').length,
        earlyLeave: data.students.filter((s) => s.status === 'early_leave').length,
      };
      setSummary(stats);
    } catch (error) {
      console.error('Failed to load class details:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStudentPress = (studentId: string) => {
    navigation.navigate('StudentDetail', { studentId, scheduleId });
  };

  if (isLoading) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title="Class Details" />
        <Loader fullScreen message="Loading..." />
      </ScreenLayout>
    );
  }

  return (
    <ScreenLayout safeArea padded={false}>
      <Header showBack title={formatDate(date, 'MMM d, yyyy')} />

      {/* Summary card */}
      <Card style={styles.summaryCard}>
        <Text variant="h4" weight="semibold" style={styles.summaryTitle}>
          Attendance Summary
        </Text>

        <View style={styles.statsRow}>
          <StatItem label="Present" value={summary.present} color={theme.colors.status.success} />
          <StatItem label="Late" value={summary.late} color={theme.colors.status.warning} />
          <StatItem label="Absent" value={summary.absent} color={theme.colors.status.error} />
          <StatItem label="Left" value={summary.earlyLeave} color={theme.colors.status.warning} />
        </View>
      </Card>

      {/* Students list */}
      <Text variant="h4" weight="semibold" style={styles.sectionTitle}>
        Students
      </Text>

      <FlatList
        data={students}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <StudentCard student={item} onPress={() => handleStudentPress(item.studentId)} />
        )}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
      />
    </ScreenLayout>
  );
};

const StatItem: React.FC<{ label: string; value: number; color: string }> = ({ label, value, color }) => (
  <View style={styles.statItem}>
    <Text variant="h3" weight="bold" style={[{ color }]}>
      {value}
    </Text>
    <Text variant="caption" color={theme.colors.text.tertiary}>
      {label}
    </Text>
  </View>
);

const styles = StyleSheet.create({
  summaryCard: {
    margin: theme.spacing[4],
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
    paddingHorizontal: theme.spacing[4],
    marginBottom: theme.spacing[4],
  },
  listContent: {
    paddingHorizontal: theme.spacing[4],
    paddingBottom: theme.spacing[6],
  },
});
