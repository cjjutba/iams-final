/**
 * useAttendance Hook
 *
 * Provides access to attendance state and actions.
 * Wraps attendanceStore for convenient component usage.
 */

import { useAttendanceStore } from '../stores';

export const useAttendance = () => {
  const {
    myAttendance,
    todayAttendance,
    liveAttendance,
    presenceLogs,
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
    myAttendance,
    todayAttendance,
    liveAttendance,
    presenceLogs,
    summary,
    isLoading,
    error,

    // Alias for backward compat: screens reference "history"
    history: myAttendance,

    // Actions
    fetchMyAttendance,
    fetchTodayAttendance,
    fetchLiveAttendance,
    fetchPresenceLogs,
    fetchSummary,
    updateStudentStatus,
    clearError,

    // Computed
    hasAttendanceToday: todayAttendance.length > 0,
    totalRecords: myAttendance.length,
  };
};
