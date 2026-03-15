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
 *
 * Detection delay:
 *   In HLS mode the recognition service reads RTSP frames in real-time,
 *   but the HLS video has ~1.5 s of pipeline latency.  Without
 *   compensation, bounding boxes appear where faces are NOW while the
 *   video shows where they were seconds ago.  A FIFO detection queue
 *   holds incoming detection messages and releases them after a
 *   mode-dependent delay so the overlay stays in sync with the video.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import { config } from '../constants/config';
import { storage } from '../utils/storage';
import type { DetectionItem } from '../components/video/DetectionOverlay';
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
  hls_url?: string;
  schedule_id: string;
  room_id: string;
  mode: 'hls' | 'webrtc' | 'legacy';
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

interface EdgeDetectionsMessage {
  type: 'edge_detections';
  room_id: string;
  timestamp: string;
  frame_width: number;
  frame_height: number;
  detections: Array<{
    bbox: [number, number, number, number];
    confidence: number;
    track_id: string;
    user_id?: string;
    name?: string;
    student_id?: string;
    similarity?: number;
  }>;
}

interface IdentityUpdateMessage {
  type: 'identity_update';
  mappings: Array<{
    track_id?: string;
    bbox?: { x: number; y: number; width: number; height: number };
    user_id: string;
    name: string;
    student_id: string;
    confidence: number;
  }>;
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

type WsMessage = ConnectedMessage | DetectionsMessage | EdgeDetectionsMessage | IdentityUpdateMessage | FusedTracksMessage | { type: string };

export interface UseDetectionWebSocketReturn {
  detections: DetectionItem[];
  fusedTracks: FusedTrack[];
  isConnected: boolean;
  isConnecting: boolean;
  hlsUrl: string | null;
  streamMode: 'hls' | 'webrtc' | 'legacy' | null;
  studentMap: Map<string, DetectedStudent>;
  connectionError: string | null;
  reconnect: () => void;
  /** Detection frame width (from recognition service). */
  detectionWidth: number;
  /** Detection frame height (from recognition service). */
  detectionHeight: number;
}

// ---------------------------------------------------------------------------
// Detection delay per stream mode (ms)
// ---------------------------------------------------------------------------

/** How long to hold detection messages before rendering, per stream mode.
 *  Compensates for the video pipeline latency in each mode. */
const DETECTION_DELAY: Record<string, number> = {
  hls: 1500,     // HLS: FFmpeg encode + segment + delivery + decode ≈ 1.5 s
  legacy: 500,   // Legacy MJPEG: smaller pipeline ≈ 0.5 s
  webrtc: 0,     // WebRTC: detections already lag behind video due to processing time
};

interface QueuedDetection {
  receivedAt: number; // Date.now()
  detections: DetectionItem[];
  timestamp: string;
  detectionWidth?: number;
  detectionHeight?: number;
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
  const [fusedTracks, setFusedTracks] = useState<FusedTrack[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(true);
  const [hlsUrl, setHlsUrl] = useState<string | null>(null);
  const [streamMode, setStreamMode] = useState<'hls' | 'webrtc' | 'legacy' | null>(null);
  const [studentMap, setStudentMap] = useState<Map<string, DetectedStudent>>(new Map());
  const [connectionError, setConnectionError] = useState<string | null>(null);
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

  // Detection delay queue
  const detectionQueueRef = useRef<QueuedDetection[]>([]);
  const drainIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const streamModeRef = useRef<string | null>(null);

  // Identity cache for edge_detections + identity_update dual-channel flow
  const identityCacheRef = useRef<Map<string, {
    user_id: string;
    name: string;
    student_id: string;
    confidence: number;
  }>>(new Map());

  // Track whether edge device is sending detections
  const usingEdgeDetectionsRef = useRef(false);

  // --------------------------------------------------
  // Apply a queued detection update
  // --------------------------------------------------

  const applyDetection = useCallback((queued: QueuedDetection) => {
    if (!isMountedRef.current) return;

    setDetections(queued.detections ?? []);

    if (queued.detectionWidth && queued.detectionHeight) {
      setDetectionWidth(queued.detectionWidth);
      setDetectionHeight(queued.detectionHeight);
    }

    const dets = queued.detections;
    if (dets && dets.length > 0) {
      setStudentMap((prev) => {
        const next = new Map(prev);
        next.forEach((student, key) => {
          if (student.currentlyDetected) {
            next.set(key, { ...student, currentlyDetected: false });
          }
        });
        for (const det of dets) {
          if (!det.user_id) continue;
          next.set(det.user_id, {
            user_id: det.user_id,
            name: det.name || 'Unknown',
            student_id: det.student_id || '',
            confidence: det.confidence,
            currentlyDetected: true,
            lastSeen: queued.timestamp,
          });
        }
        return next;
      });
    } else {
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
  }, []);

  // --------------------------------------------------
  // Queue drain loop — release detections after delay
  // --------------------------------------------------

  useEffect(() => {
    drainIntervalRef.current = setInterval(() => {
      // Skip draining when edge device is sending detections directly
      if (usingEdgeDetectionsRef.current) return;

      const queue = detectionQueueRef.current;
      if (queue.length === 0) return;

      const mode = streamModeRef.current ?? 'hls';
      const delayMs = DETECTION_DELAY[mode] ?? DETECTION_DELAY.hls;
      const now = Date.now();

      // Release all queued detections whose delay has elapsed.
      // Keep only the latest one (skip intermediate frames).
      let lastReady: QueuedDetection | null = null;
      while (queue.length > 0 && now - queue[0].receivedAt >= delayMs) {
        lastReady = queue.shift()!;
      }

      if (lastReady) {
        applyDetection(lastReady);
      }
    }, 50); // Check every 50 ms

    return () => {
      if (drainIntervalRef.current) {
        clearInterval(drainIntervalRef.current);
        drainIntervalRef.current = null;
      }
    };
  }, [applyDetection]);

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

    // Clear detection queue and edge state on reconnect
    detectionQueueRef.current = [];
    usingEdgeDetectionsRef.current = false;
    identityCacheRef.current.clear();

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
      reconnectAttemptRef.current = 0;
      setIsConnected(true);
      // Keep isConnecting=true until the 'connected' message arrives so the
      // loading spinner stays visible while streamMode/hlsUrl are still null.
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
          const mode = connMsg.mode ?? 'hls';
          setStreamMode(mode);
          streamModeRef.current = mode;
          if (connMsg.hls_url) {
            // Build full HLS URL from relative path
            const baseUrl = config.API_BASE_URL;
            const httpBase = baseUrl.replace(/\/api\/v1$/, '');
            setHlsUrl(`${httpBase}${connMsg.hls_url}`);
          }
          // Now we know the stream mode — stop showing loading spinner
          setIsConnecting(false);
        } else if (message.type === 'detections') {
          const detMsg = message as DetectionsMessage;

          // Push to delay queue instead of applying immediately.
          // The drain loop will release after the mode-appropriate delay.
          detectionQueueRef.current.push({
            receivedAt: Date.now(),
            detections: detMsg.detections ?? [],
            timestamp: detMsg.timestamp,
            detectionWidth: detMsg.detection_width,
            detectionHeight: detMsg.detection_height,
          });

          // Cap queue size to prevent unbounded growth (keep last ~5 s worth)
          const maxQueue = 100;
          if (detectionQueueRef.current.length > maxQueue) {
            detectionQueueRef.current = detectionQueueRef.current.slice(-maxQueue);
          }
        } else if (message.type === 'edge_detections') {
          const edgeMsg = message as EdgeDetectionsMessage;

          // Mark that we're receiving edge detections (disables delay queue)
          usingEdgeDetectionsRef.current = true;

          // Update detection frame dimensions
          if (edgeMsg.frame_width && edgeMsg.frame_height) {
            setDetectionWidth(edgeMsg.frame_width);
            setDetectionHeight(edgeMsg.frame_height);
          }

          // Convert edge detections to DetectionItems
          const edgeDets: DetectionItem[] = (edgeMsg.detections ?? []).map((d) => {
            // Convert bbox array [x, y, w, h] to DetectionBBox object
            const bbox = {
              x: d.bbox[0],
              y: d.bbox[1],
              width: d.bbox[2],
              height: d.bbox[3],
            };

            // Check if the relay already merged identity (user_id on detection)
            let userId = d.user_id ?? null;
            let name = d.name ?? null;
            let studentId = d.student_id ?? null;
            let similarity = d.similarity ?? null;

            // Merge cached identity from identity_update messages
            if (!userId && d.track_id) {
              const cached = identityCacheRef.current.get(d.track_id);
              if (cached) {
                userId = cached.user_id;
                name = cached.name;
                studentId = cached.student_id;
                similarity = cached.confidence;
              }
            }

            return {
              bbox,
              confidence: d.confidence,
              user_id: userId,
              name,
              student_id: studentId,
              similarity,
              track_id: d.track_id,
            } as DetectionItem;
          });

          // Apply immediately — no delay queue
          setDetections(edgeDets);

          // Update studentMap with identified detections
          if (edgeDets.length > 0) {
            setStudentMap((prev) => {
              const next = new Map(prev);
              next.forEach((student, key) => {
                if (student.currentlyDetected) {
                  next.set(key, { ...student, currentlyDetected: false });
                }
              });
              for (const det of edgeDets) {
                if (!det.user_id) continue;
                next.set(det.user_id, {
                  user_id: det.user_id,
                  name: det.name || 'Unknown',
                  student_id: det.student_id || '',
                  confidence: det.confidence,
                  currentlyDetected: true,
                  lastSeen: edgeMsg.timestamp,
                });
              }
              return next;
            });
          } else {
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
        } else if (message.type === 'identity_update') {
          const idMsg = message as IdentityUpdateMessage;
          const cache = identityCacheRef.current;

          // Update identity cache with new mappings
          for (const mapping of idMsg.mappings) {
            if (mapping.track_id) {
              cache.set(mapping.track_id, {
                user_id: mapping.user_id,
                name: mapping.name,
                student_id: mapping.student_id,
                confidence: mapping.confidence,
              });
            }
          }

          // Cap cache at 200 entries (prune oldest — Map iterates in insertion order)
          if (cache.size > 200) {
            const excess = cache.size - 200;
            let removed = 0;
            for (const key of cache.keys()) {
              if (removed >= excess) break;
              cache.delete(key);
              removed++;
            }
          }

          // Re-apply identities to current detections
          setDetections((prev) =>
            prev.map((det) => {
              const trackId = (det as any).track_id;
              if (!trackId || det.user_id) return det;
              const cached = cache.get(trackId);
              if (!cached) return det;
              return {
                ...det,
                user_id: cached.user_id,
                name: cached.name,
                student_id: cached.student_id,
                similarity: cached.confidence,
              };
            }),
          );

          // Also update studentMap for any newly identified detections
          setStudentMap((prev) => {
            const next = new Map(prev);
            for (const mapping of idMsg.mappings) {
              if (!mapping.user_id) continue;
              const existing = next.get(mapping.user_id);
              if (!existing) {
                next.set(mapping.user_id, {
                  user_id: mapping.user_id,
                  name: mapping.name,
                  student_id: mapping.student_id,
                  confidence: mapping.confidence,
                  currentlyDetected: true,
                  lastSeen: new Date().toISOString(),
                });
              }
            }
            return next;
          });
        } else if (message.type === 'pong' || message.type === 'heartbeat') {
          // Keep-alive responses — no action needed
        } else if (message.type === 'waiting') {
          // Camera not streaming yet — keep retrying automatically
          setConnectionError(null);
          setIsConnecting(true);
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
    detectionQueueRef.current = [];
    usingEdgeDetectionsRef.current = false;
    identityCacheRef.current.clear();
    connectWebSocket();
  }, [connectWebSocket]);

  return {
    detections,
    fusedTracks,
    isConnected,
    isConnecting,
    hlsUrl,
    streamMode,
    studentMap,
    connectionError,
    reconnect,
    detectionWidth,
    detectionHeight,
  };
}
