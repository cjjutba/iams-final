/**
 * useSchedule Hook
 *
 * Provides access to schedule data with helpful utilities.
 * Manages schedule fetching and filtering.
 *
 * Day-of-week convention:
 *   - JavaScript Date.getDay(): 0=Sunday, 1=Monday, ..., 6=Saturday
 *   - Backend / Schedule type:  0=Monday, 1=Tuesday, ..., 6=Sunday
 *
 * This hook accepts JS day values and converts internally so screens
 * do not need to worry about the backend convention.
 */

import { useEffect, useMemo, useCallback } from 'react';
import { useScheduleStore } from '../stores';
import type { Schedule, ScheduleWithAttendance } from '../types';

/**
 * Convert JavaScript Date.getDay() (0=Sunday) to backend day_of_week (0=Monday).
 */
const jsDayToBackendDay = (jsDay: number): number => {
  return jsDay === 0 ? 6 : jsDay - 1;
};

export const useSchedule = (autoFetch = true) => {
  const { schedules, isLoading, error, fetchMySchedules, clearError } = useScheduleStore();

  // Auto-fetch schedules on mount
  useEffect(() => {
    if (autoFetch && schedules.length === 0 && !isLoading) {
      fetchMySchedules();
    }
  }, [autoFetch]);

  // Get current JS day (0=Sunday, 6=Saturday)
  const currentJsDay = useMemo(() => new Date().getDay(), []);

  /**
   * Filter schedules by day.
   * Accepts a JS-style day (0=Sunday) as that is what screens pass from Date.getDay().
   * Converts to backend format internally.
   */
  const getSchedulesByDay = useCallback(
    (jsDayOfWeek: number): Schedule[] => {
      const backendDay = jsDayToBackendDay(jsDayOfWeek);
      return schedules.filter(
        (schedule) => schedule.day_of_week === backendDay && schedule.is_active
      );
    },
    [schedules]
  );

  // Get today's schedules (already converted)
  const todaySchedules = useMemo(() => {
    return getSchedulesByDay(currentJsDay);
  }, [schedules, currentJsDay, getSchedulesByDay]);

  /**
   * Get the currently ongoing class based on system time.
   * Compares HH:MM against schedule start_time / end_time (HH:MM:SS).
   */
  const getCurrentClass = useCallback((): Schedule | null => {
    const now = new Date();
    const currentMinutes = now.getHours() * 60 + now.getMinutes();

    for (const schedule of todaySchedules) {
      const [startHour, startMin] = schedule.start_time.split(':').map(Number);
      const [endHour, endMin] = schedule.end_time.split(':').map(Number);

      const startMinutes = startHour * 60 + startMin;
      const endMinutes = endHour * 60 + endMin;

      if (currentMinutes >= startMinutes && currentMinutes <= endMinutes) {
        return schedule;
      }
    }

    return null;
  }, [todaySchedules]);

  /**
   * Get the next upcoming class today (after current time).
   */
  const getNextClass = useCallback((): Schedule | null => {
    const now = new Date();
    const currentMinutes = now.getHours() * 60 + now.getMinutes();

    const upcomingClasses = todaySchedules.filter((schedule) => {
      const [startHour, startMin] = schedule.start_time.split(':').map(Number);
      const startMinutes = startHour * 60 + startMin;
      return currentMinutes < startMinutes;
    });

    if (upcomingClasses.length === 0) return null;

    // Return the earliest upcoming class
    return upcomingClasses.reduce((earliest, current) => {
      const [eHour, eMin] = earliest.start_time.split(':').map(Number);
      const [cHour, cMin] = current.start_time.split(':').map(Number);

      const eMinutes = eHour * 60 + eMin;
      const cMinutes = cHour * 60 + cMin;

      return cMinutes < eMinutes ? current : earliest;
    });
  }, [todaySchedules]);

  return {
    // State
    schedules,
    todaySchedules,
    isLoading,
    error,

    // Actions
    fetchMySchedules,
    clearError,

    // Utilities
    getSchedulesByDay,
    getCurrentClass,
    getNextClass,

    // Computed
    hasSchedulesToday: todaySchedules.length > 0,
    totalSchedules: schedules.length,
  };
};
