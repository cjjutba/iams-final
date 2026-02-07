/**
 * Attendance Service
 *
 * Handles all attendance-related API calls:
 * - Student attendance history and summaries
 * - Faculty live attendance monitoring
 * - Presence logs for individual records
 * - Manual attendance entries (faculty only)
 * - Early leave event listing
 *
 * All endpoints are relative to the base URL configured in api.ts.
 * Backend router prefix: /attendance
 *
 * IMPORTANT: The backend returns response data directly from the
 * Pydantic response_model -- there is NO generic ApiResponse wrapper.
 *
 * @see backend/app/routers/attendance.py
 * @see backend/app/schemas/attendance.py
 */

import { api } from '../utils/api';
import type {
  AttendanceRecord,
  PresenceLog,
  LiveAttendanceResponse,
  AttendanceSummary,
  EarlyLeaveEvent,
  ManualAttendanceRequest,
} from '../types';

// ---------------------------------------------------------------------------
// Response types matching backend Pydantic schemas
// ---------------------------------------------------------------------------

/**
 * Maps to backend AttendanceRecordResponse.
 * Re-exported from types but listed here for documentation clarity.
 *
 * Backend fields: id, student_id, schedule_id, date, status,
 * check_in_time, check_out_time, presence_score, remarks,
 * total_scans, scans_present, student_name, subject_code
 */

/**
 * Maps to backend AttendanceSummary.
 * Backend fields: total_classes, present_count, late_count,
 * absent_count, early_leave_count, attendance_rate
 */

/**
 * Maps to backend PresenceLogResponse.
 * Backend fields: id (int), scan_number, scan_time, detected, confidence
 */

/**
 * Maps to backend EarlyLeaveResponse.
 * Backend fields: id, detected_at, last_seen_at, consecutive_misses,
 * notified, notified_at
 */

// ---------------------------------------------------------------------------
// Request parameter interfaces
// ---------------------------------------------------------------------------

/** Optional filters for early leave event queries */
interface EarlyLeaveFilters {
  schedule_id?: string;
  start_date?: string;
  end_date?: string;
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

export const attendanceService = {
  /**
   * Get the current student's attendance history.
   *
   * @param startDate - Optional ISO date string to filter from (YYYY-MM-DD)
   * @param endDate - Optional ISO date string to filter to (YYYY-MM-DD)
   * @returns Array of attendance records, most recent first
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /attendance/me (student only)
   * Response: List[AttendanceRecordResponse]
   */
  async getMyAttendance(
    startDate?: string,
    endDate?: string,
  ): Promise<AttendanceRecord[]> {
    const response = await api.get<AttendanceRecord[]>('/attendance/me', {
      params: {
        ...(startDate && { start_date: startDate }),
        ...(endDate && { end_date: endDate }),
      },
    });
    return response.data;
  },

  /**
   * Get today's attendance records for a specific schedule.
   * Intended for faculty to see which students are marked for today.
   *
   * @param scheduleId - The schedule UUID
   * @returns Array of today's attendance records for the schedule
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /attendance/today?schedule_id={scheduleId} (faculty only)
   * Response: List[AttendanceRecordResponse]
   */
  async getTodayAttendance(scheduleId: string): Promise<AttendanceRecord[]> {
    const response = await api.get<AttendanceRecord[]>('/attendance/today', {
      params: { schedule_id: scheduleId },
    });
    return response.data;
  },

  /**
   * Get live / real-time attendance status for a class session.
   * Shows per-student status, counts, and whether the session is active.
   *
   * @param scheduleId - The schedule UUID
   * @returns Live attendance snapshot
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /attendance/live/{scheduleId} (faculty only)
   * Response: LiveAttendanceResponse
   */
  async getLiveAttendance(scheduleId: string): Promise<LiveAttendanceResponse> {
    const response = await api.get<LiveAttendanceResponse>(
      `/attendance/live/${scheduleId}`,
    );
    return response.data;
  },

  /**
   * Get a single attendance record by its ID.
   *
   * Students can only view their own records.
   * Faculty can view records for their schedules.
   *
   * @param attendanceId - The attendance record UUID
   * @returns The attendance record
   * @throws AxiosError (404 if not found, 403 if access denied)
   *
   * Backend: GET /attendance/{attendanceId}
   * Response: AttendanceRecordResponse
   */
  async getAttendanceDetail(attendanceId: string): Promise<AttendanceRecord> {
    const response = await api.get<AttendanceRecord>(
      `/attendance/${attendanceId}`,
    );
    return response.data;
  },

  /**
   * Get presence scan logs (timeline) for a specific attendance record.
   * Each log represents one periodic scan result (detected / not detected).
   *
   * @param attendanceId - The attendance record UUID
   * @returns Array of presence logs ordered by scan number
   * @throws AxiosError (404 if record not found, 403 if access denied)
   *
   * Backend: GET /attendance/{attendanceId}/logs
   * Response: List[PresenceLogResponse]
   */
  async getPresenceLogs(attendanceId: string): Promise<PresenceLog[]> {
    const response = await api.get<PresenceLog[]>(
      `/attendance/${attendanceId}/logs`,
    );
    return response.data;
  },

  /**
   * Get attendance summary statistics for the current student.
   *
   * The backend returns field names like `total_classes`, `present_count`, etc.
   * but the frontend AttendanceSummary type uses `total`, `present`, etc.
   * This method transforms the backend response to match the frontend type.
   *
   * @param startDate - Start date (YYYY-MM-DD, required by backend)
   * @param endDate - End date (YYYY-MM-DD, required by backend)
   * @returns Summary with counts and attendance rate
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /attendance/me/summary?start_date=...&end_date=...
   * Backend response: { total_classes, present_count, late_count,
   *                     absent_count, early_leave_count, attendance_rate }
   */
  async getAttendanceSummary(
    startDate: string,
    endDate: string,
  ): Promise<AttendanceSummary> {
    // Backend schema field names differ from frontend type
    interface BackendAttendanceSummary {
      total_classes: number;
      present_count: number;
      late_count: number;
      absent_count: number;
      early_leave_count: number;
      attendance_rate: number;
    }

    const response = await api.get<BackendAttendanceSummary>(
      '/attendance/me/summary',
      { params: { start_date: startDate, end_date: endDate } },
    );

    const data = response.data;

    // Transform to frontend expected shape
    return {
      total: data.total_classes,
      present: data.present_count,
      late: data.late_count,
      absent: data.absent_count,
      early_leave: data.early_leave_count,
      attendance_rate: data.attendance_rate,
      start_date: startDate,
      end_date: endDate,
    };
  },

  /**
   * Create or update a manual attendance entry (faculty only).
   *
   * If a record already exists for the student/schedule/date combination
   * the backend updates it; otherwise a new record is created.
   *
   * @param data - Manual attendance payload with snake_case field names
   * @returns The created or updated attendance record
   * @throws AxiosError on validation or permission errors
   *
   * Backend: POST /attendance/manual (201 Created)
   * Request: ManualAttendanceRequest { student_id, schedule_id, date, status, remarks? }
   * Response: AttendanceRecordResponse
   */
  async createManualEntry(data: ManualAttendanceRequest): Promise<AttendanceRecord> {
    const response = await api.post<AttendanceRecord>(
      '/attendance/manual',
      data,
    );
    return response.data;
  },

  /**
   * Update an existing attendance record (faculty only).
   * Only `status` and `remarks` fields are allowed.
   *
   * @param attendanceId - The attendance record UUID
   * @param status - New attendance status
   * @param remarks - Optional remarks / reason for change
   * @returns The updated attendance record
   * @throws AxiosError on not found or permission errors
   *
   * Backend: PATCH /attendance/{attendanceId}
   * Request body: { status, remarks? }
   * Response: AttendanceRecordResponse
   */
  async updateAttendanceStatus(
    attendanceId: string,
    status: string,
    remarks?: string,
  ): Promise<AttendanceRecord> {
    const response = await api.patch<AttendanceRecord>(
      `/attendance/${attendanceId}`,
      { status, ...(remarks !== undefined && { remarks }) },
    );
    return response.data;
  },

  /**
   * Get early leave events with optional filters (faculty only).
   *
   * @param filters - Optional filters for schedule, start/end date
   * @returns Array of early leave events sorted by detection time
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /attendance/early-leaves/?schedule_id=...&start_date=...&end_date=...
   * Response: List[EarlyLeaveResponse]
   */
  async getEarlyLeaveEvents(
    filters?: EarlyLeaveFilters,
  ): Promise<EarlyLeaveEvent[]> {
    const response = await api.get<EarlyLeaveEvent[]>(
      '/attendance/early-leaves/',
      {
        params: filters
          ? {
              ...(filters.schedule_id && { schedule_id: filters.schedule_id }),
              ...(filters.start_date && { start_date: filters.start_date }),
              ...(filters.end_date && { end_date: filters.end_date }),
            }
          : undefined,
      },
    );
    return response.data;
  },
};
