/**
 * Notification Service
 *
 * Handles all notification-related API calls:
 * - Retrieving user notifications (with optional unread-only filter)
 * - Marking individual notifications as read
 * - Marking all notifications as read
 * - Getting unread notification count
 *
 * All endpoints are relative to the base URL configured in api.ts.
 * Backend router prefix: /notifications
 *
 * IMPORTANT: The backend returns response data directly from the
 * Pydantic response_model -- there is NO generic ApiResponse wrapper.
 *
 * @see backend/app/routers/notifications.py
 * @see backend/app/schemas/notification.py
 */

import { api } from '../utils/api';

// ---------------------------------------------------------------------------
// Response types matching backend Pydantic schemas
// ---------------------------------------------------------------------------

/**
 * Notification object returned by the backend.
 * Maps to backend NotificationResponse schema.
 */
export interface Notification {
  id: string;
  user_id: string;
  title: string;
  message: string;
  type: string;
  read: boolean;
  read_at: string | null;
  reference_id: string | null;
  reference_type: string | null;
  created_at: string;
}

/** Response from mark-all-read endpoint */
interface MarkAllReadResponse {
  success: boolean;
  message: string;
}

/** Response from unread-count endpoint */
interface UnreadCountResponse {
  unread_count: number;
}

// ---------------------------------------------------------------------------
// Request parameter interfaces
// ---------------------------------------------------------------------------

/** Optional parameters for listing notifications */
interface GetNotificationsParams {
  /** Only return unread notifications (default: false) */
  unread_only?: boolean;
  /** Number of records to skip for pagination (default: 0) */
  skip?: number;
  /** Maximum number of records to return (default: 50, max: 200) */
  limit?: number;
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

export const notificationService = {
  /**
   * Get notifications for the current authenticated user.
   *
   * @param params - Optional filters and pagination
   * @returns Array of notifications, most recent first
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /notifications/?unread_only=...&skip=...&limit=...
   * Response: List[NotificationResponse]
   */
  async getNotifications(
    params?: GetNotificationsParams,
  ): Promise<Notification[]> {
    const response = await api.get<Notification[]>('/notifications/', {
      params: params
        ? {
            ...(params.unread_only !== undefined && { unread_only: params.unread_only }),
            ...(params.skip !== undefined && { skip: params.skip }),
            ...(params.limit !== undefined && { limit: params.limit }),
          }
        : undefined,
    });
    return response.data;
  },

  /**
   * Mark a specific notification as read.
   *
   * Only the notification owner can mark it as read.
   *
   * @param notificationId - The notification UUID
   * @returns The updated notification
   * @throws AxiosError (404 if not found, 403 if access denied)
   *
   * Backend: PATCH /notifications/{notificationId}/read
   * Response: NotificationResponse
   */
  async markAsRead(notificationId: string): Promise<Notification> {
    const response = await api.patch<Notification>(
      `/notifications/${notificationId}/read`,
    );
    return response.data;
  },

  /**
   * Mark all unread notifications as read for the current user.
   *
   * @returns Success confirmation with count of marked notifications
   * @throws AxiosError on network or auth errors
   *
   * Backend: POST /notifications/read-all
   * Response: { success: boolean, message: string }
   */
  async markAllAsRead(): Promise<MarkAllReadResponse> {
    const response = await api.post<MarkAllReadResponse>(
      '/notifications/read-all',
    );
    return response.data;
  },

  /**
   * Get the count of unread notifications for the current user.
   * Useful for badge counts in the UI.
   *
   * @returns Object with unread_count field
   * @throws AxiosError on network or auth errors
   *
   * Backend: GET /notifications/unread-count
   * Response: { unread_count: number }
   */
  async getUnreadCount(): Promise<number> {
    const response = await api.get<UnreadCountResponse>(
      '/notifications/unread-count',
    );
    return response.data.unread_count;
  },
};
