// mobile/src/hooks/useWebRTC.ts
/**
 * useWebRTC
 *
 * Manages a WebRTC peer connection to the live camera feed.
 * Uses the WHEP protocol via the FastAPI signaling proxy.
 *
 * Flow:
 * 1. GET /api/v1/webrtc/config  → fetch ICE server list (STUN + optional TURN)
 * 2. Create RTCPeerConnection with ICE servers
 * 3. Add recvonly transceivers (video + audio)
 * 4. createOffer() + setLocalDescription()
 * 5. POST /api/v1/webrtc/{scheduleId}/offer  → get SDP answer
 * 6. setRemoteDescription(answer)
 * 7. ICE negotiation → ontrack fires → remoteStream is set → video plays
 *
 * Reconnects automatically with exponential backoff on ICE failure.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  RTCPeerConnection,
  RTCSessionDescription,
  MediaStream,
} from 'react-native-webrtc';
import { config } from '../constants/config';
import { storage } from '../utils/storage';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface IceServer {
  urls: string[];
  username?: string;
  credential?: string;
}

export interface UseWebRTCReturn {
  remoteStream: MediaStream | null;
  connectionState: RTCIceConnectionState | 'idle' | 'connecting';
  error: string | null;
  reconnect: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BASE_RECONNECT_MS = 1_000;   // 1s initial backoff
const MAX_RECONNECT_MS = 30_000;   // 30s max backoff

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useWebRTC(scheduleId: string, enabled: boolean): UseWebRTCReturn {
  const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null);
  const [connectionState, setConnectionState] = useState<
    RTCIceConnectionState | 'idle' | 'connecting'
  >('idle');
  const [error, setError] = useState<string | null>(null);

  const pcRef = useRef<RTCPeerConnection | null>(null);
  const isMountedRef = useRef(true);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --------------------------------------------------
  // scheduleReconnect — exponential backoff
  // --------------------------------------------------

  const scheduleReconnect = useCallback(() => {
    if (!isMountedRef.current) return;
    const attempt = reconnectAttemptRef.current;
    const delay = Math.min(
      BASE_RECONNECT_MS * Math.pow(2, attempt),
      MAX_RECONNECT_MS,
    );
    reconnectAttemptRef.current = attempt + 1;
    reconnectTimerRef.current = setTimeout(() => {
      if (isMountedRef.current) connect();
    }, delay);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --------------------------------------------------
  // connect — full WebRTC handshake
  // --------------------------------------------------

  const connect = useCallback(async () => {
    if (!isMountedRef.current || !enabled) return;

    // Tear down any previous peer connection
    if (pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
    }
    setRemoteStream(null);
    setError(null);
    setConnectionState('connecting');

    try {
      // Step 1: Get ICE servers from backend
      const token = await storage.getAccessToken();
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };

      const configResp = await fetch(`${config.API_BASE_URL}/webrtc/config`, {
        headers,
      });
      if (!configResp.ok) {
        throw new Error(`Failed to fetch ICE config (${configResp.status})`);
      }
      const configData = await configResp.json();
      const iceServers: IceServer[] = configData?.data?.ice_servers ?? [
        { urls: ['stun:stun.l.google.com:19302'] },
      ];

      // Step 2: Create peer connection
      const pc = new RTCPeerConnection({ iceServers } as any);
      pcRef.current = pc;

      // Step 3: Add receive-only transceivers (video + audio)
      pc.addTransceiver('video', { direction: 'recvonly' });
      pc.addTransceiver('audio', { direction: 'recvonly' });

      // Step 4a: Handle incoming video track
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (pc as any).addEventListener('track', (event: any) => {
        if (event.streams?.[0] && isMountedRef.current) {
          setRemoteStream(event.streams[0]);
        }
      });

      // Step 4b: Track ICE connection state
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (pc as any).addEventListener('iceconnectionstatechange', () => {
        if (!isMountedRef.current) return;
        const state = pc.iceConnectionState as RTCIceConnectionState;
        setConnectionState(state);

        if (state === 'connected' || state === 'completed') {
          reconnectAttemptRef.current = 0;
          setError(null);
        }

        if (state === 'failed' || state === 'disconnected') {
          scheduleReconnect();
        }
      });

      // Step 5: Create offer and set local description
      const offer = await pc.createOffer({} as any);
      await pc.setLocalDescription(offer);

      // Step 6: POST offer to FastAPI signaling proxy
      const offerResp = await fetch(
        `${config.API_BASE_URL}/webrtc/${scheduleId}/offer`,
        {
          method: 'POST',
          headers,
          body: JSON.stringify({ sdp: offer.sdp, type: offer.type }),
        },
      );

      if (!offerResp.ok) {
        const errBody = await offerResp.json().catch(() => ({}));
        throw new Error(
          errBody?.detail ?? `Offer rejected (${offerResp.status})`,
        );
      }

      const offerData = await offerResp.json();
      const { sdp, type } = offerData.data;

      // Step 7: Set remote description (answer from mediamtx)
      await pc.setRemoteDescription(new RTCSessionDescription({ sdp, type }));

      // ICE negotiation now proceeds automatically.
      // oniceconnectionstatechange will fire when video flows.

    } catch (err: unknown) {
      if (!isMountedRef.current) return;
      const message =
        err instanceof Error ? err.message : 'WebRTC connection failed';
      setError(message);
      setConnectionState('failed' as RTCIceConnectionState);
      scheduleReconnect();
    }
  }, [scheduleId, enabled, scheduleReconnect]);

  // --------------------------------------------------
  // Mount / unmount
  // --------------------------------------------------

  useEffect(() => {
    isMountedRef.current = true;

    if (enabled) {
      connect();
    }

    return () => {
      isMountedRef.current = false;

      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      if (pcRef.current) {
        pcRef.current.close();
        pcRef.current = null;
      }
    };
  }, [connect, enabled]);

  // --------------------------------------------------
  // Manual reconnect (resets backoff counter)
  // --------------------------------------------------

  const reconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    reconnectAttemptRef.current = 0;
    connect();
  }, [connect]);

  return { remoteStream, connectionState, error, reconnect };
}
