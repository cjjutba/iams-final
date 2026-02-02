/**
 * useAttendance Hook
 *
 * Provides access to attendance state and actions.
 * Wraps attendanceStore for convenient component usage.
 */

import { useAttendanceStore } from '../stores';

export const useAttendance = () => {
  const {
    todayAttendance,
    history,
    liveAttendance,
    summary,
    isLoading,
    error,
    fetchMyAttendance,
    fetchTodayAttendance,
    fetchLiveAttendance,
    fetchPresenceLogs,
    fetchSummary,
    updateStudentStatus,
    clearError,
  } = useAttendanceStore();

  return {
    // State
    todayAttendance,
    history,
    liveAttendance,
    summary,
    isLoading,
    error,

    // Actions
    fetchMyAttendance,
    fetchTodayAttendance,
    fetchLiveAttendance,
    fetchPresenceLogs,
    fetchSummary,
    updateStudentStatus,
    clearError,

    // Computed
    hasAttendanceToday: todayAttendance !== null,
    totalRecords: history.length,
  };
};
