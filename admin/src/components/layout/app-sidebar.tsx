import { useLocation, Link } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  Calendar,
  Building2,
  ClipboardList,
  BarChart3,
  ScanFace,
  DoorOpen,
  Bell,
  Cpu,
  ScrollText,
  Settings,
  LogOut,
  ShieldCheck,
} from 'lucide-react'
import { useAuthStore } from '@/stores/auth.store'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from '@/components/ui/sidebar'

const navGroups = [
  {
    label: 'Overview',
    items: [
      { title: 'Dashboard', icon: LayoutDashboard, href: '/' },
    ],
  },
  {
    label: 'Management',
    items: [
      { title: 'Users', icon: Users, href: '/users' },
      { title: 'Schedules', icon: Calendar, href: '/schedules' },
      { title: 'Rooms', icon: Building2, href: '/rooms' },
    ],
  },
  {
    label: 'Monitoring',
    items: [
      { title: 'Attendance', icon: ClipboardList, href: '/attendance' },
      { title: 'Analytics', icon: BarChart3, href: '/analytics' },
      { title: 'Face Registrations', icon: ScanFace, href: '/face-registrations' },
      { title: 'Early Leaves', icon: DoorOpen, href: '/early-leaves' },
    ],
  },
  {
    label: 'System',
    items: [
      { title: 'Notifications', icon: Bell, href: '/notifications' },
      { title: 'Edge Devices', icon: Cpu, href: '/edge-devices' },
      { title: 'Audit Logs', icon: ScrollText, href: '/audit-logs' },
      { title: 'Settings', icon: Settings, href: '/settings' },
    ],
  },
]

export function AppSidebar() {
  const location = useLocation()
  const logout = useAuthStore((s) => s.logout)

  const isActive = (href: string) => {
    if (href === '/') return location.pathname === '/'
    return location.pathname.startsWith(href)
  }

  return (
    <Sidebar>
      <SidebarHeader className="px-4 py-3">
        <Link to="/" className="flex items-center gap-2">
          <ShieldCheck className="h-6 w-6 text-primary" />
          <span className="text-lg font-semibold">IAMS Admin</span>
        </Link>
      </SidebarHeader>
      <SidebarSeparator />
      <SidebarContent>
        {navGroups.map((group) => (
          <SidebarGroup key={group.label}>
            <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {group.items.map((item) => (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton asChild isActive={isActive(item.href)}>
                      <Link to={item.href}>
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter className="p-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={logout}>
              <LogOut className="h-4 w-4" />
              <span>Logout</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
