/**
 * Schedule Service
 *
 * Handles all schedule-related API calls:
 * - Fetching user schedules
 * - Schedule details
 * - Enrolled students
 */

import { api } from '../utils/api';
import type { Schedule, ScheduleWithAttendance, User, ApiResponse } from '../types';

export const scheduleService = {
  /**
   * Get my schedules (student: enrolled classes, faculty: teaching classes)
   */
  async getMySchedules(): Promise<ScheduleWithAttendance[]> {
    const response = await api.get<ApiResponse<ScheduleWithAttendance[]>>('/schedules/me');
    return response.data.data || [];
  },

  /**
   * Get schedule by ID
   */
  async getSchedule(id: string): Promise<Schedule> {
    const response = await api.get<ApiResponse<Schedule>>(`/schedules/${id}`);
    return response.data.data!;
  },

  /**
   * Get students enrolled in a schedule (faculty only)
   */
  async getScheduleStudents(id: string): Promise<User[]> {
    const response = await api.get<ApiResponse<User[]>>(`/schedules/${id}/students`);
    return response.data.data || [];
  },

  /**
   * Get schedules by day of week
   */
  async getSchedulesByDay(dayOfWeek: number): Promise<ScheduleWithAttendance[]> {
    const response = await api.get<ApiResponse<ScheduleWithAttendance[]>>(
      '/schedules/me',
      { params: { day_of_week: dayOfWeek } }
    );
    return response.data.data || [];
  },

  /**
   * Get today's schedules
   */
  async getTodaySchedules(): Promise<ScheduleWithAttendance[]> {
    const today = new Date().getDay();
    return await this.getSchedulesByDay(today);
  },

  /**
   * Get current ongoing class (if any)
   */
  async getCurrentClass(): Promise<ScheduleWithAttendance | null> {
    const todaySchedules = await this.getTodaySchedules();
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
  },
};
