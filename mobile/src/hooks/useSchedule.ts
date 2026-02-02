/**
 * useSchedule Hook
 *
 * Provides access to schedule data with helpful utilities.
 * Manages schedule fetching and filtering.
 */

import { useEffect, useMemo } from 'react';
import { useScheduleStore } from '../stores';
import type { ScheduleWithAttendance } from '../types';

export const useSchedule = (autoFetch = true) => {
  const { schedules, isLoading, error, fetchMySchedules, clearError } = useScheduleStore();

  // Auto-fetch schedules on mount
  useEffect(() => {
    if (autoFetch && schedules.length === 0 && !isLoading) {
      fetchMySchedules();
    }
  }, [autoFetch]);

  // Get current day (0 = Sunday, 6 = Saturday)
  const currentDay = useMemo(() => new Date().getDay(), []);

  // Filter schedules by day
  const getSchedulesByDay = (dayOfWeek: number): ScheduleWithAttendance[] => {
    return schedules.filter((schedule) => schedule.dayOfWeek === dayOfWeek);
  };

  // Get today's schedules
  const todaySchedules = useMemo(() => {
    return getSchedulesByDay(currentDay);
  }, [schedules, currentDay]);

  // Get current ongoing class
  const getCurrentClass = (): ScheduleWithAttendance | null => {
    const now = new Date();
    const currentTime = now.getHours() * 60 + now.getMinutes();

    for (const schedule of todaySchedules) {
      const [startHour, startMin] = schedule.startTime.split(':').map(Number);
      const [endHour, endMin] = schedule.endTime.split(':').map(Number);

      const startMinutes = startHour * 60 + startMin;
      const endMinutes = endHour * 60 + endMin;

      if (currentTime >= startMinutes && currentTime <= endMinutes) {
        return schedule;
      }
    }

    return null;
  };

  // Get next upcoming class today
  const getNextClass = (): ScheduleWithAttendance | null => {
    const now = new Date();
    const currentTime = now.getHours() * 60 + now.getMinutes();

    const upcomingClasses = todaySchedules.filter((schedule) => {
      const [startHour, startMin] = schedule.startTime.split(':').map(Number);
      const startMinutes = startHour * 60 + startMin;
      return currentTime < startMinutes;
    });

    if (upcomingClasses.length === 0) return null;

    // Return the earliest upcoming class
    return upcomingClasses.reduce((earliest, current) => {
      const [eHour, eMin] = earliest.startTime.split(':').map(Number);
      const [cHour, cMin] = current.startTime.split(':').map(Number);

      const eMinutes = eHour * 60 + eMin;
      const cMinutes = cHour * 60 + cMin;

      return cMinutes < eMinutes ? current : earliest;
    });
  };

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
