/**
 * Schedule Service
 *
 * Handles all schedule-related API calls:
 * - Retrieving user schedules (student enrolled / faculty teaching)
 * - Schedule details by ID
 * - Enrolled students list (faculty/admin)
 * - All schedules listing with day filter
 *
 * All endpoints are relative to the base URL configured in api.ts.
 * Backend router prefix: /schedules
 *
 * IMPORTANT: The backend returns response data directly from the
 * Pydantic response_model -- there is NO generic ApiResponse wrapper.
 *
 * @see backend/app/routers/schedules.py
 * @see backend/app/schemas/schedule.py
 */

import { api } from '../utils/api';
import type { Schedule, ScheduleWithStudents } from '../types';

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

export const scheduleService = {
  /**
   * Get schedules for the current authenticated user.
   * - Students receive their enrolled schedules
   * - Faculty receive their teaching schedules
   * - Admins receive all schedules
   *
   * @returns Array of schedule objects
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /schedules/me
   * Response: List[ScheduleResponse]
   */
  async getMySchedules(): Promise<Schedule[]> {
    const response = await api.get<Schedule[]>('/schedules/me');
    return response.data;
  },

  /**
   * Get a single schedule by its UUID.
   *
   * @param scheduleId - The schedule UUID
   * @returns The schedule object
   * @throws AxiosError (404 if not found)
   *
   * Backend: GET /schedules/{scheduleId}
   * Response: ScheduleResponse
   */
  async getScheduleById(scheduleId: string): Promise<Schedule> {
    const response = await api.get<Schedule>(`/schedules/${scheduleId}`);
    return response.data;
  },

  /**
   * Get enrolled students for a schedule (faculty/admin only).
   *
   * @param scheduleId - The schedule UUID
   * @returns Schedule object with enrolled_students array
   * @throws AxiosError (404 if schedule not found, 403 if not faculty/admin)
   *
   * Backend: GET /schedules/{scheduleId}/students
   * Response: ScheduleWithStudents (extends ScheduleResponse with enrolled_students)
   */
  async getScheduleStudents(scheduleId: string): Promise<ScheduleWithStudents> {
    const response = await api.get<ScheduleWithStudents>(
      `/schedules/${scheduleId}/students`,
    );
    return response.data;
  },

  /**
   * Get all schedules, optionally filtered by day of week.
   * Available to any authenticated user.
   *
   * @param day - Optional day filter (0=Monday .. 6=Sunday)
   * @returns Array of schedules
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /schedules/?day={day}
   * Response: List[ScheduleResponse]
   */
  async getAllSchedules(day?: number): Promise<Schedule[]> {
    const response = await api.get<Schedule[]>('/schedules/', {
      params: day !== undefined ? { day } : undefined,
    });
    return response.data;
  },

  // ---------------------------------------------------------------------------
  // Client-side convenience methods (no extra API calls)
  // ---------------------------------------------------------------------------

  /**
   * Get schedules for a specific day of the week.
   * Fetches all user schedules first, then filters client-side.
   *
   * @param dayOfWeek - Day number (0=Monday .. 6=Sunday)
   * @returns Filtered array of active schedules for that day
   */
  async getSchedulesByDay(dayOfWeek: number): Promise<Schedule[]> {
    const schedules = await this.getMySchedules();
    return schedules.filter(
      (s) => s.day_of_week === dayOfWeek && s.is_active,
    );
  },

  /**
   * Get today's schedules for the current user.
   * Converts JS Date.getDay() (0=Sunday) to backend format (0=Monday).
   *
   * @returns Array of today's active schedules
   */
  async getTodaySchedules(): Promise<Schedule[]> {
    const jsDay = new Date().getDay(); // 0=Sunday, 1=Monday, ..., 6=Saturday
    const backendDay = jsDay === 0 ? 6 : jsDay - 1; // 0=Monday, ..., 6=Sunday
    return this.getSchedulesByDay(backendDay);
  },

  /**
   * Find the currently-ongoing class, if any.
   * Compares current local time against each of today's schedule time ranges.
   *
   * @returns The ongoing schedule or null if no class is in session
   */
  async getCurrentClass(): Promise<Schedule | null> {
    const todaySchedules = await this.getTodaySchedules();
    const now = new Date();
    const currentTime = `${now.getHours().toString().padStart(2, '0')}:${now
      .getMinutes()
      .toString()
      .padStart(2, '0')}:00`;

    for (const schedule of todaySchedules) {
      if (currentTime >= schedule.start_time && currentTime <= schedule.end_time) {
        return schedule;
      }
    }

    return null;
  },
};
