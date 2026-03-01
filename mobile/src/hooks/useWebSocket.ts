/**
 * useWebSocket Hook
 *
 * Manages WebSocket connection lifecycle and event handling.
 * Automatically connects/disconnects based on authentication state.
 *
 * Key design decisions:
 * - Uses refs for callbacks to avoid re-running the effect on every render
 * - Provides reactive connection state via websocketService.onStateChange
 * - Cleans up event subscriptions on unmount without destroying the service
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from './useAuth';
import { websocketService } from '../services';
import type { WebSocketMessage } from '../types';

interface UseWebSocketOptions {
  onAttendanceUpdate?: (message: WebSocketMessage) => void;
  onEarlyLeave?: (message: WebSocketMessage) => void;
  onSessionStart?: (message: WebSocketMessage) => void;
  onSessionEnd?: (message: WebSocketMessage) => void;
  onConnected?: () => void;
  autoConnect?: boolean;
}

export const useWebSocket = ({
  onAttendanceUpdate,
  onEarlyLeave,
  onSessionStart,
  onSessionEnd,
  onConnected,
  autoConnect = true,
}: UseWebSocketOptions = {}) => {
  const { user, isAuthenticated } = useAuth();
  const [connectionState, setConnectionState] = useState<string>(
    websocketService.connectionState
  );

  // Use refs for callbacks to avoid re-running the effect when callbacks change.
  // This prevents the connect/disconnect cycle that would occur if callbacks
  // were in the dependency array (since inline functions get new references each render).
  const onAttendanceUpdateRef = useRef(onAttendanceUpdate);
  const onEarlyLeaveRef = useRef(onEarlyLeave);
  const onSessionStartRef = useRef(onSessionStart);
  const onSessionEndRef = useRef(onSessionEnd);
  const onConnectedRef = useRef(onConnected);

  // Keep refs up-to-date with latest callback values
  useEffect(() => {
    onAttendanceUpdateRef.current = onAttendanceUpdate;
  }, [onAttendanceUpdate]);

  useEffect(() => {
    onEarlyLeaveRef.current = onEarlyLeave;
  }, [onEarlyLeave]);

  useEffect(() => {
    onSessionStartRef.current = onSessionStart;
  }, [onSessionStart]);

  useEffect(() => {
    onSessionEndRef.current = onSessionEnd;
  }, [onSessionEnd]);

  useEffect(() => {
    onConnectedRef.current = onConnected;
  }, [onConnected]);

  // Main effect: connect, subscribe to events, and clean up
  useEffect(() => {
    if (!isAuthenticated || !user || !autoConnect) {
      return;
    }

    const unsubscribers: (() => void)[] = [];

    // Subscribe to connection state changes for reactive UI updates
    const unsubState = websocketService.onStateChange((state) => {
      setConnectionState(state);
    });
    unsubscribers.push(unsubState);

    // Register event handlers using stable wrapper functions
    // that delegate to the latest callback ref
    const unsubConnected = websocketService.on('connected', () => {
      onConnectedRef.current?.();
    });
    unsubscribers.push(unsubConnected);

    const unsubAttendance = websocketService.onAttendanceUpdate((msg) => {
      onAttendanceUpdateRef.current?.(msg);
    });
    unsubscribers.push(unsubAttendance);

    const unsubEarlyLeave = websocketService.onEarlyLeave((msg) => {
      onEarlyLeaveRef.current?.(msg);
    });
    unsubscribers.push(unsubEarlyLeave);

    const unsubSessionStart = websocketService.onSessionStart((msg) => {
      onSessionStartRef.current?.(msg);
    });
    unsubscribers.push(unsubSessionStart);

    const unsubSessionEnd = websocketService.onSessionEnd((msg) => {
      onSessionEndRef.current?.(msg);
    });
    unsubscribers.push(unsubSessionEnd);

    // Acquire a ref-counted connection (only the last release disconnects)
    websocketService.acquire(user.id);

    // Cleanup on unmount or when dependencies change
    return () => {
      unsubscribers.forEach((unsub) => unsub());
      websocketService.release();
    };
  }, [isAuthenticated, user?.id, autoConnect]);

  // Stable reference for manual connect
  const connect = useCallback(() => {
    if (user) {
      websocketService.connect(user.id);
    }
  }, [user?.id]);

  // Stable reference for manual disconnect
  const disconnect = useCallback(() => {
    websocketService.disconnect();
  }, []);

  return {
    isConnected: connectionState === 'CONNECTED',
    connectionState,
    connect,
    disconnect,
  };
};
