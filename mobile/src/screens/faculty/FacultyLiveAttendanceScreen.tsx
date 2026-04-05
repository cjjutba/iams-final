/**
 * Faculty Live Attendance Screen
 *
 * Real-time attendance monitoring with WebSocket updates.
 * Shows all students with detection status, search filtering,
 * stats bar with correct counts, and handles WebSocket
 * disconnect/reconnect gracefully.
 *
 * Features:
 * - Session active indicator bar
 * - "View Camera Feed" button in header
 * - "End Session" fixed bar at bottom when session is active
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  TextInput,
  RefreshControl,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { Search, Edit, RefreshCw, Wifi, WifiOff, Camera, Square } from 'lucide-react-native';
import { useAttendance, useWebSocket, useSession } from '../../hooks';
import { useToast } from '../../hooks/useToast';
import { theme, strings } from '../../constants';
import { getErrorMessage } from '../../utils';
import type {
  FacultyStackParamList,
  WebSocketMessage,
  StudentAttendanceStatus,
} from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Button, Skeleton } from '../../components/ui';

type LiveAttendanceRouteProp = RouteProp<FacultyStackParamList, 'LiveAttendance'>;
type LiveAttendanceNavigationProp = StackNavigationProp<FacultyStackParamList, 'LiveAttendance'>;

export const FacultyLiveAttendanceScreen: React.FC = () => {
  const route = useRoute<LiveAttendanceRouteProp>();
  const navigation = useNavigation<LiveAttendanceNavigationProp>();

  const { scheduleId } = route.params;
  const { showError, showSuccess } = useToast();

  const {
    liveAttendance,
    isLoading,
    error,
    fetchLiveAttendance,
    updateStudentStatus,
  } = useAttendance();

  const {
    isSessionActive,
    endSession,
    isLoading: isSessionLoading,
  } = useSession();

  const [searchQuery, setSearchQuery] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isEndingSession, setIsEndingSession] = useState(false);

  const sessionActive = isSessionActive(scheduleId);

  // WebSocket integration for real-time updates
  const { isConnected } = useWebSocket({
    onAttendanceUpdate: (message: WebSocketMessage) => {
      if (message.data?.schedule_id === scheduleId) {
        updateStudentStatus(message.data.student_id, message.data);
      }
    },
    onEarlyLeave: (message: WebSocketMessage) => {
      if (message.data?.schedule_id === scheduleId) {
        // Refresh live data to get updated status
        fetchLiveAttendance(scheduleId);
      }
    },
  });

  useEffect(() => {
    if (error) showError(error, 'Load Failed');
  }, [error]);

  useEffect(() => {
    fetchLiveAttendance(scheduleId);

    // Refresh every 30 seconds as fallback
    const interval = setInterval(() => {
      fetchLiveAttendance(scheduleId);
    }, 30000);

    return () => clearInterval(interval);
  }, [scheduleId]);

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    fetchLiveAttendance(scheduleId).finally(() => setIsRefreshing(false));
  }, [scheduleId, fetchLiveAttendance]);

  const handleManualEntry = () => {
    navigation.navigate('ManualEntry', { scheduleId });
  };

  const handleViewCameraFeed = () => {
    (navigation as any).navigate('LiveFeed', {
      scheduleId,
      roomId: '',
      subjectName: route.params.subjectName || '',
    });
  };

  const handleEndSession = () => {
    Alert.alert(
      'End Session',
      'Are you sure you want to end this attendance session? This action cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'End Session',
          style: 'destructive',
          onPress: async () => {
            setIsEndingSession(true);
            try {
              const result = await endSession(scheduleId);
              if (result) {
                showSuccess('Session ended successfully');
              } else {
                showError('Failed to end session');
              }
            } catch (err) {
              showError(getErrorMessage(err));
            } finally {
              setIsEndingSession(false);
            }
          },
        },
      ],
    );
  };

  const handleStudentPress = (studentId: string) => {
    navigation.navigate('StudentDetail', { studentId, scheduleId });
  };

  // Filter students by search
  const students = liveAttendance?.students || [];
  const filteredStudents = students.filter(
    (student) =>
      student.student_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      student.student_id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Compute stats from API response fields or calculate from students
  const stats = liveAttendance
    ? {
        present: liveAttendance.present_count,
        late: liveAttendance.late_count,
        absent: liveAttendance.absent_count,
        earlyLeave: liveAttendance.early_leave_count,
      }
    : { present: 0, late: 0, absent: 0, earlyLeave: 0 };

  // ---------- error state ----------

  if (error && !liveAttendance) {
    return (
      <ScreenLayout safeArea padded={false}>
        <Header showBack title="Live Attendance" />
        <View style={styles.errorContainer}>
          <RefreshCw size={40} color={theme.colors.text.tertiary} style={styles.errorIcon} />
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            Unable to load live attendance. Please try again.
          </Text>
          <Button
            variant="secondary"
            size="md"
            onPress={() => fetchLiveAttendance(scheduleId)}
            style={styles.retryButton}
          >
            {strings.common.retry}
          </Button>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- loading state ----------

  if (isLoading && !liveAttendance) {
    return (
      <ScreenLayout safeArea padded={false}>
        <Header showBack title="Live Attendance" />
        <View style={styles.container}>
          {/* Stats row skeleton */}
          <View style={styles.statsRow}>
            {[1, 2, 3, 4].map((i) => (
              <View key={i} style={{ flex: 1, borderWidth: 1, borderColor: '#E5E5E5', borderRadius: 12, padding: 12, alignItems: 'center' }}>
                <Skeleton width={30} height={24} />
                <View style={{ height: 4 }} />
                <Skeleton width={40} height={10} />
              </View>
            ))}
          </View>

          {/* Search skeleton */}
          <View style={{ marginHorizontal: theme.spacing[4], marginBottom: theme.spacing[4] }}>
            <Skeleton width="100%" height={44} borderRadius={theme.borderRadius.md} />
          </View>

          {/* Student cards skeleton */}
          <View style={{ paddingHorizontal: theme.spacing[4] }}>
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <View key={i} style={{ borderWidth: 1, borderColor: '#E5E5E5', borderRadius: 12, padding: 12, marginBottom: 8 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <Skeleton width={40} height={40} borderRadius={20} style={{ marginRight: 12 }} />
                  <View style={{ flex: 1 }}>
                    <Skeleton width="55%" height={14} />
                    <View style={{ height: 4 }} />
                    <Skeleton width="35%" height={12} />
                  </View>
                  <Skeleton width={56} height={24} borderRadius={12} />
                </View>
              </View>
            ))}
          </View>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- render student card inline ----------

  const renderStudentItem = ({ item }: { item: StudentAttendanceStatus }) => {
    const isCurrentlyDetected = item.currently_detected === true;
    const firstName = item.student_name.split(' ')[0] || '';
    const lastName = item.student_name.split(' ').slice(1).join(' ') || '';

    return (
      <Card
        onPress={() => handleStudentPress(item.student_id)}
        style={styles.studentCard}
      >
        <View style={styles.studentContent}>
          {/* Avatar with initials */}
          <View style={styles.studentAvatar}>
            <Text variant="bodySmall" weight="600" color={theme.colors.text.primary}>
              {firstName.charAt(0).toUpperCase()}
              {lastName.charAt(0).toUpperCase()}
            </Text>
          </View>

          {/* Info */}
          <View style={styles.studentInfo}>
            <View style={styles.nameRow}>
              <Text variant="body" weight="600" numberOfLines={1} style={styles.studentName}>
                {item.student_name}
              </Text>
              {isCurrentlyDetected && <View style={styles.detectionDot} />}
            </View>

            <Text variant="bodySmall" color={theme.colors.text.secondary}>
              {item.student_number || item.student_id}
            </Text>

            {item.presence_score !== undefined && (
              <Text variant="caption" color={theme.colors.text.tertiary}>
                Presence: {item.presence_score.toFixed(0)}%
              </Text>
            )}
          </View>

          {/* Status */}
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
                ? 'Left'
                : item.status.charAt(0).toUpperCase() + item.status.slice(1)}
            </Text>
          </View>
        </View>
      </Card>
    );
  };

  // ---------- empty state ----------

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Text variant="body" color={theme.colors.text.secondary} align="center">
        {searchQuery ? 'No students match your search' : strings.empty.noStudents}
      </Text>
    </View>
  );

  return (
    <ScreenLayout safeArea padded={false}>
      <Header
        showBack
        title="Live Attendance"
        rightAction={
          <View style={styles.headerActions}>
            <TouchableOpacity
              onPress={handleViewCameraFeed}
              activeOpacity={theme.interaction.activeOpacity}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            >
              <Camera size={24} color={theme.colors.primary} />
            </TouchableOpacity>
            <TouchableOpacity
              onPress={handleManualEntry}
              activeOpacity={theme.interaction.activeOpacity}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              style={styles.headerActionSpacing}
            >
              <Edit size={24} color={theme.colors.primary} />
            </TouchableOpacity>
          </View>
        }
      />

      <View style={styles.container}>
        {/* Connection status indicator */}
        <View style={styles.connectionBar}>
          {isConnected ? (
            <Wifi size={14} color={theme.colors.status.present.fg} />
          ) : (
            <WifiOff size={14} color={theme.colors.status.absent.fg} />
          )}
          <Text
            variant="caption"
            color={
              isConnected
                ? theme.colors.status.present.fg
                : theme.colors.status.absent.fg
            }
            style={styles.connectionText}
          >
            {isConnected ? 'Live' : 'Reconnecting...'}
          </Text>
        </View>

        {/* Session active indicator bar */}
        {sessionActive && (
          <View style={styles.sessionBar}>
            <View style={styles.sessionDot} />
            <Text variant="caption" weight="600" color="#FFFFFF">
              Session Active
            </Text>
          </View>
        )}

        {/* Stats row */}
        <View style={styles.statsRow}>
          <StatCard
            label="Present"
            value={stats.present}
            color={theme.colors.status.present.fg}
          />
          <StatCard
            label="Late"
            value={stats.late}
            color={theme.colors.status.late.fg}
          />
          <StatCard
            label="Absent"
            value={stats.absent}
            color={theme.colors.status.absent.fg}
          />
          <StatCard
            label="Left"
            value={stats.earlyLeave}
            color={theme.colors.status.early_leave.fg}
          />
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
          keyExtractor={(item) => item.student_id}
          renderItem={renderStudentItem}
          ListEmptyComponent={renderEmpty}
          contentContainerStyle={[
            styles.listContent,
            filteredStudents.length === 0 && styles.listContentEmpty,
            sessionActive && styles.listContentWithEndSession,
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
      </View>

      {/* End Session fixed bar at bottom */}
      {sessionActive && (
        <View style={styles.endSessionBar}>
          <TouchableOpacity
            style={styles.endSessionButton}
            onPress={handleEndSession}
            activeOpacity={theme.interaction.activeOpacity}
            disabled={isEndingSession || isSessionLoading}
          >
            {isEndingSession ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <Square size={18} color="#FFFFFF" />
            )}
            <Text variant="body" weight="700" color="#FFFFFF" style={styles.endSessionText}>
              {isEndingSession ? 'Ending Session...' : 'End Session'}
            </Text>
          </TouchableOpacity>
        </View>
      )}
    </ScreenLayout>
  );
};

// StatCard component
const StatCard: React.FC<{ label: string; value: number; color: string }> = ({
  label,
  value,
  color,
}) => (
  <Card variant="outlined" style={styles.statCard}>
    <Text variant="h2" weight="700" style={[styles.statValue, { color }]}>
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
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  headerActionSpacing: {
    marginLeft: theme.spacing[4],
  },
  connectionBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: theme.spacing[1],
    backgroundColor: theme.colors.secondary,
  },
  connectionText: {
    marginLeft: theme.spacing[1],
  },
  sessionBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: theme.spacing[2],
    backgroundColor: theme.colors.success,
  },
  sessionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#FFFFFF',
    marginRight: theme.spacing[2],
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
    backgroundColor: theme.colors.inputBackground,
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
  listContentEmpty: {
    flexGrow: 1,
  },
  listContentWithEndSession: {
    paddingBottom: 80,
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
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: theme.spacing[1],
  },
  studentName: {
    flex: 1,
  },
  detectionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: theme.colors.status.present.fg,
    marginLeft: theme.spacing[2],
  },
  statusBadge: {
    paddingHorizontal: theme.spacing[2],
    paddingVertical: theme.spacing[1],
    borderRadius: theme.borderRadius.full,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
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
  endSessionBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingHorizontal: theme.spacing[4],
    paddingVertical: theme.spacing[3],
    backgroundColor: theme.colors.background,
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
  },
  endSessionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.colors.error,
    paddingVertical: theme.spacing[4],
    borderRadius: theme.borderRadius.md,
  },
  endSessionText: {
    marginLeft: theme.spacing[2],
  },
});
