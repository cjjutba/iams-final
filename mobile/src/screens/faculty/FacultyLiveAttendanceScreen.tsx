/**
 * Faculty Live Attendance Screen
 *
 * Real-time attendance monitoring with WebSocket updates
 * Shows all students with detection status
 * Includes search and manual entry
 */

import React, { useEffect, useState } from 'react';
import { View, StyleSheet, FlatList, TextInput } from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { Search, Edit } from 'lucide-react-native';
import { useAttendance, useWebSocket } from '../../hooks';
import { theme, strings } from '../../constants';
import type { FacultyStackParamList, WebSocketMessage } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card } from '../../components/ui';
import { StudentCard } from '../../components/cards';

type LiveAttendanceRouteProp = RouteProp<FacultyStackParamList, 'LiveAttendance'>;
type LiveAttendanceNavigationProp = StackNavigationProp<FacultyStackParamList, 'LiveAttendance'>;

export const FacultyLiveAttendanceScreen: React.FC = () => {
  const route = useRoute<LiveAttendanceRouteProp>();
  const navigation = useNavigation<LiveAttendanceNavigationProp>();

  const { scheduleId } = route.params;

  const { liveAttendance, fetchLiveAttendance, updateStudentStatus } = useAttendance();
  const [searchQuery, setSearchQuery] = useState('');

  // WebSocket integration for real-time updates
  useWebSocket({
    onAttendanceUpdate: (message: WebSocketMessage) => {
      if (message.data.scheduleId === scheduleId) {
        updateStudentStatus(message.data.studentId, message.data.status);
      }
    },
    onEarlyLeave: (message: WebSocketMessage) => {
      console.log('Early leave detected:', message);
    },
  });

  useEffect(() => {
    fetchLiveAttendance(scheduleId);

    // Refresh every 30 seconds
    const interval = setInterval(() => {
      fetchLiveAttendance(scheduleId);
    }, 30000);

    return () => clearInterval(interval);
  }, [scheduleId]);

  const handleManualEntry = () => {
    navigation.navigate('ManualEntry', { scheduleId });
  };

  const handleStudentPress = (studentId: string) => {
    navigation.navigate('StudentDetail', { studentId, scheduleId });
  };

  const filteredStudents = liveAttendance?.students.filter((student) =>
    student.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    student.studentId.toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

  const stats = liveAttendance ? {
    present: liveAttendance.students.filter((s) => s.status === 'present').length,
    late: liveAttendance.students.filter((s) => s.status === 'late').length,
    absent: liveAttendance.students.filter((s) => s.status === 'absent').length,
    earlyLeave: liveAttendance.students.filter((s) => s.status === 'early_leave').length,
  } : { present: 0, late: 0, absent: 0, earlyLeave: 0 };

  return (
    <ScreenLayout safeArea padded={false}>
      <Header
        showBack
        title="Live Attendance"
        rightAction={
          <Edit
            size={24}
            color={theme.colors.primary}
            onPress={handleManualEntry}
          />
        }
      />

      <View style={styles.container}>
        {/* Stats row */}
        <View style={styles.statsRow}>
          <StatCard label="Present" value={stats.present} color={theme.colors.status.success} />
          <StatCard label="Late" value={stats.late} color={theme.colors.status.warning} />
          <StatCard label="Absent" value={stats.absent} color={theme.colors.status.error} />
          <StatCard label="Left" value={stats.earlyLeave} color={theme.colors.status.warning} />
        </View>

        {/* Search */}
        <View style={styles.searchContainer}>
          <Search size={20} color={theme.colors.text.tertiary} style={styles.searchIcon} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search students..."
            placeholderTextColor={theme.colors.text.tertiary}
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
        </View>

        {/* Students list */}
        <FlatList
          data={filteredStudents}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <StudentCard student={item} onPress={() => handleStudentPress(item.studentId)} />
          )}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
        />
      </View>
    </ScreenLayout>
  );
};

// StatCard component
const StatCard: React.FC<{ label: string; value: number; color: string }> = ({ label, value, color }) => (
  <Card variant="outlined" style={styles.statCard}>
    <Text variant="h2" weight="bold" style={[styles.statValue, { color }]}>
      {value}
    </Text>
    <Text variant="caption" color={theme.colors.text.tertiary}>
      {label}
    </Text>
  </Card>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  statsRow: {
    flexDirection: 'row',
    paddingHorizontal: theme.spacing[4],
    paddingTop: theme.spacing[4],
    paddingBottom: theme.spacing[3],
    gap: theme.spacing[2],
  },
  statCard: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: theme.spacing[3],
  },
  statValue: {
    marginBottom: theme.spacing[1],
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.backgroundSecondary,
    marginHorizontal: theme.spacing[4],
    marginBottom: theme.spacing[4],
    paddingHorizontal: theme.spacing[4],
    borderRadius: theme.borderRadius.md,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  searchIcon: {
    marginRight: theme.spacing[2],
  },
  searchInput: {
    flex: 1,
    paddingVertical: theme.spacing[3],
    fontSize: 16,
    color: theme.colors.text.primary,
  },
  listContent: {
    paddingHorizontal: theme.spacing[4],
    paddingBottom: theme.spacing[6],
  },
});
