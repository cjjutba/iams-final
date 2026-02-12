/**
 * Attendance Store - Zustand State Management
 *
 * Manages attendance records, presence logs, and early leave events.
 * Supports real-time updates via WebSocket integration.
 */

import { create } from 'zustand';
import { api, getErrorMessage } from '../utils';
import type {
  AttendanceRecord,
  AttendanceSummary,
  LiveAttendanceResponse,
  PresenceLog,
  EarlyLeaveEvent,
  ApiResponse,
} from '../types';

interface AttendanceState {
  // State
  myAttendance: AttendanceRecord[];
  todayAttendance: AttendanceRecord[];
  liveAttendance: LiveAttendanceResponse | null;
  presenceLogs: PresenceLog[];
  summary: AttendanceSummary | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchMyAttendance: (startDate?: string, endDate?: string) => Promise<void>;
  fetchTodayAttendance: (scheduleId: string) => Promise<void>;
  fetchLiveAttendance: (scheduleId: string) => Promise<void>;
  fetchPresenceLogs: (attendanceId: string) => Promise<void>;
  fetchSummary: (startDate: string, endDate: string) => Promise<void>;
  updateStudentStatus: (studentId: string, data: Partial<AttendanceRecord>) => void;
  clearError: () => void;
}

export const useAttendanceStore = create<AttendanceState>((set, get) => ({
  // Initial state
  myAttendance: [],
  todayAttendance: [],
  liveAttendance: null,
  presenceLogs: [],
  summary: null,
  isLoading: false,
  error: null,

  // Fetch student's attendance history
  fetchMyAttendance: async (startDate?: string, endDate?: string) => {
    set({ isLoading: true, error: null });

    try {
      const params: any = {};
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      const response = await api.get<ApiResponse<AttendanceRecord[]>>('/attendance/me', { params });

      if (response.data && response.data.data) {
        set({
          myAttendance: response.data.data,
          isLoading: false,
        });
      } else {
        set({ isLoading: false });
      }
    } catch (error) {
      console.error('Failed to fetch attendance:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
    }
  },

  // Fetch today's attendance for a schedule (faculty)
  fetchTodayAttendance: async (scheduleId: string) => {
    set({ isLoading: true, error: null });

    try {
      const response = await api.get<ApiResponse<AttendanceRecord[]>>('/attendance/today', {
        params: { schedule_id: scheduleId },
      });

      if (response.data && response.data.data) {
        set({
          todayAttendance: response.data.data,
          isLoading: false,
        });
      } else {
        set({ isLoading: false });
      }
    } catch (error) {
      console.error('Failed to fetch today attendance:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
    }
  },

  // Fetch live attendance for a class session (faculty)
  fetchLiveAttendance: async (scheduleId: string) => {
    set({ isLoading: true, error: null });

    try {
      const response = await api.get<ApiResponse<LiveAttendanceResponse>>(
        `/attendance/live/${scheduleId}`
      );

      if (response.data && response.data.data) {
        set({
          liveAttendance: response.data.data,
          isLoading: false,
        });
      } else {
        set({ isLoading: false });
      }
    } catch (error) {
      console.error('Failed to fetch live attendance:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
    }
  },

  // Fetch presence logs for an attendance record
  fetchPresenceLogs: async (attendanceId: string) => {
    set({ isLoading: true, error: null });

    try {
      const response = await api.get<ApiResponse<PresenceLog[]>>(
        `/attendance/${attendanceId}/logs`
      );

      if (response.data && response.data.data) {
        set({
          presenceLogs: response.data.data,
          isLoading: false,
        });
      } else {
        set({ isLoading: false });
      }
    } catch (error) {
      console.error('Failed to fetch presence logs:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
    }
  },

  // Fetch attendance summary for date range (student)
  fetchSummary: async (startDate: string, endDate: string) => {
    set({ isLoading: true, error: null });

    try {
      const response = await api.get<ApiResponse<AttendanceSummary>>('/attendance/me/summary', {
        params: { start_date: startDate, end_date: endDate },
      });

      if (response.data && response.data.data) {
        set({
          summary: response.data.data,
          isLoading: false,
        });
      } else {
        set({ isLoading: false });
      }
    } catch (error) {
      console.error('Failed to fetch summary:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
    }
  },

  // Update student status in live attendance (for real-time updates)
  updateStudentStatus: (studentId: string, data: Partial<AttendanceRecord>) => {
    const { liveAttendance } = get();

    if (!liveAttendance) return;

    // Update student in live attendance list
    const updatedStudents = liveAttendance.students.map((student) => {
      if (student.student_id === studentId) {
        return { ...student, ...data };
      }
      return student;
    });

    set({
      liveAttendance: {
        ...liveAttendance,
        students: updatedStudents,
      },
    });
  },

  // Clear error
  clearError: () => {
    set({ error: null });
  },
}));
