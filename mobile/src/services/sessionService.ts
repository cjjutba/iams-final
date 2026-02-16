/**
 * Session Service
 *
 * Handles attendance session management API calls.
 * Faculty can start/stop class sessions; sessions also auto-start/stop
 * based on schedule times via the backend scheduler.
 *
 * Backend router prefix: /presence
 *
 * @see backend/app/routers/presence.py
 */

import { api } from '../utils/api';

// ---------------------------------------------------------------------------
// Response types matching backend Pydantic schemas
// ---------------------------------------------------------------------------

export interface SessionStartResponse {
  schedule_id: string;
  started_at: string;
  student_count: number;
  message: string;
}

export interface SessionEndResponse {
  schedule_id: string;
  total_scans: number;
  total_students: number;
  present_count: number;
  early_leave_count: number;
  message: string;
}

export interface ActiveSessionsResponse {
  active_sessions: string[];
  count: number;
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

export const sessionService = {
  /**
   * Start an attendance session for a schedule.
   *
   * Creates attendance records for all enrolled students and initializes
   * presence tracking. Can be called manually by faculty before the
   * schedule's start_time (auto-scheduler handles the rest).
   *
   * @param scheduleId - The schedule UUID
   * @returns Session start response with student count
   *
   * Backend: POST /presence/sessions/start
   */
  async startSession(scheduleId: string): Promise<SessionStartResponse> {
    const response = await api.post<SessionStartResponse>(
      '/presence/sessions/start',
      { schedule_id: scheduleId },
    );
    return response.data;
  },

  /**
   * End an active attendance session.
   *
   * Finalizes presence scores, sets check-out times, and stops tracking.
   * Marks the session as manually ended so the auto-scheduler won't restart it.
   *
   * @param scheduleId - The schedule UUID
   * @returns Session end response with summary stats
   *
   * Backend: POST /presence/sessions/end?schedule_id=...
   */
  async endSession(scheduleId: string): Promise<SessionEndResponse> {
    const response = await api.post<SessionEndResponse>(
      '/presence/sessions/end',
      null,
      { params: { schedule_id: scheduleId } },
    );
    return response.data;
  },

  /**
   * Get list of currently active session schedule IDs.
   *
   * Used to check if any sessions are running (for UI state).
   *
   * @returns Active sessions with count
   *
   * Backend: GET /presence/sessions/active
   */
  async getActiveSessions(): Promise<ActiveSessionsResponse> {
    const response = await api.get<ActiveSessionsResponse>(
      '/presence/sessions/active',
    );
    return response.data;
  },
};
