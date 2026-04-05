/**
 * useDetectionWebSocket
 *
 * Custom hook for the live stream WebSocket. The WebSocket carries
 * lightweight recognition metadata while video is delivered via WebRTC
 * with bounding boxes burned in by the backend.
 *
 * Responsibilities:
 * - Connect/reconnect to ws://<host>/api/v1/stream/{scheduleId}
 * - Parse `type: "connected"` to set stream mode
 * - Parse `type: "fused_tracks"` to update the detected-students panel
 * - Ping/pong heartbeat
 * - Auto-reconnect on disconnect (exponential backoff)
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import { config } from '../constants/config';
import { storage } from '../utils/storage';

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
  schedule_id: string;
  room_id: string;
  mode: 'webrtc';
  stream_fps: number;
  stream_resolution: string;
}

/** Identity info nested inside a fused track. */
interface TrackIdentity {
  user_id: string;
  name: string;
  student_id: string;
  similarity: number;
}

/** A single track in the fused_tracks wire format. */
interface WireTrack {
  id: number;
  conf: number;
  state: 'confirmed' | 'tentative';
  identity?: TrackIdentity;
}

interface FusedTracksMessage {
  type: 'fused_tracks';
  room_id: string;
  ts: number;
  tracks: WireTrack[];
}

type WsMessage = ConnectedMessage | FusedTracksMessage | { type: string };

export interface UseDetectionWebSocketReturn {
  isConnected: boolean;
  isConnecting: boolean;
  /** True when connected but waiting for camera/edge device to come online. */
  isWaitingForCamera: boolean;
  streamMode: 'webrtc' | null;
  /** Detected/recognized students for the bottom panel. */
  studentMap: Map<string, DetectedStudent>;
  /** Total faces currently in frame (recognized + unknown). */
  detectedCount: number;
  /** Number of unrecognized faces currently in frame. */
  unknownCount: number;
  connectionError: string | null;
  reconnect: () => void;
}

// ---------------------------------------------------------------------------
// WebSocket URL builder
// ---------------------------------------------------------------------------

const getStreamWsUrl = (scheduleId: string): string => {
  // config.WS_URL is ws://<host>/api/v1/ws
  return `${config.WS_URL}/stream/${scheduleId}`;
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useDetectionWebSocket(scheduleId: string): UseDetectionWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(true);
  const [streamMode, setStreamMode] = useState<'webrtc' | null>(null);
  const [studentMap, setStudentMap] = useState<Map<string, DetectedStudent>>(new Map());
  const [detectedCount, setDetectedCount] = useState(0);
  const [unknownCount, setUnknownCount] = useState(0);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [isWaitingForCamera, setIsWaitingForCamera] = useState(false);

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
    setIsWaitingForCamera(false);
    hasErrorRef.current = false;

    const url = getStreamWsUrl(scheduleId);
    const token = await storage.getAccessToken();
    const wsUrl = token ? `${url}?token=${encodeURIComponent(token)}` : url;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMountedRef.current) return;
      reconnectAttemptRef.current = 0;
      setIsConnected(true);
      // Keep isConnecting=true until the 'connected' message arrives so the
      // loading spinner stays visible while streamMode is still null.
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
          setStreamMode('webrtc');
          setIsWaitingForCamera(false);
          // Now we know the stream mode -- stop showing loading spinner
          setIsConnecting(false);
        } else if (message.type === 'fused_tracks') {
          const ftMsg = message as FusedTracksMessage;
          const tsIso = new Date(ftMsg.ts).toISOString();
          const wireTracks = ftMsg.tracks ?? [];

          // Update status bar counts
          const recognizedIds = new Set<string>();
          let unknowns = 0;
          for (const t of wireTracks) {
            if (t.identity?.user_id) {
              recognizedIds.add(t.identity.user_id);
            } else {
              unknowns++;
            }
          }
          setDetectedCount(recognizedIds.size + unknowns);
          setUnknownCount(unknowns);

          // Update studentMap for the detected-students panel
          setStudentMap((prev) => {
            const next = new Map(prev);
            // Mark all as not currently detected
            next.forEach((student, key) => {
              if (student.currentlyDetected) {
                next.set(key, { ...student, currentlyDetected: false });
              }
            });
            // Mark detected students
            for (const t of wireTracks) {
              if (!t.identity?.user_id) continue;
              const id = t.identity;
              next.set(id.user_id, {
                user_id: id.user_id,
                name: id.name || 'Unknown',
                student_id: id.student_id || '',
                confidence: id.similarity ?? t.conf,
                currentlyDetected: true,
                lastSeen: tsIso,
              });
            }
            return next;
          });
        } else if (message.type === 'pong' || message.type === 'heartbeat') {
          // Keep-alive responses -- no action needed
        } else if (message.type === 'waiting') {
          // Camera not streaming yet -- backend keeps WS open and polls
          setConnectionError(null);
          setIsWaitingForCamera(true);
          setIsConnecting(false);
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
      if (nextState === 'active' && !isConnected && !isConnecting) {
        connectWebSocket();
      }
    };

    const subscription = AppState.addEventListener('change', handleAppState);
    return () => subscription.remove();
  }, [isConnected, isConnecting, connectWebSocket]);

  const reconnect = useCallback(() => {
    reconnectAttemptRef.current = 0;
    connectWebSocket();
  }, [connectWebSocket]);

  return {
    isConnected,
    isConnecting,
    isWaitingForCamera,
    streamMode,
    studentMap,
    detectedCount,
    unknownCount,
    connectionError,
    reconnect,
  };
}
