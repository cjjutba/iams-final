/**
 * useDetectionWebSocket
 *
 * Custom hook for the WebRTC-mode live stream WebSocket. The WebSocket
 * carries lightweight `fused_tracks` metadata (~200 bytes per message),
 * while video is delivered via WebRTC.
 *
 * Responsibilities:
 * - Connect/reconnect to ws://<host>/api/v1/stream/{scheduleId}
 * - Parse `type: "connected"` → set stream mode
 * - Parse `type: "fused_tracks"` → update fusedTracks + studentMap
 * - Ping/pong heartbeat
 * - Auto-reconnect on disconnect (exponential backoff)
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import { config } from '../constants/config';
import { storage } from '../utils/storage';
import type { FusedTrack } from '../engines/TrackAnimationEngine';

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

interface FusedTracksMessage {
  type: 'fused_tracks';
  room_id: string;
  timestamp: string;
  seq: number;
  frame_width: number;
  frame_height: number;
  tracks: Array<{
    track_id: number;
    bbox: [number, number, number, number];
    confidence: number;
    user_id: string | null;
    name: string | null;
    student_id: string | null;
    similarity: number | null;
    state: 'confirmed' | 'tentative';
    missed_frames: number;
  }>;
}

type WsMessage = ConnectedMessage | FusedTracksMessage | { type: string };

export interface UseDetectionWebSocketReturn {
  fusedTracks: FusedTrack[];
  isConnected: boolean;
  isConnecting: boolean;
  /** True when connected but waiting for camera/edge device to come online. */
  isWaitingForCamera: boolean;
  streamMode: 'webrtc' | null;
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
  const [fusedTracks, setFusedTracks] = useState<FusedTrack[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(true);
  const [streamMode, setStreamMode] = useState<'webrtc' | null>(null);
  const [studentMap, setStudentMap] = useState<Map<string, DetectedStudent>>(new Map());
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [isWaitingForCamera, setIsWaitingForCamera] = useState(false);
  const [detectionWidth, setDetectionWidth] = useState(1280);
  const [detectionHeight, setDetectionHeight] = useState(720);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);
  const hasErrorRef = useRef(false);
  const reconnectAttemptRef = useRef(0);
  const MAX_RECONNECT_DELAY_MS = 30_000;
  const BASE_RECONNECT_DELAY_MS = 1_000;

  const streamModeRef = useRef<'webrtc' | null>(null);

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
          streamModeRef.current = 'webrtc';
          setIsWaitingForCamera(false);
          // Now we know the stream mode — stop showing loading spinner
          setIsConnecting(false);
        } else if (message.type === 'fused_tracks') {
          const ftMsg = message as FusedTracksMessage;

          // Update frame dimensions
          if (ftMsg.frame_width && ftMsg.frame_height) {
            setDetectionWidth(ftMsg.frame_width);
            setDetectionHeight(ftMsg.frame_height);
          }

          // Convert to FusedTrack format
          const tracks: FusedTrack[] = (ftMsg.tracks ?? []).map((t) => ({
            track_id: t.track_id,
            bbox: t.bbox,
            confidence: t.confidence,
            user_id: t.user_id,
            name: t.name,
            student_id: t.student_id,
            similarity: t.similarity,
            state: t.state,
            missed_frames: t.missed_frames,
          }));

          setFusedTracks(tracks);

          // Also update studentMap for detected students panel
          setStudentMap((prev) => {
            const next = new Map(prev);
            // Mark all as not currently detected
            next.forEach((student, key) => {
              if (student.currentlyDetected) {
                next.set(key, { ...student, currentlyDetected: false });
              }
            });
            // Mark detected students
            for (const t of tracks) {
              if (!t.user_id) continue;
              next.set(t.user_id, {
                user_id: t.user_id,
                name: t.name || 'Unknown',
                student_id: t.student_id || '',
                confidence: t.confidence,
                currentlyDetected: true,
                lastSeen: ftMsg.timestamp,
              });
            }
            return next;
          });
        } else if (message.type === 'pong' || message.type === 'heartbeat') {
          // Keep-alive responses — no action needed
        } else if (message.type === 'waiting') {
          // Camera not streaming yet — backend keeps WS open and polls
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
    fusedTracks,
    isConnected,
    isConnecting,
    isWaitingForCamera,
    streamMode,
    studentMap,
    connectionError,
    reconnect,
    detectionWidth,
    detectionHeight,
  };
}
