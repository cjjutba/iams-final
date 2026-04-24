import { useLocation, Link } from 'react-router-dom'
import {
  LayoutDashboard,
  GraduationCap,
  UserCog,
  ShieldAlert,
  Calendar,
  Building2,
  ClipboardList,
  BarChart3,
  DoorOpen,
  ScanSearch,
  Activity,
  Shield,
  Settings,
  LogOut,
  ShieldCheck,
} from 'lucide-react'
import { toast } from 'sonner'
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
} from '@/components/ui/sidebar'

const navGroups = [
  {
    label: 'Overview',
    items: [
      { title: 'Dashboard', icon: LayoutDashboard, href: '/dashboard' },
    ],
  },
  {
    label: 'People',
    items: [
      { title: 'Students', icon: GraduationCap, href: '/students' },
      { title: 'Faculty', icon: UserCog, href: '/faculty' },
      { title: 'Admins', icon: ShieldAlert, href: '/admins' },
    ],
  },
  {
    label: 'Management',
    items: [
      { title: 'Schedules', icon: Calendar, href: '/schedules' },
      { title: 'Rooms', icon: Building2, href: '/rooms' },
    ],
  },
  {
    label: 'Monitoring',
    items: [
      { title: 'Attendance', icon: ClipboardList, href: '/attendance' },
      { title: 'Analytics', icon: BarChart3, href: '/analytics' },
      { title: 'Early Leaves', icon: DoorOpen, href: '/early-leaves' },
      { title: 'Recognitions', icon: ScanSearch, href: '/recognitions' },
      { title: 'System Activity', icon: Activity, href: '/activity' },
    ],
  },
  {
    label: 'System',
    items: [
      {
        title: 'Recognition Access',
        icon: Shield,
        href: '/audit/recognition-access',
      },
      { title: 'Settings', icon: Settings, href: '/settings' },
    ],
  },
]

export function AppSidebar() {
  const location = useLocation()
  const logout = useAuthStore((s) => s.logout)

  const handleLogout = () => {
    logout()
    toast.success('Signed out successfully')
  }

  const isActive = (href: string) => {
    if (href === '/dashboard') return location.pathname === '/dashboard' || location.pathname === '/'
    if (location.pathname.startsWith(href)) return true

    // Map detail routes back to their parent sidebar item
    const state = location.state as Record<string, string> | null
    if (location.pathname.startsWith('/users/') && state?.role) {
      const roleToHref: Record<string, string> = {
        student: '/students',
        faculty: '/faculty',
        admin: '/admins',
      }
      return roleToHref[state.role] === href
    }

    return false
  }

  return (
    <Sidebar>
      <SidebarHeader className="px-4 py-3 border-b border-sidebar-border">
        <Link to="/dashboard" className="flex items-center gap-2">
          <ShieldCheck className="h-6 w-6 text-primary" />
          <span className="text-lg font-semibold">IAMS Admin</span>
        </Link>
      </SidebarHeader>
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
            <SidebarMenuButton onClick={handleLogout}>
              <LogOut className="h-4 w-4" />
              <span>Logout</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
