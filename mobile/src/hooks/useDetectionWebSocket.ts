/**
 * useDetectionWebSocket
 *
 * Custom hook for the HLS-mode live stream WebSocket. In HLS mode the
 * WebSocket only carries lightweight detection metadata (~200 bytes per
 * message), while video is delivered via HLS to the native video player.
 *
 * Responsibilities:
 * - Connect/reconnect to ws://<host>/api/v1/stream/{scheduleId}
 * - Parse `type: "connected"` → extract HLS URL
 * - Parse `type: "detections"` → update detection list + student map
 * - Ping/pong heartbeat
 * - Auto-reconnect on disconnect (3-second delay)
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import { config } from '../constants/config';
import { storage } from '../utils/storage';
import type { DetectionItem } from '../components/video/DetectionOverlay';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DetectedStudent {
  user_id: string;
  name: string;
  student_id: string;
  confidence: number;
  currentlyDetected: boolean;
  lastSeen: string;
}

interface ConnectedMessage {
  type: 'connected';
  hls_url: string;
  schedule_id: string;
  room_id: string;
  mode: string;
  stream_fps: number;
  stream_resolution: string;
}

interface DetectionsMessage {
  type: 'detections';
  timestamp: string;
  detections: DetectionItem[];
  detection_width?: number;
  detection_height?: number;
}

type WsMessage = ConnectedMessage | DetectionsMessage | { type: string };

export interface UseDetectionWebSocketReturn {
  detections: DetectionItem[];
  isConnected: boolean;
  isConnecting: boolean;
  hlsUrl: string | null;
  studentMap: Map<string, DetectedStudent>;
  connectionError: string | null;
  reconnect: () => void;
  /** Detection frame width (from recognition service). */
  detectionWidth: number;
  /** Detection frame height (from recognition service). */
  detectionHeight: number;
}

// ---------------------------------------------------------------------------
// WebSocket URL builder
// ---------------------------------------------------------------------------

const getStreamWsUrl = (scheduleId: string): string => {
  const baseUrl = config.API_BASE_URL;
  const wsBase = baseUrl.replace(/^http/, 'ws');
  return wsBase.replace(/\/api\/v1$/, `/api/v1/stream/${scheduleId}`);
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useDetectionWebSocket(scheduleId: string): UseDetectionWebSocketReturn {
  const [detections, setDetections] = useState<DetectionItem[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(true);
  const [hlsUrl, setHlsUrl] = useState<string | null>(null);
  const [studentMap, setStudentMap] = useState<Map<string, DetectedStudent>>(new Map());
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [detectionWidth, setDetectionWidth] = useState(1280);
  const [detectionHeight, setDetectionHeight] = useState(720);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);
  const hasErrorRef = useRef(false);

  // --------------------------------------------------
  // Connect
  // --------------------------------------------------

  const connectWebSocket = useCallback(async () => {
    if (!isMountedRef.current) return;

    // Cleanup previous
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnecting(true);
    setConnectionError(null);
    hasErrorRef.current = false;

    const url = getStreamWsUrl(scheduleId);
    const token = await storage.getAccessToken();
    const wsUrl = token ? `${url}?token=${encodeURIComponent(token)}` : url;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMountedRef.current) return;
      setIsConnected(true);
      setIsConnecting(false);
      setConnectionError(null);

      // Start ping interval to keep connection alive
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          try {
            ws.send(JSON.stringify({ type: 'ping' }));
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

        if (message.type === 'connected') {
          const connMsg = message as ConnectedMessage;
          if (connMsg.hls_url) {
            // Build full HLS URL from relative path
            const baseUrl = config.API_BASE_URL;
            const httpBase = baseUrl.replace(/\/api\/v1$/, '');
            setHlsUrl(`${httpBase}${connMsg.hls_url}`);
          }
        } else if (message.type === 'detections') {
          const detMsg = message as DetectionsMessage;
          setDetections(detMsg.detections ?? []);

          // Update detection frame dimensions if provided
          if (detMsg.detection_width && detMsg.detection_height) {
            setDetectionWidth(detMsg.detection_width);
            setDetectionHeight(detMsg.detection_height);
          }

          // Update student map
          const dets = detMsg.detections;
          if (dets && dets.length > 0) {
            setStudentMap((prev) => {
              const next = new Map(prev);

              // Mark all as not currently detected
              next.forEach((student, key) => {
                if (student.currentlyDetected) {
                  next.set(key, { ...student, currentlyDetected: false });
                }
              });

              // Update from this detection
              for (const det of dets) {
                if (!det.user_id) continue;
                next.set(det.user_id, {
                  user_id: det.user_id,
                  name: det.name || 'Unknown',
                  student_id: det.student_id || '',
                  confidence: det.confidence,
                  currentlyDetected: true,
                  lastSeen: detMsg.timestamp,
                });
              }

              return next;
            });
          } else {
            // No detections — mark all not currently detected
            setStudentMap((prev) => {
              let changed = false;
              const next = new Map(prev);
              next.forEach((student, key) => {
                if (student.currentlyDetected) {
                  next.set(key, { ...student, currentlyDetected: false });
                  changed = true;
                }
              });
              return changed ? next : prev;
            });
          }
        } else if (message.type === 'pong' || message.type === 'heartbeat') {
          // Keep-alive responses — no action needed
        } else if (message.type === 'error') {
          const errMsg = message as { type: string; message?: string };
          hasErrorRef.current = true;
          setConnectionError(errMsg.message ?? 'Stream error');
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onerror = () => {
      if (!isMountedRef.current) return;
      setIsConnected(false);
      setIsConnecting(false);
    };

    ws.onclose = () => {
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = null;
      }
      if (!isMountedRef.current) return;
      setIsConnected(false);
      setIsConnecting(false);

      // Don't auto-reconnect if the server sent an error (permanent failure)
      if (hasErrorRef.current) return;

      // Auto-reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        if (isMountedRef.current) {
          connectWebSocket();
        }
      }, 3000);
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
      if (nextState === 'active' && !isConnected && !isConnecting) {
        connectWebSocket();
      }
    };

    const subscription = AppState.addEventListener('change', handleAppState);
    return () => subscription.remove();
  }, [isConnected, isConnecting, connectWebSocket]);

  return {
    detections,
    isConnected,
    isConnecting,
    hlsUrl,
    studentMap,
    connectionError,
    reconnect: connectWebSocket,
    detectionWidth,
    detectionHeight,
  };
}
