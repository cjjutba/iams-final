/**
 * Notification Store
 *
 * Zustand store for managing notification unread count.
 * Used by Header badge and notification WebSocket hook.
 */

import { create } from 'zustand';
import { notificationService } from '../services/notificationService';

interface NotificationState {
  unreadCount: number;
  setUnreadCount: (count: number) => void;
  incrementUnreadCount: () => void;
  decrementUnreadCount: () => void;
  fetchUnreadCount: () => Promise<void>;
}

export const useNotificationStore = create<NotificationState>((set) => ({
  unreadCount: 0,
  setUnreadCount: (count) => set({ unreadCount: count }),
  incrementUnreadCount: () => set((s) => ({ unreadCount: s.unreadCount + 1 })),
  decrementUnreadCount: () =>
    set((s) => ({ unreadCount: Math.max(0, s.unreadCount - 1) })),
  fetchUnreadCount: async () => {
    try {
      const count = await notificationService.getUnreadCount();
      set({ unreadCount: count });
    } catch {
      // Silently fail — badge will show stale count
    }
  },
}));
