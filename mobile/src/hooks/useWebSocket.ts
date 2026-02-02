/**
 * useWebSocket Hook
 *
 * Manages WebSocket connection lifecycle and event handling.
 * Automatically connects/disconnects based on component mount/unmount.
 */

import { useEffect, useRef } from 'react';
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
  const unsubscribersRef = useRef<(() => void)[]>([]);

  useEffect(() => {
    // Only connect if authenticated and autoConnect is true
    if (!isAuthenticated || !user || !autoConnect) {
      return;
    }

    // Connect to WebSocket
    websocketService.connect(user.id);

    // Register event handlers
    const unsubscribers: (() => void)[] = [];

    // Connected event
    if (onConnected) {
      const unsub = websocketService.on('connected', () => {
        onConnected();
      });
      unsubscribers.push(unsub);
    }

    // Attendance update event
    if (onAttendanceUpdate) {
      const unsub = websocketService.onAttendanceUpdate(onAttendanceUpdate);
      unsubscribers.push(unsub);
    }

    // Early leave event
    if (onEarlyLeave) {
      const unsub = websocketService.onEarlyLeave(onEarlyLeave);
      unsubscribers.push(unsub);
    }

    // Session start event
    if (onSessionStart) {
      const unsub = websocketService.onSessionStart(onSessionStart);
      unsubscribers.push(unsub);
    }

    // Session end event
    if (onSessionEnd) {
      const unsub = websocketService.onSessionEnd(onSessionEnd);
      unsubscribers.push(unsub);
    }

    unsubscribersRef.current = unsubscribers;

    // Cleanup on unmount
    return () => {
      // Unsubscribe from all events
      unsubscribersRef.current.forEach((unsub) => unsub());
      unsubscribersRef.current = [];

      // Disconnect WebSocket
      websocketService.disconnect();
    };
  }, [
    isAuthenticated,
    user?.id,
    autoConnect,
    onAttendanceUpdate,
    onEarlyLeave,
    onSessionStart,
    onSessionEnd,
    onConnected,
  ]);

  return {
    isConnected: websocketService.isConnected(),
    connect: () => user && websocketService.connect(user.id),
    disconnect: () => websocketService.disconnect(),
  };
};
