import { create } from 'zustand'
import { notificationsService } from '@/services/notifications.service'

interface NotificationState {
  unreadCount: number
  setUnreadCount: (count: number) => void
  incrementUnreadCount: () => void
  fetchUnreadCount: () => Promise<void>
}

export const useNotificationStore = create<NotificationState>((set) => ({
  unreadCount: 0,
  setUnreadCount: (count) => set({ unreadCount: count }),
  incrementUnreadCount: () => set((state) => ({ unreadCount: state.unreadCount + 1 })),
  fetchUnreadCount: async () => {
    try {
      const response = await notificationsService.unreadCount()
      set({ unreadCount: response.count || 0 })
    } catch {
      // Silently fail
    }
  },
}))
