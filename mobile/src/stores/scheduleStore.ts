/**
 * Schedule Store - Zustand State Management
 *
 * Manages class schedules for both students and faculty.
 * Fetches schedules from backend and provides filtering/sorting.
 */

import { create } from 'zustand';
import { api, getErrorMessage } from '../utils';
import type { Schedule, ScheduleWithAttendance, ApiResponse } from '../types';

interface ScheduleState {
  // State
  schedules: Schedule[];
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchMySchedules: () => Promise<void>;
  getSchedulesByDay: (dayOfWeek: number) => Schedule[];
  getTodaySchedules: () => Schedule[];
  getCurrentClass: () => Schedule | null;
  clearError: () => void;
}

export const useScheduleStore = create<ScheduleState>((set, get) => ({
  // Initial state
  schedules: [],
  isLoading: false,
  error: null,

  // Fetch user's schedules (student or faculty)
  fetchMySchedules: async () => {
    set({ isLoading: true, error: null });

    try {
      const response = await api.get<ApiResponse<Schedule[]>>('/schedules/me');

      if (response.data && response.data.data) {
        set({
          schedules: response.data.data,
          isLoading: false,
        });
      } else {
        set({ isLoading: false });
      }
    } catch (error) {
      console.error('Failed to fetch schedules:', error);
      set({
        error: getErrorMessage(error),
        isLoading: false,
      });
    }
  },

  // Get schedules for specific day
  getSchedulesByDay: (dayOfWeek: number): Schedule[] => {
    const { schedules } = get();
    return schedules.filter((s) => s.day_of_week === dayOfWeek && s.is_active);
  },

  // Get today's schedules
  getTodaySchedules: (): Schedule[] => {
    const { schedules, getSchedulesByDay } = get();
    const today = new Date().getDay(); // 0=Sunday, 1=Monday, etc.
    // Convert to our format (0=Monday)
    const dayOfWeek = today === 0 ? 6 : today - 1;
    return getSchedulesByDay(dayOfWeek);
  },

  // Get current/ongoing class
  getCurrentClass: (): Schedule | null => {
    const { getTodaySchedules } = get();
    const todaySchedules = getTodaySchedules();

    const now = new Date();
    const currentTime = `${now.getHours().toString().padStart(2, '0')}:${now
      .getMinutes()
      .toString()
      .padStart(2, '0')}:00`;

    // Find class that's currently ongoing
    for (const schedule of todaySchedules) {
      if (currentTime >= schedule.start_time && currentTime <= schedule.end_time) {
        return schedule;
      }
    }

    return null;
  },

  // Clear error
  clearError: () => {
    set({ error: null });
  },
}));
