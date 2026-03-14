/**
 * WebSocket Types
 *
 * Type definitions for WebSocket events and messages.
 */

// WebSocket event types
export enum WebSocketEventType {
  CONNECTED = 'connected',
  ATTENDANCE_UPDATE = 'attendance_update',
  EARLY_LEAVE = 'early_leave',
  EARLY_LEAVE_RETURN = 'early_leave_return',
  SESSION_START = 'session_start',
  SESSION_END = 'session_end',
  PRESENCE_WARNING = 'presence_warning',
  PRESENCE_SCORE = 'presence_score',
  STUDENT_CHECKED_IN = 'student_checked_in',
  NOTIFICATION = 'notification',
  ATTENDANCE_CONFIRMED = 'attendance_confirmed',
  LOW_ATTENDANCE_WARNING = 'low_attendance_warning',
  ANOMALY_DETECTED = 'anomaly_detected',
}

// Base WebSocket message
export interface WebSocketMessage<T = any> {
  event: WebSocketEventType | string;
  data: T;
}

// Connected event data
export interface ConnectedEventData {
  user_id: string;
  timestamp: string;
}

// Attendance update event data
export interface AttendanceUpdateEventData {
  student_id: string;
  schedule_id: string;
  status: string;
  check_in_time?: string;
  timestamp: string;
}

// Early leave event data
export interface EarlyLeaveEventData {
  student_id: string;
  student_name: string;
  schedule_id: string;
  detected_at: string;
  consecutive_misses: number;
  last_seen_at?: string;
}

// Session start event data
export interface SessionStartEventData {
  schedule_id: string;
  start_time: string;
  subject_code: string;
  subject_name: string;
}

// Session end event data
export interface SessionEndEventData {
  schedule_id: string;
  end_time: string;
  summary: {
    total_enrolled: number;
    present: number;
    late: number;
    absent: number;
    early_leave: number;
  };
}
