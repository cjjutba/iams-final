# Admin Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a full admin dashboard web app for the IAMS system using React + Vite + TypeScript with shadcn/ui.

**Architecture:** Standalone SPA in `admin/` directory. Communicates with existing FastAPI backend via REST API + WebSocket. Deployed as static files served by nginx alongside the backend.

**Tech Stack:** React 19, Vite 6, TypeScript, Tailwind CSS v4, shadcn/ui, TanStack Table, Recharts, Axios, Zustand, React Hook Form + Zod, React Router v7, date-fns

**Design Doc:** `docs/plans/2026-03-13-admin-dashboard-design.md`

---

## Task 1: Project Scaffolding

**Files:**
- Create: `admin/package.json`
- Create: `admin/vite.config.ts`
- Create: `admin/tsconfig.json`
- Create: `admin/tsconfig.app.json`
- Create: `admin/tsconfig.node.json`
- Create: `admin/index.html`
- Create: `admin/src/main.tsx`
- Create: `admin/src/App.tsx`
- Create: `admin/src/styles/globals.css`
- Create: `admin/tailwind.config.ts`
- Create: `admin/components.json`
- Create: `admin/src/lib/utils.ts`
- Create: `admin/src/vite-env.d.ts`

**Step 1: Scaffold Vite + React + TypeScript project**

```bash
cd /Users/cjjutba/Projects/iams
npm create vite@latest admin -- --template react-ts
```

**Step 2: Install core dependencies**

```bash
cd /Users/cjjutba/Projects/iams/admin
npm install react-router-dom@7 axios zustand react-hook-form @hookform/resolvers zod recharts @tanstack/react-table date-fns lucide-react clsx tailwind-merge class-variance-authority
```

**Step 3: Install Tailwind CSS v4**

```bash
cd /Users/cjjutba/Projects/iams/admin
npm install -D tailwindcss @tailwindcss/vite
```

**Step 4: Configure Tailwind in vite.config.ts**

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
```

**Step 5: Configure globals.css for Tailwind v4**

```css
@import "tailwindcss";

@theme {
  --color-background: oklch(1 0 0);
  --color-foreground: oklch(0.145 0 0);
  --color-card: oklch(1 0 0);
  --color-card-foreground: oklch(0.145 0 0);
  --color-popover: oklch(1 0 0);
  --color-popover-foreground: oklch(0.145 0 0);
  --color-primary: oklch(0.205 0 0);
  --color-primary-foreground: oklch(0.985 0 0);
  --color-secondary: oklch(0.97 0 0);
  --color-secondary-foreground: oklch(0.205 0 0);
  --color-muted: oklch(0.97 0 0);
  --color-muted-foreground: oklch(0.556 0 0);
  --color-accent: oklch(0.97 0 0);
  --color-accent-foreground: oklch(0.205 0 0);
  --color-destructive: oklch(0.577 0.245 27.325);
  --color-destructive-foreground: oklch(0.577 0.245 27.325);
  --color-border: oklch(0.922 0 0);
  --color-input: oklch(0.922 0 0);
  --color-ring: oklch(0.708 0 0);
  --color-chart-1: oklch(0.646 0.222 41.116);
  --color-chart-2: oklch(0.6 0.118 184.704);
  --color-chart-3: oklch(0.398 0.07 227.392);
  --color-chart-4: oklch(0.828 0.189 84.429);
  --color-chart-5: oklch(0.769 0.188 70.08);
  --color-sidebar: oklch(0.985 0 0);
  --color-sidebar-foreground: oklch(0.145 0 0);
  --color-sidebar-primary: oklch(0.205 0 0);
  --color-sidebar-primary-foreground: oklch(0.985 0 0);
  --color-sidebar-accent: oklch(0.97 0 0);
  --color-sidebar-accent-foreground: oklch(0.205 0 0);
  --color-sidebar-border: oklch(0.922 0 0);
  --color-sidebar-ring: oklch(0.708 0 0);
  --radius: 0.625rem;
}
```

**Step 6: Initialize shadcn/ui**

```bash
cd /Users/cjjutba/Projects/iams/admin
npx shadcn@latest init
```

Select: New York style, Neutral color, CSS variables.

**Step 7: Install essential shadcn/ui components**

```bash
cd /Users/cjjutba/Projects/iams/admin
npx shadcn@latest add button input label card table badge dialog dropdown-menu separator sheet avatar tabs select command popover calendar form toast sidebar breadcrumb skeleton alert-dialog textarea switch tooltip checkbox scroll-area
```

**Step 8: Create utils.ts**

```ts
// src/lib/utils.ts
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

**Step 9: Create placeholder App.tsx**

```tsx
// src/App.tsx
function App() {
  return <div className="p-8"><h1 className="text-2xl font-bold">IAMS Admin Dashboard</h1></div>
}
export default App
```

**Step 10: Verify dev server starts**

```bash
cd /Users/cjjutba/Projects/iams/admin
npm run dev
```

Expected: Vite dev server running at http://localhost:5173, showing "IAMS Admin Dashboard".

**Step 11: Commit**

```bash
git add admin/
git commit -m "feat(admin): scaffold Vite + React + TypeScript + shadcn/ui project"
```

---

## Task 2: TypeScript Types

**Files:**
- Create: `admin/src/types/auth.ts`
- Create: `admin/src/types/user.ts`
- Create: `admin/src/types/schedule.ts`
- Create: `admin/src/types/room.ts`
- Create: `admin/src/types/attendance.ts`
- Create: `admin/src/types/analytics.ts`
- Create: `admin/src/types/face.ts`
- Create: `admin/src/types/notification.ts`
- Create: `admin/src/types/index.ts`

Mirror the backend Pydantic schemas as TypeScript interfaces. Reference:
- `backend/app/schemas/user.py` — `UserResponse`, `UserCreate`, `UserUpdate`
- `backend/app/schemas/schedule.py` — `ScheduleResponse`, `ScheduleCreate`, `ScheduleUpdate`
- `backend/app/schemas/attendance.py` — `AttendanceRecordResponse`, `LiveAttendanceResponse`, `AlertResponse`, `ScheduleAttendanceSummaryItem`
- `backend/app/schemas/analytics.py` — `SystemMetrics`
- `backend/app/schemas/notification.py` — notification schemas
- `backend/app/schemas/face.py` — face registration schemas

**Step 1: Create all type files**

```ts
// src/types/auth.ts
export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: UserResponse
}

export interface AuthUser {
  id: string
  email: string
  first_name: string
  last_name: string
  role: 'student' | 'faculty' | 'admin'
}

import type { UserResponse } from './user'
```

```ts
// src/types/user.ts
export type UserRole = 'student' | 'faculty' | 'admin'

export interface UserResponse {
  id: string
  email: string
  first_name: string
  last_name: string
  phone: string | null
  role: UserRole
  student_id: string | null
  is_active: boolean
  email_verified: boolean
  created_at: string
}

export interface UserCreate {
  email: string
  first_name: string
  last_name: string
  phone?: string
  password: string
  role: UserRole
  student_id?: string
}

export interface UserUpdate {
  email?: string
  first_name?: string
  last_name?: string
  phone?: string
}

export interface UserStatistics {
  total_users: number
  total_students: number
  total_faculty: number
  total_admins: number
  active_users: number
  inactive_users: number
}
```

```ts
// src/types/schedule.ts
import type { UserResponse } from './user'

export interface RoomInfo {
  id: string
  name: string
  building: string | null
  capacity: number | null
}

export interface ScheduleResponse {
  id: string
  subject_code: string
  subject_name: string
  day_of_week: number
  start_time: string
  end_time: string
  semester: string
  academic_year: string
  target_course: string | null
  target_year_level: number | null
  faculty_id: string
  room_id: string
  is_active: boolean
  faculty: UserResponse | null
  room: RoomInfo | null
}

export interface ScheduleCreate {
  subject_code: string
  subject_name: string
  day_of_week: number
  start_time: string
  end_time: string
  semester: string
  academic_year: string
  target_course?: string
  target_year_level?: number
  faculty_id: string
  room_id: string
}

export interface ScheduleUpdate {
  subject_code?: string
  subject_name?: string
  day_of_week?: number
  start_time?: string
  end_time?: string
  semester?: string
  academic_year?: string
  target_course?: string
  target_year_level?: number
  faculty_id?: string
  room_id?: string
  is_active?: boolean
}
```

```ts
// src/types/room.ts
export interface Room {
  id: string
  name: string
  building: string | null
  capacity: number | null
  camera_endpoint: string | null
  is_active: boolean
}

export interface RoomCreate {
  name: string
  building?: string
  capacity?: number
  camera_endpoint?: string
}

export interface RoomUpdate {
  name?: string
  building?: string
  capacity?: number
  camera_endpoint?: string
  is_active?: boolean
}
```

```ts
// src/types/attendance.ts
export type AttendanceStatus = 'PRESENT' | 'LATE' | 'ABSENT' | 'EXCUSED' | 'EARLY_LEAVE'

export interface AttendanceRecord {
  id: string
  student_id: string
  schedule_id: string
  date: string
  status: AttendanceStatus
  check_in_time: string | null
  check_out_time: string | null
  presence_score: number
  total_scans: number
  scans_present: number
  remarks: string | null
  student_name: string | null
  subject_code: string | null
}

export interface ScheduleAttendanceSummary {
  schedule_id: string
  subject_code: string
  subject_name: string
  start_time: string
  end_time: string
  room_name: string | null
  session_active: boolean
  total_enrolled: number
  present_count: number
  late_count: number
  absent_count: number
  attendance_rate: number
}

export interface LiveAttendanceResponse {
  schedule_id: string
  subject_code: string
  subject_name: string
  date: string
  start_time: string
  end_time: string
  session_active: boolean
  total_enrolled: number
  present_count: number
  late_count: number
  absent_count: number
  early_leave_count: number
  students: StudentAttendanceStatus[]
}

export interface StudentAttendanceStatus {
  student_id: string
  student_name: string
  status: AttendanceStatus
  check_in_time: string | null
  presence_score: number
}

export interface EarlyLeaveAlert {
  id: string
  attendance_id: string
  student_id: string
  student_name: string
  student_student_id: string | null
  schedule_id: string
  subject_code: string
  subject_name: string
  detected_at: string
  last_seen_at: string
  consecutive_misses: number
  notified: boolean
  date: string
}
```

```ts
// src/types/analytics.ts
export interface SystemMetrics {
  total_students: number
  total_faculty: number
  total_schedules: number
  total_attendance_records: number
  average_attendance_rate: number
  total_anomalies: number
  unresolved_anomalies: number
  total_early_leaves: number
}

export interface AttendanceAnomaly {
  id: string
  student_id: string
  anomaly_type: 'FREQUENT_ABSENTEE' | 'CHRONIC_ABSENTEE' | 'PATTERN_CHANGE'
  severity: string
  description: string
  resolved: boolean
  detected_at: string
  resolved_by: string | null
  resolved_at: string | null
}

export interface AtRiskStudent {
  student_id: string
  student_name: string
  attendance_rate: number
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH'
  missed_classes: number
}
```

```ts
// src/types/face.ts
export interface FaceRegistration {
  id: string
  user_id: string
  embedding_id: string
  registered_at: string
  is_active: boolean
}

export interface FaceStatistics {
  total_registered: number
  total_active: number
  total_inactive: number
}
```

```ts
// src/types/notification.ts
export interface Notification {
  id: string
  user_id: string
  type: string
  title: string
  message: string
  read: boolean
  created_at: string
}

export interface BroadcastNotificationRequest {
  target: 'all' | 'students' | 'faculty' | 'admin'
  target_user_id?: string
  title: string
  message: string
}
```

```ts
// src/types/index.ts
export * from './auth'
export * from './user'
export * from './schedule'
export * from './room'
export * from './attendance'
export * from './analytics'
export * from './face'
export * from './notification'

export interface ApiResponse<T> {
  success: boolean
  data?: T
  message?: string
  error?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd /Users/cjjutba/Projects/iams/admin
npx tsc --noEmit
```

Expected: No errors.

**Step 3: Commit**

```bash
git add admin/src/types/
git commit -m "feat(admin): add TypeScript type definitions mirroring backend schemas"
```

---

## Task 3: API Client & Services

**Files:**
- Create: `admin/src/services/api.ts`
- Create: `admin/src/services/auth.service.ts`
- Create: `admin/src/services/users.service.ts`
- Create: `admin/src/services/schedules.service.ts`
- Create: `admin/src/services/rooms.service.ts`
- Create: `admin/src/services/attendance.service.ts`
- Create: `admin/src/services/analytics.service.ts`
- Create: `admin/src/services/face.service.ts`
- Create: `admin/src/services/notifications.service.ts`

**Step 1: Create Axios instance with interceptors**

```ts
// src/services/api.ts
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
```

**Step 2: Create auth service**

```ts
// src/services/auth.service.ts
import api from './api'
import type { LoginRequest, LoginResponse } from '@/types'

export const authService = {
  login: (data: LoginRequest) =>
    api.post<LoginResponse>('/auth/login', data).then(r => r.data),

  me: () =>
    api.get('/auth/me').then(r => r.data),

  logout: () =>
    api.post('/auth/logout').then(r => r.data),

  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post('/auth/change-password', data).then(r => r.data),
}
```

**Step 3: Create users service**

Map to endpoints in `backend/app/routers/users.py`.

```ts
// src/services/users.service.ts
import api from './api'
import type { UserResponse, UserUpdate, UserRole, UserStatistics } from '@/types'

export const usersService = {
  list: (params?: { skip?: number; limit?: number; role?: UserRole }) =>
    api.get<UserResponse[]>('/users', { params }).then(r => r.data),

  getById: (id: string) =>
    api.get<UserResponse>(`/users/${id}`).then(r => r.data),

  update: (id: string, data: UserUpdate) =>
    api.patch<UserResponse>(`/users/${id}`, data).then(r => r.data),

  deactivate: (id: string) =>
    api.delete(`/users/${id}`).then(r => r.data),

  reactivate: (id: string) =>
    api.post(`/users/${id}/reactivate`).then(r => r.data),

  statistics: () =>
    api.get<{ success: boolean; data: UserStatistics }>('/users/statistics').then(r => r.data),
}
```

**Step 4: Create schedules service**

Map to endpoints in `backend/app/routers/schedules.py`.

```ts
// src/services/schedules.service.ts
import api from './api'
import type { ScheduleResponse, ScheduleCreate, ScheduleUpdate } from '@/types'

export const schedulesService = {
  list: (params?: { day?: number }) =>
    api.get<ScheduleResponse[]>('/schedules', { params }).then(r => r.data),

  getById: (id: string) =>
    api.get<ScheduleResponse>(`/schedules/${id}`).then(r => r.data),

  getEnrolledStudents: (id: string) =>
    api.get(`/schedules/${id}/students`).then(r => r.data),

  create: (data: ScheduleCreate) =>
    api.post<ScheduleResponse>('/schedules', data).then(r => r.data),

  update: (id: string, data: ScheduleUpdate) =>
    api.patch<ScheduleResponse>(`/schedules/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/schedules/${id}`).then(r => r.data),
}
```

**Step 5: Create rooms service**

Note: Backend currently only has a lookup endpoint (`backend/app/routers/rooms.py`). Room CRUD endpoints need to be created as part of Task 14 (new backend work). For now, stub the service with the lookup endpoint and add CRUD methods that will be wired up later.

```ts
// src/services/rooms.service.ts
import api from './api'
import type { Room, RoomCreate, RoomUpdate } from '@/types'

export const roomsService = {
  list: () =>
    api.get<Room[]>('/rooms').then(r => r.data),

  getById: (id: string) =>
    api.get<Room>(`/rooms/${id}`).then(r => r.data),

  create: (data: RoomCreate) =>
    api.post<Room>('/rooms', data).then(r => r.data),

  update: (id: string, data: RoomUpdate) =>
    api.patch<Room>(`/rooms/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/rooms/${id}`).then(r => r.data),

  lookup: (name: string) =>
    api.get('/rooms/lookup', { params: { name } }).then(r => r.data),
}
```

**Step 6: Create attendance service**

Map to endpoints in `backend/app/routers/attendance.py`.

```ts
// src/services/attendance.service.ts
import api from './api'
import type { AttendanceRecord, ScheduleAttendanceSummary, LiveAttendanceResponse, EarlyLeaveAlert } from '@/types'

export const attendanceService = {
  list: (params?: { schedule_id?: string; start_date?: string; end_date?: string; status?: string; skip?: number; limit?: number }) =>
    api.get<AttendanceRecord[]>('/attendance', { params }).then(r => r.data),

  getById: (id: string) =>
    api.get<AttendanceRecord>(`/attendance/${id}`).then(r => r.data),

  getScheduleSummaries: (targetDate?: string) =>
    api.get<ScheduleAttendanceSummary[]>('/attendance/schedule-summaries', { params: { target_date: targetDate } }).then(r => r.data),

  getScheduleAttendance: (scheduleId: string, date?: string) =>
    api.get<AttendanceRecord[]>(`/attendance/schedule/${scheduleId}`, { params: { date } }).then(r => r.data),

  getScheduleSummary: (scheduleId: string, startDate?: string, endDate?: string) =>
    api.get(`/attendance/schedule/${scheduleId}/summary`, { params: { start_date: startDate, end_date: endDate } }).then(r => r.data),

  getLive: (scheduleId: string) =>
    api.get<LiveAttendanceResponse>(`/attendance/live/${scheduleId}`).then(r => r.data),

  getAlerts: (params?: { filter?: string; schedule_id?: string }) =>
    api.get<EarlyLeaveAlert[]>('/attendance/alerts', { params }).then(r => r.data),

  getEarlyLeaves: () =>
    api.get('/attendance/early-leaves').then(r => r.data),

  export: (params: { schedule_id?: string; start_date?: string; end_date?: string; format?: 'csv' | 'json' }) =>
    api.get('/attendance/export', { params, responseType: params.format === 'csv' ? 'blob' : 'json' }).then(r => r.data),

  update: (id: string, data: { status?: string; remarks?: string }) =>
    api.patch<AttendanceRecord>(`/attendance/${id}`, data).then(r => r.data),

  getPresenceLogs: (attendanceId: string) =>
    api.get(`/attendance/${attendanceId}/logs`).then(r => r.data),
}
```

**Step 7: Create analytics service**

```ts
// src/services/analytics.service.ts
import api from './api'
import type { SystemMetrics, AttendanceAnomaly, AtRiskStudent } from '@/types'

export const analyticsService = {
  systemMetrics: () =>
    api.get<{ success: boolean; data: SystemMetrics }>('/analytics/system/metrics').then(r => r.data),

  classOverview: (scheduleId: string) =>
    api.get(`/analytics/class/${scheduleId}`).then(r => r.data),

  heatmap: (scheduleId: string) =>
    api.get(`/analytics/class/${scheduleId}/heatmap`).then(r => r.data),

  ranking: (scheduleId: string) =>
    api.get(`/analytics/class/${scheduleId}/ranking`).then(r => r.data),

  atRisk: () =>
    api.get<AtRiskStudent[]>('/analytics/at-risk').then(r => r.data),

  anomalies: () =>
    api.get<AttendanceAnomaly[]>('/analytics/anomalies').then(r => r.data),

  resolveAnomaly: (id: string) =>
    api.patch(`/analytics/anomalies/${id}/resolve`).then(r => r.data),

  predictions: (scheduleId: string) =>
    api.get(`/analytics/predictions/${scheduleId}`).then(r => r.data),
}
```

**Step 8: Create face service**

```ts
// src/services/face.service.ts
import api from './api'
import type { FaceStatistics } from '@/types'

export const faceService = {
  statistics: () =>
    api.get<{ success: boolean; data: FaceStatistics }>('/face/statistics').then(r => r.data),

  deregister: (userId: string) =>
    api.delete(`/face/${userId}`).then(r => r.data),
}
```

**Step 9: Create notifications service**

```ts
// src/services/notifications.service.ts
import api from './api'
import type { Notification, BroadcastNotificationRequest } from '@/types'

export const notificationsService = {
  list: () =>
    api.get<Notification[]>('/notifications').then(r => r.data),

  markRead: (id: string) =>
    api.patch(`/notifications/${id}/read`).then(r => r.data),

  markAllRead: () =>
    api.post('/notifications/read-all').then(r => r.data),

  unreadCount: () =>
    api.get<{ count: number }>('/notifications/unread-count').then(r => r.data),

  broadcast: (data: BroadcastNotificationRequest) =>
    api.post('/notifications/broadcast', data).then(r => r.data),
}
```

**Step 10: Verify TypeScript compiles**

```bash
cd /Users/cjjutba/Projects/iams/admin
npx tsc --noEmit
```

**Step 11: Commit**

```bash
git add admin/src/services/
git commit -m "feat(admin): add API client and service layer for all backend endpoints"
```

---

## Task 4: Auth Store & Protected Routes

**Files:**
- Create: `admin/src/stores/auth.store.ts`
- Create: `admin/src/components/protected-route.tsx`
- Create: `admin/src/routes/login.tsx`

**Step 1: Create Zustand auth store**

```ts
// src/stores/auth.store.ts
import { create } from 'zustand'
import type { AuthUser } from '@/types'
import { authService } from '@/services/auth.service'

interface AuthState {
  user: AuthUser | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('access_token'),
  isLoading: true,
  isAuthenticated: false,

  login: async (email, password) => {
    const response = await authService.login({ email, password })
    const { access_token, user } = response
    if (user.role !== 'admin') {
      throw new Error('Access denied. Admin role required.')
    }
    localStorage.setItem('access_token', access_token)
    set({ user, token: access_token, isAuthenticated: true })
  },

  logout: () => {
    localStorage.removeItem('access_token')
    set({ user: null, token: null, isAuthenticated: false })
  },

  checkAuth: async () => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      set({ isLoading: false, isAuthenticated: false })
      return
    }
    try {
      const response = await authService.me()
      const user = response.user || response
      if (user.role !== 'admin') {
        localStorage.removeItem('access_token')
        set({ user: null, token: null, isLoading: false, isAuthenticated: false })
        return
      }
      set({ user, token, isLoading: false, isAuthenticated: true })
    } catch {
      localStorage.removeItem('access_token')
      set({ user: null, token: null, isLoading: false, isAuthenticated: false })
    }
  },
}))
```

**Step 2: Create ProtectedRoute component**

```tsx
// src/components/protected-route.tsx
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth.store'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthStore()

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
```

**Step 3: Create Login page**

```tsx
// src/routes/login.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuthStore } from '@/stores/auth.store'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
})

type LoginForm = z.infer<typeof loginSchema>

export default function LoginPage() {
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)
  const [error, setError] = useState('')
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginForm) => {
    try {
      setError('')
      await login(data.email, data.password)
      navigate('/')
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Login failed')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/50">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">IAMS Admin</CardTitle>
          <CardDescription>Sign in to manage the attendance system</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {error && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
            )}
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" placeholder="admin@jrmsu.edu.ph" {...register('email')} />
              {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" {...register('password')} />
              {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
            </div>
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? 'Signing in...' : 'Sign In'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
```

**Step 4: Verify it renders**

```bash
cd /Users/cjjutba/Projects/iams/admin
npm run dev
```

**Step 5: Commit**

```bash
git add admin/src/stores/ admin/src/components/protected-route.tsx admin/src/routes/login.tsx
git commit -m "feat(admin): add auth store, protected routes, and login page"
```

---

## Task 5: Dashboard Layout (Sidebar + Header)

**Files:**
- Create: `admin/src/components/layout/dashboard-layout.tsx`
- Create: `admin/src/components/layout/app-sidebar.tsx`
- Create: `admin/src/components/layout/header.tsx`
- Create: `admin/src/components/layout/breadcrumbs.tsx`

**Step 1: Create AppSidebar**

Use shadcn/ui `Sidebar` component. Reference the sidebar navigation groups from the design doc:
- **Overview:** Dashboard
- **Management:** Users, Schedules, Rooms
- **Monitoring:** Attendance, Analytics, Face Registrations, Early Leaves
- **System:** Notifications, Edge Devices, Audit Logs, Settings

Use `lucide-react` icons for each menu item:
- `LayoutDashboard`, `Users`, `Calendar`, `Building2`, `ClipboardList`, `BarChart3`, `ScanFace`, `DoorOpen`, `Bell`, `Cpu`, `ScrollText`, `Settings`

The sidebar should highlight the active route using `useLocation()` from React Router.

**Step 2: Create Header**

Header with:
- `SidebarTrigger` for mobile hamburger
- Breadcrumbs component
- Notification bell (with unread count badge from `notificationsService.unreadCount()`)
- Admin avatar dropdown (profile info, logout action)

**Step 3: Create Breadcrumbs**

Parse current route path and render breadcrumb segments using shadcn/ui `Breadcrumb` component.

**Step 4: Create DashboardLayout**

```tsx
// src/components/layout/dashboard-layout.tsx
import { SidebarProvider, SidebarInset } from '@/components/ui/sidebar'
import { AppSidebar } from './app-sidebar'
import { Header } from './header'

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <Header />
        <main className="flex-1 p-6">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  )
}
```

**Step 5: Verify layout renders**

**Step 6: Commit**

```bash
git add admin/src/components/layout/
git commit -m "feat(admin): add dashboard layout with sidebar, header, and breadcrumbs"
```

---

## Task 6: Router Setup & App.tsx

**Files:**
- Modify: `admin/src/App.tsx`
- Create: `admin/src/routes/dashboard.tsx` (placeholder)

**Step 1: Set up React Router with all routes**

```tsx
// src/App.tsx
import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth.store'
import { ProtectedRoute } from '@/components/protected-route'
import { DashboardLayout } from '@/components/layout/dashboard-layout'
import LoginPage from '@/routes/login'
import DashboardPage from '@/routes/dashboard'
// Import all other route pages (lazy load for code splitting)
import { lazy, Suspense } from 'react'

const UsersPage = lazy(() => import('@/routes/users/index'))
const UserDetailPage = lazy(() => import('@/routes/users/[id]'))
const SchedulesPage = lazy(() => import('@/routes/schedules/index'))
const ScheduleDetailPage = lazy(() => import('@/routes/schedules/[id]'))
const RoomsPage = lazy(() => import('@/routes/rooms'))
const AttendancePage = lazy(() => import('@/routes/attendance'))
const AnalyticsPage = lazy(() => import('@/routes/analytics/index'))
const AtRiskPage = lazy(() => import('@/routes/analytics/at-risk'))
const AnomaliesPage = lazy(() => import('@/routes/analytics/anomalies'))
const FaceRegistrationsPage = lazy(() => import('@/routes/face-registrations'))
const EarlyLeavesPage = lazy(() => import('@/routes/early-leaves'))
const NotificationsPage = lazy(() => import('@/routes/notifications'))
const EdgeDevicesPage = lazy(() => import('@/routes/edge-devices'))
const AuditLogsPage = lazy(() => import('@/routes/audit-logs'))
const SettingsPage = lazy(() => import('@/routes/settings'))

function Loading() {
  return (
    <div className="flex h-64 items-center justify-center">
      <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
    </div>
  )
}

export default function App() {
  const checkAuth = useAuthStore((s) => s.checkAuth)

  useEffect(() => { checkAuth() }, [checkAuth])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={
          <ProtectedRoute>
            <DashboardLayout>
              <Suspense fallback={<Loading />}>
                <Routes>
                  <Route index element={<DashboardPage />} />
                  <Route path="users" element={<UsersPage />} />
                  <Route path="users/:id" element={<UserDetailPage />} />
                  <Route path="schedules" element={<SchedulesPage />} />
                  <Route path="schedules/:id" element={<ScheduleDetailPage />} />
                  <Route path="rooms" element={<RoomsPage />} />
                  <Route path="attendance" element={<AttendancePage />} />
                  <Route path="analytics" element={<AnalyticsPage />} />
                  <Route path="analytics/at-risk" element={<AtRiskPage />} />
                  <Route path="analytics/anomalies" element={<AnomaliesPage />} />
                  <Route path="face-registrations" element={<FaceRegistrationsPage />} />
                  <Route path="early-leaves" element={<EarlyLeavesPage />} />
                  <Route path="notifications" element={<NotificationsPage />} />
                  <Route path="edge-devices" element={<EdgeDevicesPage />} />
                  <Route path="audit-logs" element={<AuditLogsPage />} />
                  <Route path="settings" element={<SettingsPage />} />
                </Routes>
              </Suspense>
            </DashboardLayout>
          </ProtectedRoute>
        } />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
```

Note: The nested `<Routes>` inside a `<Route>` requires the parent route path to end with `/*`. Adjust to `path="/*"` for the protected layout route.

**Step 2: Create placeholder pages for all routes**

Create a placeholder for each route file that exports a default component with the page name as an `<h1>`. This ensures routing works end-to-end before building each page.

```tsx
// Example placeholder for src/routes/users/index.tsx
export default function UsersPage() {
  return <div><h1 className="text-2xl font-bold">User Management</h1><p className="text-muted-foreground">Coming soon...</p></div>
}
```

Create placeholders for all 15 route files:
- `src/routes/dashboard.tsx`
- `src/routes/users/index.tsx`
- `src/routes/users/[id].tsx`
- `src/routes/schedules/index.tsx`
- `src/routes/schedules/[id].tsx`
- `src/routes/rooms.tsx`
- `src/routes/attendance.tsx`
- `src/routes/analytics/index.tsx`
- `src/routes/analytics/at-risk.tsx`
- `src/routes/analytics/anomalies.tsx`
- `src/routes/face-registrations.tsx`
- `src/routes/early-leaves.tsx`
- `src/routes/notifications.tsx`
- `src/routes/edge-devices.tsx`
- `src/routes/audit-logs.tsx`
- `src/routes/settings.tsx`

**Step 3: Verify all routes navigate correctly**

```bash
cd /Users/cjjutba/Projects/iams/admin
npm run dev
```

Visit each route in the browser. Expected: Each shows its placeholder heading.

**Step 4: Commit**

```bash
git add admin/src/
git commit -m "feat(admin): set up React Router with lazy-loaded routes and placeholder pages"
```

---

## Task 7: Shared Data Table Component

**Files:**
- Create: `admin/src/components/data-tables/data-table.tsx`
- Create: `admin/src/components/data-tables/data-table-pagination.tsx`
- Create: `admin/src/components/data-tables/data-table-toolbar.tsx`

**Step 1: Create reusable DataTable component**

Build a generic `DataTable<T>` component using `@tanstack/react-table` and shadcn/ui `Table`. Support:
- Column definitions with `ColumnDef<T>`
- Client-side sorting (clickable headers)
- Client-side filtering (search input)
- Pagination (page size selector, prev/next)
- Row selection (optional)
- Loading skeleton state

This component will be reused across Users, Schedules, Rooms, Attendance, etc.

**Step 2: Create DataTablePagination**

Previous/Next buttons, page size selector (10, 20, 50), row count display.

**Step 3: Create DataTableToolbar**

Search input, filter dropdowns (passed as props), action buttons (export, create new).

**Step 4: Commit**

```bash
git add admin/src/components/data-tables/
git commit -m "feat(admin): add reusable DataTable component with pagination and toolbar"
```

---

## Task 8: Shared Chart Components

**Files:**
- Create: `admin/src/components/charts/stat-card.tsx`
- Create: `admin/src/components/charts/line-chart.tsx`
- Create: `admin/src/components/charts/bar-chart.tsx`
- Create: `admin/src/components/charts/area-chart.tsx`

**Step 1: Create StatCard**

```tsx
// src/components/charts/stat-card.tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  title: string
  value: string | number
  description?: string
  icon: LucideIcon
  trend?: { value: number; label: string }
}

export function StatCard({ title, value, description, icon: Icon, trend }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
        {trend && (
          <p className={`text-xs ${trend.value >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {trend.value >= 0 ? '+' : ''}{trend.value}% {trend.label}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
```

**Step 2: Create Recharts wrapper components**

Wrap Recharts `LineChart`, `BarChart`, `AreaChart` with consistent styling (shadcn/ui card wrapper, responsive container, theme-aware colors using CSS variables).

**Step 3: Commit**

```bash
git add admin/src/components/charts/
git commit -m "feat(admin): add stat card and chart wrapper components"
```

---

## Task 9: Dashboard Home Page

**Files:**
- Modify: `admin/src/routes/dashboard.tsx`

**Step 1: Implement Dashboard Home**

This is the main landing page after login. It calls:
- `analyticsService.systemMetrics()` — stat cards
- `attendanceService.getScheduleSummaries()` — active sessions table
- `attendanceService.getAlerts()` — recent early-leave alerts
- `analyticsService.anomalies()` — recent anomalies

**Layout:**
1. Row of 6 stat cards (total students, faculty, schedules, attendance records, avg attendance rate, early leaves)
2. Row of 2 charts (attendance trend line chart, attendance by day bar chart)
3. Row of 2 tables (active sessions, recent early-leave alerts)

Use `useEffect` + `useState` for data fetching. Use `setInterval` for 60-second polling on stat cards.

**Step 2: Verify with live backend**

```bash
cd /Users/cjjutba/Projects/iams/admin
npm run dev
```

Visit `http://localhost:5173/`. Expected: Dashboard renders with data from backend.

**Step 3: Commit**

```bash
git add admin/src/routes/dashboard.tsx
git commit -m "feat(admin): implement dashboard home with metrics, charts, and live tables"
```

---

## Task 10: User Management Page

**Files:**
- Modify: `admin/src/routes/users/index.tsx`
- Modify: `admin/src/routes/users/[id].tsx`

**Step 1: Implement Users list page**

- Use `DataTable` with columns: Name, Email, Role (badge), Student ID, Face Registered, Status (active/inactive badge), Created, Actions
- Filter by role (dropdown: all/student/faculty/admin) and status (active/inactive)
- Search by name or email
- Actions dropdown per row: View, Deactivate/Reactivate, Deregister Face
- Deactivate/Reactivate uses `usersService.deactivate()` / `.reactivate()` with confirmation dialog

**Step 2: Implement User Detail page**

- Fetch user by ID from URL params: `usersService.getById(id)`
- Display profile card (name, email, role, status, created date)
- Show attendance history table for this student (filter `attendanceService.list({ student_id: id })`)
- Show face registration status from `faceService.statistics()`
- Actions: Edit profile (inline form), deactivate, deregister face

**Step 3: Commit**

```bash
git add admin/src/routes/users/
git commit -m "feat(admin): implement user management with list, detail, and actions"
```

---

## Task 11: Schedule Management Page

**Files:**
- Modify: `admin/src/routes/schedules/index.tsx`
- Modify: `admin/src/routes/schedules/[id].tsx`

**Step 1: Implement Schedules list page**

- Use `DataTable` with columns: Subject Code, Subject Name, Faculty, Room, Day, Time, Enrolled, Status, Actions
- Filter by day of week, faculty, semester
- Create Schedule button opens a dialog/sheet with form:
  - Fields: subject_code, subject_name, faculty_id (select from faculty list), room_id (select from rooms), day_of_week, start_time, end_time, semester, academic_year, target_course, target_year_level
  - Uses `schedulesService.create()`
- Edit action opens same form pre-filled, uses `schedulesService.update()`
- Delete action uses confirmation dialog, calls `schedulesService.delete()`

**Step 2: Implement Schedule Detail page**

- Fetch schedule by ID: `schedulesService.getById(id)`
- Show schedule info card
- Enrolled students table: `schedulesService.getEnrolledStudents(id)`
- Attendance summary: `attendanceService.getScheduleSummary(id)`

**Step 3: Commit**

```bash
git add admin/src/routes/schedules/
git commit -m "feat(admin): implement schedule management with CRUD and enrollment view"
```

---

## Task 12: Room Management Page

**Files:**
- Modify: `admin/src/routes/rooms.tsx`

**Step 1: Implement Rooms page**

- Use `DataTable` with columns: Name, Building, Capacity, Camera Endpoint, Active, Actions
- Create Room dialog with form: name, building, capacity, camera_endpoint
- Edit/Delete actions
- Uses `roomsService` (note: CRUD endpoints need to be created in Task 14)

**Step 2: Commit**

```bash
git add admin/src/routes/rooms.tsx
git commit -m "feat(admin): implement room management page"
```

---

## Task 13: Attendance, Analytics, Face, Early Leaves, Notifications Pages

**Files:**
- Modify: `admin/src/routes/attendance.tsx`
- Modify: `admin/src/routes/analytics/index.tsx`
- Modify: `admin/src/routes/analytics/at-risk.tsx`
- Modify: `admin/src/routes/analytics/anomalies.tsx`
- Modify: `admin/src/routes/face-registrations.tsx`
- Modify: `admin/src/routes/early-leaves.tsx`
- Modify: `admin/src/routes/notifications.tsx`

**Step 1: Attendance Overview**

- Filters: Date range (calendar picker), schedule (dropdown), status (multi-select)
- Data table with attendance records
- Export button: calls `attendanceService.export()` and triggers file download
- Click row to expand and show presence logs

**Step 2: Analytics Dashboard**

- System metrics stat cards from `analyticsService.systemMetrics()`
- Class-level analytics with schedule selector
- Attendance heatmap visualization
- Links to at-risk and anomalies sub-pages

**Step 3: At-Risk Students page**

- Table from `analyticsService.atRisk()`
- Columns: Student, Attendance Rate, Risk Level (badge with color), Missed Classes
- Risk level color coding: LOW=green, MEDIUM=yellow, HIGH=red

**Step 4: Anomalies page**

- Table from `analyticsService.anomalies()`
- Columns: Student, Type (badge), Severity, Description, Detected, Resolved, Actions
- Resolve action: confirmation dialog, calls `analyticsService.resolveAnomaly(id)`

**Step 5: Face Registrations**

- Stats cards from `faceService.statistics()`
- Table of users with face registration status
- Deregister action with confirmation

**Step 6: Early Leaves**

- Data table from `attendanceService.getEarlyLeaves()`
- Columns: Student, Subject, Left At, Consecutive Misses, Date
- Filter by date range, schedule

**Step 7: Notifications**

- Two tabs: "Send" and "History"
- Send tab: Form with target selector, title, message fields. Uses `notificationsService.broadcast()` (backend endpoint from Task 14)
- History tab: Table of sent notifications

**Step 8: Commit**

```bash
git add admin/src/routes/
git commit -m "feat(admin): implement attendance, analytics, face, early leaves, and notifications pages"
```

---

## Task 14: New Backend Endpoints

**Files:**
- Create: `backend/app/models/audit_log.py`
- Create: `backend/app/models/system_setting.py`
- Create: `backend/app/schemas/audit_log.py`
- Create: `backend/app/schemas/system_setting.py`
- Create: `backend/app/schemas/room.py`
- Create: `backend/app/routers/audit.py`
- Create: `backend/app/routers/settings_router.py`
- Modify: `backend/app/routers/rooms.py` — add CRUD endpoints
- Modify: `backend/app/routers/notifications.py` — add broadcast endpoint
- Modify: `backend/app/main.py` — register new routers
- Modify: `backend/app/models/__init__.py` — add new models

**Step 1: Room CRUD endpoints**

Add to `backend/app/routers/rooms.py`:
- `GET /rooms` — list all rooms (admin only)
- `GET /rooms/{room_id}` — get room by ID
- `POST /rooms` — create room (admin only)
- `PATCH /rooms/{room_id}` — update room (admin only)
- `DELETE /rooms/{room_id}` — delete room (admin only)

Create `backend/app/schemas/room.py` with `RoomCreate`, `RoomUpdate`, `RoomResponse`.

**Step 2: Audit Log model + endpoint**

```python
# backend/app/models/audit_log.py
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
from app.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)  # e.g. "user.deactivate", "schedule.create"
    target_type = Column(String(50), nullable=False)  # e.g. "user", "schedule", "room"
    target_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

Create router `backend/app/routers/audit.py`:
- `GET /audit/logs` — list logs (admin only, paginated, filterable by action, admin_id, date range)

Create utility function to log admin actions that can be called from other routers.

**Step 3: System Settings model + endpoints**

```python
# backend/app/models/system_setting.py
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
from app.database import Base

class SystemSetting(Base):
    __tablename__ = "system_settings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

Create router `backend/app/routers/settings_router.py`:
- `GET /settings` — get all settings (admin only)
- `PATCH /settings` — update settings (admin only)

**Step 4: Broadcast Notifications endpoint**

Add to `backend/app/routers/notifications.py`:
- `POST /notifications/broadcast` — send notification to all users, by role, or specific user (admin only)

**Step 5: Register new routers in main.py**

Add to `backend/app/main.py`:
```python
from app.routers import audit, settings_router
app.include_router(audit.router, prefix=f"{settings.API_PREFIX}/audit", tags=["Audit"])
app.include_router(settings_router.router, prefix=f"{settings.API_PREFIX}/settings", tags=["Settings"])
```

**Step 6: Create Alembic migration**

```bash
cd /Users/cjjutba/Projects/iams/backend
alembic revision --autogenerate -m "add audit_logs and system_settings tables"
alembic upgrade head
```

**Step 7: Commit**

```bash
git add backend/app/models/ backend/app/schemas/ backend/app/routers/ backend/app/main.py
git commit -m "feat(backend): add room CRUD, audit logs, system settings, and broadcast notifications endpoints"
```

---

## Task 15: Edge Devices & Audit Logs & Settings Pages

**Files:**
- Modify: `admin/src/routes/edge-devices.tsx`
- Modify: `admin/src/routes/audit-logs.tsx`
- Modify: `admin/src/routes/settings.tsx`
- Create: `admin/src/services/edge.service.ts`
- Create: `admin/src/services/audit.service.ts`
- Create: `admin/src/services/settings.service.ts`

**Step 1: Edge Device Monitoring page**

- Status cards: Connected devices, total devices
- Device list table (if edge status endpoint is available)
- Note: This depends on the edge heartbeat feature. For MVP, show a "No edge devices reporting" message until heartbeat is implemented.

**Step 2: Audit Logs page**

- Data table from `GET /api/v1/audit/logs`
- Columns: Timestamp, Admin, Action, Target, Details
- Filters: Date range, action type, admin user

**Step 3: Settings page**

- Form with current settings from `GET /api/v1/settings`
- Grouped sections: Semester, Thresholds, System
- Save button calls `PATCH /api/v1/settings`
- Show success/error toast on save

**Step 4: Commit**

```bash
git add admin/src/routes/ admin/src/services/
git commit -m "feat(admin): implement edge devices, audit logs, and settings pages"
```

---

## Task 16: WebSocket Integration

**Files:**
- Create: `admin/src/hooks/use-websocket.ts`
- Modify: `admin/src/stores/auth.store.ts` — trigger WS connection on login

**Step 1: Create useWebSocket hook**

```ts
// src/hooks/use-websocket.ts
import { useEffect, useRef, useCallback, useState } from 'react'
import { useAuthStore } from '@/stores/auth.store'

export function useWebSocket(onMessage: (data: any) => void) {
  const user = useAuthStore((s) => s.user)
  const wsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  const connect = useCallback(() => {
    if (!user) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = import.meta.env.VITE_WS_URL || `${protocol}//${window.location.host}`
    const ws = new WebSocket(`${host}/api/v1/ws/${user.id}`)

    ws.onopen = () => setIsConnected(true)
    ws.onclose = () => {
      setIsConnected(false)
      setTimeout(connect, 5000) // reconnect after 5s
    }
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage(data)
      } catch { /* ignore non-JSON */ }
    }

    wsRef.current = ws
  }, [user, onMessage])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  return { isConnected }
}
```

**Step 2: Wire WebSocket into Dashboard and Early Leaves pages**

- Dashboard: Listen for `early_leave_alert` and `session_update` events to update live tables
- Early Leaves: Listen for `early_leave_alert` to prepend to list
- Header: Listen for `notification` events to update unread count badge

**Step 3: Commit**

```bash
git add admin/src/hooks/ admin/src/routes/ admin/src/components/
git commit -m "feat(admin): add WebSocket integration for real-time dashboard updates"
```

---

## Task 17: Deployment Configuration

**Files:**
- Modify: `deploy/nginx.conf`
- Modify: `deploy/docker-compose.prod.yml`
- Create: `admin/Dockerfile`
- Create: `admin/.env.production`

**Step 1: Create admin Dockerfile**

```dockerfile
# admin/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html/admin
```

**Step 2: Update nginx.conf**

Add location block to serve admin static files:

```nginx
location /admin {
    alias /usr/share/nginx/html/admin;
    try_files $uri $uri/ /admin/index.html;
}
```

**Step 3: Update docker-compose.prod.yml**

Add admin build service or include admin dist in nginx container.

**Step 4: Create .env.production**

```
VITE_API_URL=https://167.71.217.44/api/v1
VITE_WS_URL=wss://167.71.217.44
```

**Step 5: Test production build**

```bash
cd /Users/cjjutba/Projects/iams/admin
npm run build
```

Expected: `admin/dist/` contains built static files.

**Step 6: Commit**

```bash
git add admin/Dockerfile admin/.env.production deploy/nginx.conf deploy/docker-compose.prod.yml
git commit -m "feat(deploy): add admin dashboard to production deployment pipeline"
```

---

## Task 18: Final Polish & Testing

**Step 1: Test all pages end-to-end**

Run backend and admin dev server simultaneously:

```bash
# Terminal 1
cd /Users/cjjutba/Projects/iams/backend && source venv/bin/activate && python run.py

# Terminal 2
cd /Users/cjjutba/Projects/iams/admin && npm run dev
```

Test flow:
1. Visit `http://localhost:5173/login` — login with admin credentials
2. Verify redirect to dashboard with metrics
3. Navigate to each page via sidebar
4. Test CRUD operations (create/edit/delete) on users, schedules, rooms
5. Test attendance export (CSV download)
6. Test anomaly resolution
7. Test notification broadcast
8. Verify WebSocket updates on dashboard

**Step 2: Fix any TypeScript errors**

```bash
cd /Users/cjjutba/Projects/iams/admin
npx tsc --noEmit
```

**Step 3: Fix any lint issues**

```bash
cd /Users/cjjutba/Projects/iams/admin
npm run lint
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(admin): complete admin dashboard with all pages and deployment config"
```

---

## Summary

| Task | Description | Dependencies |
|------|-------------|-------------- |
| 1 | Project scaffolding | None |
| 2 | TypeScript types | Task 1 |
| 3 | API client & services | Tasks 1, 2 |
| 4 | Auth store & login | Tasks 1, 2, 3 |
| 5 | Dashboard layout | Task 1 |
| 6 | Router setup | Tasks 4, 5 |
| 7 | Shared DataTable | Task 1 |
| 8 | Shared Charts | Task 1 |
| 9 | Dashboard Home | Tasks 3, 6, 7, 8 |
| 10 | User Management | Tasks 3, 6, 7 |
| 11 | Schedule Management | Tasks 3, 6, 7 |
| 12 | Room Management | Tasks 3, 6, 7 |
| 13 | Attendance, Analytics, etc. | Tasks 3, 6, 7, 8 |
| 14 | New Backend Endpoints | None (parallel) |
| 15 | Edge, Audit, Settings pages | Tasks 6, 7, 14 |
| 16 | WebSocket integration | Tasks 4, 9 |
| 17 | Deployment config | Task 1 |
| 18 | Final polish | All |

**Parallelizable groups:**
- Tasks 1-6: Sequential (foundation)
- Tasks 7, 8: Parallel (shared components)
- Tasks 9-13: Parallel (independent pages, all depend on 7+8)
- Task 14: Parallel with 9-13 (backend work)
- Tasks 15-17: After dependencies
- Task 18: Last
