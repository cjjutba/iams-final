import { create } from 'zustand'
import { notificationsService } from '@/services/notifications.service'

interface NotificationState {
  unreadCount: number
  unreadCriticalCount: number
  setUnreadCount: (count: number) => void
  setUnreadCriticalCount: (count: number) => void
  incrementUnreadCount: () => void
  incrementCriticalCount: () => void
  decrementUnreadCount: (wasCritical?: boolean) => void
  fetchUnreadCount: () => Promise<void>
}

export const useNotificationStore = create<NotificationState>((set) => ({
  unreadCount: 0,
  unreadCriticalCount: 0,
  setUnreadCount: (count) => set({ unreadCount: count }),
  setUnreadCriticalCount: (count) => set({ unreadCriticalCount: count }),
  incrementUnreadCount: () =>
    set((state) => ({ unreadCount: state.unreadCount + 1 })),
  incrementCriticalCount: () =>
    set((state) => ({ unreadCriticalCount: state.unreadCriticalCount + 1 })),
  // Decrements unread + (optionally) critical when a notification is cleared.
  // Pass wasCritical=true to also decrement the critical bucket — callers
  // that don't know the severity of the cleared notification should leave it
  // unset; in that case fetchUnreadCount() should be called afterwards to
  // resync from the server.
  // TODO: thread severity through markRead callsites so we don't need the
  // fetchUnreadCount() resync after every individual mark-read.
  decrementUnreadCount: (wasCritical) =>
    set((state) => ({
      unreadCount: Math.max(0, state.unreadCount - 1),
      unreadCriticalCount: wasCritical
        ? Math.max(0, state.unreadCriticalCount - 1)
        : state.unreadCriticalCount,
    })),
  fetchUnreadCount: async () => {
    try {
      const response = await notificationsService.unreadCount()
      set({
        unreadCount: response.unread_count || 0,
        unreadCriticalCount: response.unread_critical_count || 0,
      })
    } catch {
      // Silently fail
    }
  },
}))
