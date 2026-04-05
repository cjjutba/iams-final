/**
 * useAttendanceWebSocket
 *
 * Custom hook for real-time attendance updates via WebSocket.
 * Connects to /api/v1/ws/attendance/{scheduleId} and receives
 * `attendance_update` messages whenever the presence engine
 * completes a scan cycle (~every 60 seconds).
 *
 * Responsibilities:
 * - Connect/reconnect to ws://<host>/api/v1/ws/attendance/{scheduleId}
 * - Parse `type: "attendance_update"` messages
 * - Maintain summary counts (present, absent, late, total)
 * - Maintain student attendance list
 * - Ping/pong heartbeat (every 10s)
 * - Auto-reconnect on disconnect (exponential backoff)
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import { config } from '../constants/config';
import { storage } from '../utils/storage';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AttendanceSummary {
  present: number;
  absent: number;
  late: number;
  total: number;
}

export interface StudentAttendanceRecord {
  user_id: string;
  name: string;
  student_id: string;
  status: 'present' | 'absent' | 'late' | 'excused';
  check_in_time: string | null;
  presence_score: number | null;
}

interface AttendanceUpdateMessage {
  type: 'attendance_update';
  event: string;
  schedule_id: string;
  present_count: number;
  total_enrolled: number;
  late_count?: number;
  students: StudentAttendanceRecord[];
}

type WsMessage = AttendanceUpdateMessage | { type: string; message?: string };

export interface UseAttendanceWebSocketReturn {
  summary: AttendanceSummary;
  students: StudentAttendanceRecord[];
  isConnected: boolean;
  connectionError: string | null;
  reconnect: () => void;
}

// ---------------------------------------------------------------------------
// WebSocket URL builder
// ---------------------------------------------------------------------------

const getAttendanceWsUrl = (scheduleId: string): string => {
  // config.WS_URL is already ws://<host>/api/v1/ws
  return `${config.WS_URL}/attendance/${scheduleId}`;
};

// ---------------------------------------------------------------------------
// Default state
// ---------------------------------------------------------------------------

const DEFAULT_SUMMARY: AttendanceSummary = {
  present: 0,
  absent: 0,
  late: 0,
  total: 0,
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAttendanceWebSocket(
  scheduleId: string,
): UseAttendanceWebSocketReturn {
  const [summary, setSummary] = useState<AttendanceSummary>(DEFAULT_SUMMARY);
  const [students, setStudents] = useState<StudentAttendanceRecord[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);
  const hasErrorRef = useRef(false);
  const reconnectAttemptRef = useRef(0);
  const MAX_RECONNECT_DELAY_MS = 30_000;
  const BASE_RECONNECT_DELAY_MS = 1_000;

  // --------------------------------------------------
  // Connect
  // --------------------------------------------------

  const connectWebSocket = useCallback(async () => {
    if (!isMountedRef.current) return;

    // Cleanup previous connection
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnectionError(null);
    hasErrorRef.current = false;

    const url = getAttendanceWsUrl(scheduleId);
    const token = await storage.getAccessToken();
    const wsUrl = token ? `${url}?token=${encodeURIComponent(token)}` : url;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMountedRef.current) return;
      reconnectAttemptRef.current = 0;
      setIsConnected(true);
      setConnectionError(null);

      // Start ping interval to keep connection alive
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          try {
            ws.send('ping');
          } catch {
            // ignore send errors
          }
        }
      }, 10_000);
    };

    ws.onmessage = (event: WebSocketMessageEvent) => {
      if (!isMountedRef.current) return;

      try {
        const message: WsMessage = JSON.parse(event.data);

        if (message.type === 'attendance_update') {
          const update = message as AttendanceUpdateMessage;

          // Update student list
          setStudents(update.students);

          // Derive summary counts
          const presentCount = update.present_count ?? 0;
          const totalEnrolled = update.total_enrolled ?? 0;
          const lateCount =
            update.late_count ??
            update.students.filter((s) => s.status === 'late').length;
          const absentCount = totalEnrolled - presentCount - lateCount;

          setSummary({
            present: presentCount,
            absent: Math.max(0, absentCount),
            late: lateCount,
            total: totalEnrolled,
          });
        } else if (message.type === 'error') {
          hasErrorRef.current = true;
          setConnectionError(message.message ?? 'Attendance WebSocket error');
        }
        // Ignore pong / heartbeat messages
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onerror = () => {
      if (!isMountedRef.current) return;
      setIsConnected(false);
    };

    ws.onclose = () => {
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = null;
      }
      if (!isMountedRef.current) return;
      setIsConnected(false);

      // Don't auto-reconnect if the server sent an error (permanent failure)
      if (hasErrorRef.current) return;

      // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s max
      const attempt = reconnectAttemptRef.current;
      const delay = Math.min(
        BASE_RECONNECT_DELAY_MS * Math.pow(2, attempt),
        MAX_RECONNECT_DELAY_MS,
      );
      reconnectAttemptRef.current = attempt + 1;

      reconnectTimeoutRef.current = setTimeout(() => {
        if (isMountedRef.current) {
          connectWebSocket();
        }
      }, delay);
    };
  }, [scheduleId]);

  // --------------------------------------------------
  // Mount / unmount
  // --------------------------------------------------

  useEffect(() => {
    isMountedRef.current = true;
    connectWebSocket();

    return () => {
      isMountedRef.current = false;

      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = null;
      }

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onmessage = null;
        wsRef.current.onerror = null;
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connectWebSocket]);

  // Reconnect when the app comes back to foreground
  useEffect(() => {
    const handleAppState = (nextState: AppStateStatus) => {
      if (nextState === 'active' && !isConnected) {
        connectWebSocket();
      }
    };

    const subscription = AppState.addEventListener('change', handleAppState);
    return () => subscription.remove();
  }, [isConnected, connectWebSocket]);

  const reconnect = useCallback(() => {
    reconnectAttemptRef.current = 0;
    connectWebSocket();
  }, [connectWebSocket]);

  return {
    summary,
    students,
    isConnected,
    connectionError,
    reconnect,
  };
}
