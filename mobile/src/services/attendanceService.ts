/**
 * Attendance Service
 *
 * Handles all attendance-related API calls:
 * - Fetching attendance records
 * - Live attendance tracking
 * - Presence logs
 * - Manual attendance entry
 * - Attendance summaries
 */

import { api } from '../utils/api';
import type {
  AttendanceRecord,
  PresenceLog,
  LiveAttendanceResponse,
  AttendanceSummary,
  ApiResponse,
  PaginatedResponse,
} from '../types';

interface AttendanceFilters {
  startDate?: string;
  endDate?: string;
  scheduleId?: string;
  status?: string;
  page?: number;
  limit?: number;
}

interface ManualAttendanceData {
  scheduleId: string;
  studentId: string;
  status: string;
  remarks?: string;
}

export const attendanceService = {
  /**
   * Get today's attendance for a specific schedule
   */
  async getTodayAttendance(scheduleId: string): Promise<AttendanceRecord | null> {
    const response = await api.get<ApiResponse<AttendanceRecord>>(
      `/attendance/today`,
      { params: { schedule_id: scheduleId } }
    );
    return response.data.data || null;
  },

  /**
   * Get my attendance records within date range
   */
  async getMyAttendance(startDate?: string, endDate?: string): Promise<AttendanceRecord[]> {
    const response = await api.get<ApiResponse<AttendanceRecord[]>>(
      '/attendance/me',
      { params: { start_date: startDate, end_date: endDate } }
    );
    return response.data.data || [];
  },

  /**
   * Get attendance history with filters
   */
  async getAttendanceHistory(filters: AttendanceFilters): Promise<PaginatedResponse<AttendanceRecord>> {
    const response = await api.get<PaginatedResponse<AttendanceRecord>>(
      '/attendance/history',
      { params: filters }
    );
    return response.data;
  },

  /**
   * Get live attendance for a class (real-time view)
   */
  async getLiveAttendance(scheduleId: string): Promise<LiveAttendanceResponse> {
    const response = await api.get<ApiResponse<LiveAttendanceResponse>>(
      `/attendance/live/${scheduleId}`
    );
    return response.data.data!;
  },

  /**
   * Get detailed attendance record by ID
   */
  async getAttendanceDetail(id: string): Promise<AttendanceRecord> {
    const response = await api.get<ApiResponse<AttendanceRecord>>(`/attendance/${id}`);
    return response.data.data!;
  },

  /**
   * Get presence logs (timeline) for an attendance record
   */
  async getPresenceLogs(attendanceId: string): Promise<PresenceLog[]> {
    const response = await api.get<ApiResponse<PresenceLog[]>>(
      `/attendance/${attendanceId}/logs`
    );
    return response.data.data || [];
  },

  /**
   * Create manual attendance entry (faculty only)
   */
  async createManualEntry(data: ManualAttendanceData): Promise<AttendanceRecord> {
    const response = await api.post<ApiResponse<AttendanceRecord>>(
      '/attendance/manual',
      data
    );
    return response.data.data!;
  },

  /**
   * Get attendance summary/statistics
   */
  async getAttendanceSummary(
    startDate?: string,
    endDate?: string
  ): Promise<AttendanceSummary> {
    const response = await api.get<ApiResponse<AttendanceSummary>>(
      '/attendance/summary',
      { params: { start_date: startDate, end_date: endDate } }
    );
    return response.data.data!;
  },

  /**
   * Update attendance status (faculty only)
   */
  async updateAttendanceStatus(
    id: string,
    status: string,
    remarks?: string
  ): Promise<AttendanceRecord> {
    const response = await api.patch<ApiResponse<AttendanceRecord>>(
      `/attendance/${id}`,
      { status, remarks }
    );
    return response.data.data!;
  },

  /**
   * Export attendance report
   */
  async exportReport(filters: AttendanceFilters, format: 'csv' | 'pdf'): Promise<Blob> {
    const response = await api.get(`/attendance/export`, {
      params: { ...filters, format },
      responseType: 'blob',
    });
    return response.data;
  },
};
