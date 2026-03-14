import { useLocation, Link } from 'react-router-dom'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Fragment } from 'react'
import { useBreadcrumbStore } from '@/stores/breadcrumb.store'

const segmentNames: Record<string, string> = {
  dashboard: 'Dashboard',
  students: 'Students',
  faculty: 'Faculty',
  admins: 'Admins',
  users: 'Users',
  schedules: 'Schedules',
  rooms: 'Rooms',
  attendance: 'Attendance',
  analytics: 'Analytics',
  'face-registrations': 'Face Registrations',
  'early-leaves': 'Early Leaves',
  notifications: 'Notifications',
  'edge-devices': 'Edge Devices',
  'audit-logs': 'Audit Logs',
  settings: 'Settings',
  'at-risk': 'At-Risk Students',
  anomalies: 'Anomaly Detection',
}

const roleToListRoute: Record<string, { path: string; label: string }> = {
  student: { path: '/students', label: 'Students' },
  faculty: { path: '/faculty', label: 'Faculty' },
  admin: { path: '/admins', label: 'Admins' },
}

/** Check if a segment looks like a UUID (detail page parameter) */
function isUuid(segment: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(segment)
}

export function Breadcrumbs() {
  const location = useLocation()
  const segments = location.pathname.split('/').filter(Boolean)
  const stateRole = (location.state as { role?: string })?.role
  const dynamicLabel = useBreadcrumbStore((s) => s.label)

  if (segments.length === 0 || (segments.length === 1 && segments[0] === 'dashboard')) {
    return (
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbPage>Dashboard</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
    )
  }

  // Special case: /students/:studentId — student record detail
  if (segments[0] === 'students' && segments.length === 2) {
    return (
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/dashboard">Dashboard</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/students">Students</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{dynamicLabel ?? segments[1]}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
    )
  }

  // Special case: /users/:id — show role-aware breadcrumb with dynamic name
  if (segments[0] === 'users' && segments.length === 2) {
    const listRoute = roleToListRoute[stateRole ?? ''] ?? { path: '/students', label: 'Students' }
    return (
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/dashboard">Dashboard</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to={listRoute.path}>{listRoute.label}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{dynamicLabel ?? 'Details'}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
    )
  }

  return (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem>
          <BreadcrumbLink asChild>
            <Link to="/dashboard">Dashboard</Link>
          </BreadcrumbLink>
        </BreadcrumbItem>
        {segments.map((segment, index) => {
          const path = '/' + segments.slice(0, index + 1).join('/')
          const isLast = index === segments.length - 1

          // For the last segment, use dynamic label if it's a UUID (detail page)
          let name: string
          if (isLast && isUuid(segment) && dynamicLabel) {
            name = dynamicLabel
          } else if (isUuid(segment)) {
            name = dynamicLabel ?? 'Details'
          } else {
            name = segmentNames[segment] || segment.charAt(0).toUpperCase() + segment.slice(1)
          }

          return (
            <Fragment key={path}>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                {isLast ? (
                  <BreadcrumbPage>{name}</BreadcrumbPage>
                ) : (
                  <BreadcrumbLink asChild>
                    <Link to={path}>{name}</Link>
                  </BreadcrumbLink>
                )}
              </BreadcrumbItem>
            </Fragment>
          )
        })}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
