# Admin Dashboard Design

**Date:** 2026-03-13
**Status:** Approved

## Overview

A full admin dashboard for the IAMS system built as a standalone SPA. Provides system-wide visibility and management capabilities for administrators including user management, schedule/room configuration, attendance monitoring, analytics, and real-time alerts.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tech stack | React + Vite + TypeScript | Consistent with RN mobile app, lightweight, no SSR needed |
| UI library | shadcn/ui + Tailwind CSS | Owned components, modern look, excellent data table support |
| Architecture | Standalone SPA in `admin/` | Clean separation, no risk to existing code, simple nginx serving |
| Auth | Same Supabase Auth + JWT | Reuse existing `/api/v1/auth/login`, backend enforces admin role |
| Real-time | Hybrid (WebSocket + polling) | WebSocket for live alerts/sessions, polling for slower-changing data |
| State management | Zustand | Consistent with mobile app |
| Forms | React Hook Form + Zod | Consistent with mobile app |
| HTTP client | Axios | Consistent with mobile app |

## Project Structure

```
admin/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── components.json              # shadcn/ui config
├── public/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── routes/                  # React Router pages
│   │   ├── login.tsx
│   │   ├── dashboard.tsx
│   │   ├── users/
│   │   │   ├── index.tsx
│   │   │   └── [id].tsx
│   │   ├── schedules/
│   │   │   ├── index.tsx
│   │   │   └── [id].tsx
│   │   ├── rooms.tsx
│   │   ├── attendance.tsx
│   │   ├── analytics/
│   │   │   ├── index.tsx
│   │   │   ├── at-risk.tsx
│   │   │   └── anomalies.tsx
│   │   ├── face-registrations.tsx
│   │   ├── early-leaves.tsx
│   │   ├── notifications.tsx
│   │   ├── edge-devices.tsx
│   │   ├── audit-logs.tsx
│   │   └── settings.tsx
│   ├── components/
│   │   ├── ui/                  # shadcn/ui components
│   │   ├── layout/              # Sidebar, Header, Breadcrumbs
│   │   ├── charts/              # Recharts wrappers
│   │   └── data-tables/         # TanStack Table wrappers
│   ├── hooks/                   # useAuth, useWebSocket, useUsers, etc.
│   ├── services/                # API client (Axios)
│   │   ├── api.ts
│   │   ├── auth.service.ts
│   │   ├── users.service.ts
│   │   ├── schedules.service.ts
│   │   ├── rooms.service.ts
│   │   ├── attendance.service.ts
│   │   ├── analytics.service.ts
│   │   ├── face.service.ts
│   │   ├── notifications.service.ts
│   │   ├── edge.service.ts
│   │   └── audit.service.ts
│   ├── stores/                  # Zustand stores
│   ├── types/                   # TypeScript interfaces
│   ├── lib/                     # Utilities (cn, formatters)
│   └── styles/
│       └── globals.css
```

## Core Dependencies

- React 19 + Vite 6
- React Router v7
- shadcn/ui + Tailwind CSS v4
- TanStack Table (data tables with sorting, filtering, pagination)
- Recharts (charts and data visualization)
- Axios (HTTP client)
- Zustand (state management)
- React Hook Form + Zod (form handling)
- date-fns (date formatting)

## Authentication & Routing

### Login Flow

1. Admin visits `/login` and enters email + password
2. Calls `POST /api/v1/auth/login` and receives JWT token
3. Token stored in Zustand + `localStorage` for persistence
4. Axios interceptor attaches `Authorization: Bearer <token>` to all requests
5. 401/403 responses redirect to `/login`
6. Backend `get_current_admin()` dependency rejects non-admin users

### Route Map

| Route | Page | Access |
|-------|------|--------|
| `/login` | LoginPage | Public |
| `/` | DashboardHome | Protected |
| `/users` | UserManagement | Protected |
| `/users/:id` | UserDetail | Protected |
| `/schedules` | ScheduleManagement | Protected |
| `/schedules/:id` | ScheduleDetail | Protected |
| `/rooms` | RoomManagement | Protected |
| `/attendance` | AttendanceOverview | Protected |
| `/attendance/export` | AttendanceExport | Protected |
| `/analytics` | AnalyticsDashboard | Protected |
| `/analytics/at-risk` | AtRiskStudents | Protected |
| `/analytics/anomalies` | AnomalyDetection | Protected |
| `/face-registrations` | FaceRegistrationManagement | Protected |
| `/early-leaves` | EarlyLeaveMonitoring | Protected |
| `/notifications` | NotificationManagement | Protected |
| `/edge-devices` | EdgeDeviceMonitoring | Protected |
| `/audit-logs` | AuditLogs | Protected |
| `/settings` | SystemSettings | Protected |

All protected routes wrapped in `<ProtectedRoute>` (checks Zustand auth store) and `<DashboardLayout>` (sidebar + header).

## Layout

### Dashboard Layout

- **Sidebar:** Collapsible, grouped sections (Overview, Management, Monitoring, System), active page highlighted, logout at bottom
- **Header:** App title + logo, notification bell with unread badge (WebSocket), admin avatar + dropdown
- **Content:** Breadcrumbs + fluid main area
- **Footer:** Version + copyright

### Responsive Behavior

- Desktop: Fixed sidebar + fluid content
- Tablet: Collapsed sidebar (icons only)
- Mobile: Hidden sidebar with hamburger toggle

## Pages

### Dashboard Home (`/`)
- Stat cards: Total users, active students, faculty count, face registrations, today's attendance rate, active sessions
- Charts: Attendance trend (line, 30 days), attendance by weekday (bar), user growth (area)
- Tables: Active sessions (live via WebSocket), recent early-leave alerts (live), recent anomalies
- Quick actions: Add user, create schedule, export report

### User Management (`/users`)
- Data table: Search, filter by role/status, sortable
- Columns: Name, email, role, student ID, face registered, status, created date, actions
- Actions: View detail, deactivate/reactivate, deregister face
- Detail page: Full profile, attendance history, face registration status, engagement scores

### Schedule Management (`/schedules`)
- Data table: Filter by faculty, room, day, semester
- Columns: Subject, faculty, room, day, time, enrolled count, status, actions
- Actions: Create/edit/delete, manage enrollments
- Detail page: Enrolled students, attendance summary

### Room Management (`/rooms`)
- Data table: Filter by building, status
- Columns: Name, building, capacity, camera endpoint, active, actions
- Actions: Create/edit, configure camera endpoint, toggle active

### Attendance Overview (`/attendance`)
- Filters: Date range, schedule, student, status
- Data table: Student, schedule, date, status, check-in time, presence score
- Export: CSV/Excel via existing `/api/v1/attendance/export`

### Analytics (`/analytics`)
- System metrics cards from `/api/v1/analytics/system/metrics`
- Attendance heatmap per class
- At-risk students table
- Anomalies list with resolve action
- Predictions with risk-level indicators

### Face Registration Management (`/face-registrations`)
- Stats cards: Total registered, pending, success rate
- Data table: Student, registration date, status, actions
- Actions: View details, deregister

### Early Leave Monitoring (`/early-leaves`)
- Live feed via WebSocket
- Data table: Student, schedule, left-at, reason
- Filters: Date range, schedule, student

### Notification Management (`/notifications`)
- Send form: Target (all/role/specific user), title, message
- History table: Sent notifications with read/unread stats

### Edge Device Monitoring (`/edge-devices`)
- Status cards: Connected devices, last heartbeat, queue depth
- Device list: RPi ID, IP, status, last seen, queue stats

### Audit Logs (`/audit-logs`)
- Data table: Timestamp, admin, action, target, details
- Filters: Date range, admin, action type

### Settings (`/settings`)
- Semester config: Current semester, academic year
- Thresholds: Scan interval, miss threshold, similarity threshold
- System: Maintenance mode toggle

## Real-time & Data Fetching

### WebSocket (live critical data)
- Active sessions on dashboard
- Early-leave alerts
- Notification bell unread count
- Uses existing `/ws/{user_id}` endpoint

### Polling (semi-live)
- Dashboard stat cards: 60-second interval
- Edge device status: 30-second interval

### On-demand (user-triggered)
- All other data: Fetched on page load, refreshed on user action

### Data Fetching Pattern
- Custom hooks per domain: `useUsers()`, `useSchedules()`, `useAttendance()`, etc.
- Each hook wraps Axios + loading/error state
- Zustand for cross-page state (auth, notifications, active filters)

## New Backend Work Required

### 1. Edge Device Monitoring
- **New endpoint:** `GET /api/v1/edge/status` (admin only)
- Returns connected RPi devices, last heartbeat, queue depth
- Requires edge heartbeat pings

### 2. Audit Logs
- **New model:** `audit_logs` table (admin_id, action, target_type, target_id, details, timestamp)
- **New endpoint:** `GET /api/v1/audit/logs` (admin only, paginated, filterable)
- **Middleware:** Auto-log admin write operations

### 3. System Settings
- **New model:** `system_settings` table (key, value, updated_by, updated_at)
- **New endpoints:** `GET /api/v1/settings`, `PATCH /api/v1/settings` (admin only)

### 4. Broadcast Notifications
- **New endpoint:** `POST /api/v1/notifications/broadcast` (admin only)
- Target: All users, by role, or specific user

## Deployment

- Admin app builds to `admin/dist/`
- Update `deploy/nginx.conf` to serve static files at `/admin`
- Update `deploy/docker-compose.prod.yml` to include admin build step
- nginx serves `admin/dist/` for `/admin/*` routes, proxies `/api/` to backend
