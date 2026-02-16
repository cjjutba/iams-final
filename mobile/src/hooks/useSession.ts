/**
 * useSession Hook
 *
 * Manages attendance session state for faculty.
 * Tracks which sessions are active and provides start/stop actions.
 * Listens to WebSocket events for real-time session status updates.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { sessionService } from '../services/sessionService';
import type { SessionStartResponse, SessionEndResponse } from '../services/sessionService';
import { useWebSocket } from './useWebSocket';
import type { WebSocketMessage } from '../types';
import { getErrorMessage } from '../utils';

interface UseSessionReturn {
  /** List of currently active schedule IDs */
  activeSessionIds: string[];
  /** Whether any session operation is in progress */
  isLoading: boolean;
  /** Last error message */
  error: string | null;
  /** Check if a specific schedule has an active session */
  isSessionActive: (scheduleId: string) => boolean;
  /** Start a session for a schedule */
  startSession: (scheduleId: string) => Promise<SessionStartResponse | null>;
  /** End a session for a schedule */
  endSession: (scheduleId: string) => Promise<SessionEndResponse | null>;
  /** Refresh active sessions from backend */
  refreshActiveSessions: () => Promise<void>;
}

export const useSession = (): UseSessionReturn => {
  const [activeSessionIds, setActiveSessionIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  // Listen for WebSocket session events
  useWebSocket({
    onSessionStart: (message: WebSocketMessage) => {
      if (message.data?.schedule_id) {
        setActiveSessionIds((prev) => {
          if (prev.includes(message.data.schedule_id)) return prev;
          return [...prev, message.data.schedule_id];
        });
      }
    },
    onSessionEnd: (message: WebSocketMessage) => {
      if (message.data?.schedule_id) {
        setActiveSessionIds((prev) =>
          prev.filter((id) => id !== message.data.schedule_id),
        );
      }
    },
  });

  // Fetch active sessions on mount
  const refreshActiveSessions = useCallback(async () => {
    try {
      const result = await sessionService.getActiveSessions();
      if (mountedRef.current) {
        setActiveSessionIds(result.active_sessions);
      }
    } catch (err) {
      // Silently handle — not critical
      console.warn('Failed to fetch active sessions:', err);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    refreshActiveSessions();
    return () => {
      mountedRef.current = false;
    };
  }, [refreshActiveSessions]);

  const isSessionActive = useCallback(
    (scheduleId: string) => activeSessionIds.includes(scheduleId),
    [activeSessionIds],
  );

  const startSession = useCallback(
    async (scheduleId: string): Promise<SessionStartResponse | null> => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await sessionService.startSession(scheduleId);
        if (mountedRef.current) {
          setActiveSessionIds((prev) => {
            if (prev.includes(scheduleId)) return prev;
            return [...prev, scheduleId];
          });
        }
        return result;
      } catch (err) {
        const msg = getErrorMessage(err);
        if (mountedRef.current) setError(msg);
        return null;
      } finally {
        if (mountedRef.current) setIsLoading(false);
      }
    },
    [],
  );

  const endSession = useCallback(
    async (scheduleId: string): Promise<SessionEndResponse | null> => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await sessionService.endSession(scheduleId);
        if (mountedRef.current) {
          setActiveSessionIds((prev) =>
            prev.filter((id) => id !== scheduleId),
          );
        }
        return result;
      } catch (err) {
        const msg = getErrorMessage(err);
        if (mountedRef.current) setError(msg);
        return null;
      } finally {
        if (mountedRef.current) setIsLoading(false);
      }
    },
    [],
  );

  return {
    activeSessionIds,
    isLoading,
    error,
    isSessionActive,
    startSession,
    endSession,
    refreshActiveSessions,
  };
};
