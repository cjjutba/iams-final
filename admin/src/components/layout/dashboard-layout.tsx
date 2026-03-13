import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { SidebarProvider, SidebarInset } from '@/components/ui/sidebar'
import { AppSidebar } from './app-sidebar'
import { Header } from './header'
import { useWebSocket } from '@/hooks/use-websocket'
import { useNotificationStore } from '@/stores/notification.store'

export function DashboardLayout() {
  const { fetchUnreadCount } = useNotificationStore()

  useEffect(() => { fetchUnreadCount() }, [fetchUnreadCount])

  useWebSocket((data) => {
    if (data.type === 'notification' || data.type === 'early_leave_alert') {
      useNotificationStore.getState().incrementUnreadCount()
    }
  })

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <Header />
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
