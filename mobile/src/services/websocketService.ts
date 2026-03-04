/**
 * WebSocket Service
 *
 * Manages WebSocket connection for real-time updates:
 * - Attendance updates
 * - Early leave alerts
 * - Session events
 * - Automatic reconnection with exponential backoff
 * - Heartbeat/ping mechanism for connection health
 *
 * Connection state machine: DISCONNECTED -> CONNECTING -> CONNECTED -> RECONNECTING
 */

import { AppState, type AppStateStatus } from 'react-native';
import { config } from '../constants';
import type { WebSocketMessage } from '../types';
import { WebSocketEventType } from '../types';

type MessageCallback = (message: WebSocketMessage) => void;
type ConnectionState = 'DISCONNECTED' | 'CONNECTING' | 'CONNECTED' | 'RECONNECTING';
type ConnectionStateCallback = (state: ConnectionState) => void;

/** Base reconnect delay in milliseconds */
const BASE_RECONNECT_DELAY = 1000;
/** Maximum reconnect delay in milliseconds */
const MAX_RECONNECT_DELAY = 30000;
/** Heartbeat interval in milliseconds */
const HEARTBEAT_INTERVAL = 30000;
/** Heartbeat timeout - how long to wait for pong response */
const HEARTBEAT_TIMEOUT = 5000;
/** Max consecutive heartbeat failures before triggering reconnect */
const MAX_HEARTBEAT_FAILURES = 2;

class WebSocketService {
  private socket: WebSocket | null = null;
  private userId: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = config.WS_MAX_RECONNECT_ATTEMPTS;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private heartbeatTimeout: ReturnType<typeof setTimeout> | null = null;
  private heartbeatFailures = 0;
  private messageHandlers: Map<string, Set<MessageCallback>> = new Map();
  private stateListeners: Set<ConnectionStateCallback> = new Set();
  private isIntentionalClose = false;
  private _connectionState: ConnectionState = 'DISCONNECTED';
  private appStateSubscription: ReturnType<typeof AppState.addEventListener> | null = null;
  /** Number of active consumers (hooks) holding the connection open */
  private refCount = 0;

  /**
   * Current connection state
   */
  get connectionState(): ConnectionState {
    return this._connectionState;
  }

  private setConnectionState(state: ConnectionState): void {
    if (this._connectionState !== state) {
      this._connectionState = state;
      this.stateListeners.forEach((listener) => {
        try {
          listener(state);
        } catch (error) {
          console.error('[WebSocket] State listener error:', error);
        }
      });
    }
  }

  /**
   * Subscribe to connection state changes
   * Returns an unsubscribe function
   */
  onStateChange(callback: ConnectionStateCallback): () => void {
    this.stateListeners.add(callback);
    return () => {
      this.stateListeners.delete(callback);
    };
  }

  /**
   * Connect to WebSocket server
   */
  connect(userId: string): void {
    // Avoid duplicate connections
    if (this.socket && this.userId === userId) {
      if (this.socket.readyState === WebSocket.OPEN ||
          this.socket.readyState === WebSocket.CONNECTING) {
        return;
      }
    }

    // Close any existing connection first
    if (this.socket) {
      this.socket.onclose = null; // prevent triggering reconnect
      this.socket.close();
      this.socket = null;
    }

    this.userId = userId;
    this.isIntentionalClose = false;
    this.setConnectionState(
      this.reconnectAttempts > 0 ? 'RECONNECTING' : 'CONNECTING'
    );

    try {
      const wsUrl = `${config.WS_URL}/${userId}`;
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        console.log('[WebSocket] Connected');
        this.reconnectAttempts = 0;
        this.heartbeatFailures = 0;
        this.setConnectionState('CONNECTED');
        this.startHeartbeat();
        this.emit(WebSocketEventType.CONNECTED, {
          event: WebSocketEventType.CONNECTED,
          data: { user_id: userId, timestamp: new Date().toISOString() },
        });
      };

      this.socket.onmessage = (event: WebSocketMessageEvent) => {
        this.handleMessage(event);
      };

      this.socket.onerror = (error: Event) => {
        console.error('[WebSocket] Error:', error);
      };

      this.socket.onclose = (event: WebSocketCloseEvent) => {
        console.log('[WebSocket] Closed:', event.code, event.reason);
        this.socket = null;
        this.stopHeartbeat();

        if (!this.isIntentionalClose) {
          this.setConnectionState('RECONNECTING');
          if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect();
          } else {
            console.error('[WebSocket] Max reconnection attempts reached');
            this.setConnectionState('DISCONNECTED');
          }
        } else {
          this.setConnectionState('DISCONNECTED');
        }
      };

      // Listen for app state changes to manage connection lifecycle
      this.setupAppStateListener();
    } catch (error) {
      console.error('[WebSocket] Connection failed:', error);
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect from WebSocket server
   * Does NOT clear message handlers so they persist across reconnects
   */
  disconnect(): void {
    this.isIntentionalClose = true;
    this.clearReconnectTimeout();
    this.stopHeartbeat();
    this.removeAppStateListener();

    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }

    this.userId = null;
    this.reconnectAttempts = 0;
    this.setConnectionState('DISCONNECTED');
  }

  /**
   * Acquire a connection (reference-counted).
   * Multiple hooks can call acquire — connection opens on first,
   * and only closes when the last one calls release.
   */
  acquire(userId: string): void {
    this.refCount++;
    this.connect(userId);
  }

  /**
   * Release a connection (reference-counted).
   * Only disconnects when refCount drops to 0.
   */
  release(): void {
    this.refCount = Math.max(0, this.refCount - 1);
    if (this.refCount === 0) {
      this.disconnect();
    }
  }

  /**
   * Fully clean up - disconnect and remove all handlers
   * Call this when the user logs out
   */
  destroy(): void {
    this.refCount = 0;
    this.disconnect();
    this.messageHandlers.clear();
    this.stateListeners.clear();
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected(): boolean {
    return this.socket !== null && this.socket.readyState === WebSocket.OPEN;
  }

  /**
   * Send a message to the server
   */
  send(data: string | object): void {
    if (!this.isConnected() || !this.socket) {
      console.warn('[WebSocket] Cannot send message, not connected');
      return;
    }

    try {
      const payload = typeof data === 'string' ? data : JSON.stringify(data);
      this.socket.send(payload);
    } catch (error) {
      console.error('[WebSocket] Send error:', error);
    }
  }

  /**
   * Register callback for specific event type
   * Returns an unsubscribe function
   */
  on(eventType: string, callback: MessageCallback): () => void {
    if (!this.messageHandlers.has(eventType)) {
      this.messageHandlers.set(eventType, new Set());
    }

    const handlers = this.messageHandlers.get(eventType)!;
    handlers.add(callback);

    // Return unsubscribe function
    return () => {
      handlers.delete(callback);
      // Clean up empty sets
      if (handlers.size === 0) {
        this.messageHandlers.delete(eventType);
      }
    };
  }

  /**
   * Register callback for attendance updates
   */
  onAttendanceUpdate(callback: MessageCallback): () => void {
    return this.on(WebSocketEventType.ATTENDANCE_UPDATE, callback);
  }

  /**
   * Register callback for early leave events
   */
  onEarlyLeave(callback: MessageCallback): () => void {
    return this.on(WebSocketEventType.EARLY_LEAVE, callback);
  }

  /**
   * Register callback for session start
   */
  onSessionStart(callback: MessageCallback): () => void {
    return this.on(WebSocketEventType.SESSION_START, callback);
  }

  /**
   * Register callback for session end
   */
  onSessionEnd(callback: MessageCallback): () => void {
    return this.on(WebSocketEventType.SESSION_END, callback);
  }

  /**
   * Handle incoming WebSocket message
   * Backend sends: { "event": "attendance_update", "data": {...} }
   */
  private handleMessage(event: WebSocketMessageEvent): void {
    // Reset heartbeat on any incoming message (server is alive)
    this.heartbeatFailures = 0;

    try {
      const message: WebSocketMessage = JSON.parse(event.data);

      // Handle pong response for heartbeat
      if (message.event === 'pong') {
        this.clearHeartbeatTimeout();
        return;
      }

      console.log('[WebSocket] Message received:', message.event);
      this.emit(message.event, message);
    } catch (error) {
      console.error('[WebSocket] Failed to parse message:', error);
    }
  }

  /**
   * Emit message to all registered handlers for an event type
   */
  private emit(eventType: string, message: WebSocketMessage): void {
    const handlers = this.messageHandlers.get(eventType);

    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(message);
        } catch (error) {
          console.error('[WebSocket] Handler error:', error);
        }
      });
    }
  }

  /**
   * Schedule reconnection with exponential backoff
   * Delay = min(BASE * 2^attempts, MAX)
   */
  private scheduleReconnect(): void {
    this.clearReconnectTimeout();

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WebSocket] Max reconnection attempts reached');
      this.setConnectionState('DISCONNECTED');
      return;
    }

    // Exponential backoff with jitter
    const delay = Math.min(
      BASE_RECONNECT_DELAY * Math.pow(2, this.reconnectAttempts),
      MAX_RECONNECT_DELAY
    );
    // Add random jitter (0-25% of delay)
    const jitter = Math.random() * delay * 0.25;
    const totalDelay = Math.round(delay + jitter);

    this.reconnectAttempts++;
    console.log(
      `[WebSocket] Reconnecting in ${totalDelay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`
    );

    this.reconnectTimeout = setTimeout(() => {
      if (this.userId && !this.isIntentionalClose) {
        this.connect(this.userId);
      }
    }, totalDelay);
  }

  /**
   * Clear reconnection timeout
   */
  private clearReconnectTimeout(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  /**
   * Start heartbeat ping interval
   * Sends ping every HEARTBEAT_INTERVAL; if no pong within HEARTBEAT_TIMEOUT,
   * increments failure count. After MAX_HEARTBEAT_FAILURES, triggers reconnect.
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();

    this.heartbeatInterval = setInterval(() => {
      if (!this.isConnected()) {
        return;
      }

      // Send application-level ping
      this.send({ event: 'ping', data: {} });

      // Set timeout waiting for pong
      this.heartbeatTimeout = setTimeout(() => {
        this.heartbeatFailures++;
        console.warn(
          `[WebSocket] Heartbeat timeout (failures: ${this.heartbeatFailures}/${MAX_HEARTBEAT_FAILURES})`
        );

        if (this.heartbeatFailures >= MAX_HEARTBEAT_FAILURES) {
          console.error('[WebSocket] Heartbeat failed, reconnecting...');
          // Force close to trigger reconnect
          if (this.socket) {
            this.socket.close();
          }
        }
      }, HEARTBEAT_TIMEOUT);
    }, HEARTBEAT_INTERVAL);
  }

  /**
   * Stop heartbeat interval and timeout
   */
  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    this.clearHeartbeatTimeout();
    this.heartbeatFailures = 0;
  }

  /**
   * Clear heartbeat timeout (called when pong is received)
   */
  private clearHeartbeatTimeout(): void {
    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
  }

  /**
   * Listen for app going to background/foreground
   * Disconnect when backgrounded, reconnect when foregrounded
   */
  private setupAppStateListener(): void {
    this.removeAppStateListener();

    this.appStateSubscription = AppState.addEventListener(
      'change',
      (nextAppState: AppStateStatus) => {
        if (nextAppState === 'active') {
          // App came to foreground - reconnect if needed
          if (!this.isConnected() && this.userId && !this.isIntentionalClose) {
            console.log('[WebSocket] App foregrounded, reconnecting...');
            this.reconnectAttempts = 0; // Reset backoff
            this.connect(this.userId);
          }
        } else if (nextAppState === 'background') {
          // App went to background - stop heartbeat to save battery
          this.stopHeartbeat();
        }
      }
    );
  }

  /**
   * Remove app state listener
   */
  private removeAppStateListener(): void {
    if (this.appStateSubscription) {
      this.appStateSubscription.remove();
      this.appStateSubscription = null;
    }
  }
}

// Export singleton instance
export const websocketService = new WebSocketService();
