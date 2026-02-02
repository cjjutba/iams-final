/**
 * WebSocket Service
 *
 * Manages WebSocket connection for real-time updates:
 * - Attendance updates
 * - Early leave alerts
 * - Session events
 * - Automatic reconnection
 */

import { config } from '../constants';
import type { WebSocketMessage, WebSocketEventType } from '../types';

type MessageCallback = (message: WebSocketMessage) => void;

class WebSocketService {
  private socket: WebSocket | null = null;
  private userId: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = config.WS_MAX_RECONNECT_ATTEMPTS;
  private reconnectInterval = config.WS_RECONNECT_INTERVAL;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private messageHandlers: Map<WebSocketEventType, MessageCallback[]> = new Map();
  private isIntentionalClose = false;

  /**
   * Connect to WebSocket server
   */
  connect(userId: string): void {
    this.userId = userId;
    this.isIntentionalClose = false;

    try {
      const wsUrl = `${config.WS_URL}/${userId}`;
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        console.log('[WebSocket] Connected');
        this.reconnectAttempts = 0;
        this.emit('connected', { type: 'connected', data: { userId } });
      };

      this.socket.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          console.log('[WebSocket] Message received:', message);
          this.emit(message.type, message);
        } catch (error) {
          console.error('[WebSocket] Failed to parse message:', error);
        }
      };

      this.socket.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
      };

      this.socket.onclose = (event) => {
        console.log('[WebSocket] Closed:', event.code, event.reason);
        this.socket = null;

        // Attempt reconnection if not intentional close
        if (!this.isIntentionalClose && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect();
        }
      };
    } catch (error) {
      console.error('[WebSocket] Connection failed:', error);
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.isIntentionalClose = true;
    this.clearReconnectTimeout();

    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }

    this.userId = null;
    this.messageHandlers.clear();
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected(): boolean {
    return this.socket !== null && this.socket.readyState === WebSocket.OPEN;
  }

  /**
   * Register callback for specific event type
   */
  on(eventType: WebSocketEventType, callback: MessageCallback): () => void {
    if (!this.messageHandlers.has(eventType)) {
      this.messageHandlers.set(eventType, []);
    }

    const handlers = this.messageHandlers.get(eventType)!;
    handlers.push(callback);

    // Return unsubscribe function
    return () => {
      const index = handlers.indexOf(callback);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    };
  }

  /**
   * Register callback for attendance updates
   */
  onAttendanceUpdate(callback: MessageCallback): () => void {
    return this.on('attendance_update', callback);
  }

  /**
   * Register callback for early leave events
   */
  onEarlyLeave(callback: MessageCallback): () => void {
    return this.on('early_leave', callback);
  },

  /**
   * Register callback for session start
   */
  onSessionStart(callback: MessageCallback): () => void {
    return this.on('session_start', callback);
  }

  /**
   * Register callback for session end
   */
  onSessionEnd(callback: MessageCallback): () => void {
    return this.on('session_end', callback);
  }

  /**
   * Emit message to all registered handlers
   */
  private emit(eventType: WebSocketEventType, message: WebSocketMessage): void {
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
   * Schedule reconnection attempt
   */
  private scheduleReconnect(): void {
    this.clearReconnectTimeout();

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WebSocket] Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    console.log(
      `[WebSocket] Reconnecting in ${this.reconnectInterval}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`
    );

    this.reconnectTimeout = setTimeout(() => {
      if (this.userId) {
        this.connect(this.userId);
      }
    }, this.reconnectInterval);
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
}

// Export singleton instance
export const websocketService = new WebSocketService();
