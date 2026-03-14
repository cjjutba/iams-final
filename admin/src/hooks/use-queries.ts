import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { usersService } from '@/services/users.service'
import { schedulesService } from '@/services/schedules.service'
import { roomsService } from '@/services/rooms.service'
import { analyticsService } from '@/services/analytics.service'
import { attendanceService } from '@/services/attendance.service'
import { notificationsService } from '@/services/notifications.service'
import { settingsService } from '@/services/settings.service'
import { faceService } from '@/services/face.service'
import { auditService } from '@/services/audit.service'
import { edgeService } from '@/services/edge.service'
import type { AdminCreateUser, CreateStudentRecord, UpdateStudentRecord, UserRole, UserUpdate, ScheduleCreate, ScheduleUpdate, RoomCreate, RoomUpdate, BroadcastNotificationRequest, NotificationPreferenceUpdate } from '@/types'

// ── Query keys ──────────────────────────────────────────────

export const queryKeys = {
  users: {
    all: ['users'] as const,
    list: (params?: { role?: UserRole }) => ['users', 'list', params] as const,
    detail: (id: string) => ['users', 'detail', id] as const,
    statistics: ['users', 'statistics'] as const,
  },
  studentRecords: {
    all: ['student-records'] as const,
    list: ['student-records', 'list'] as const,
    detail: (studentId: string) => ['student-records', 'detail', studentId] as const,
  },
  schedules: {
    all: ['schedules'] as const,
    list: (params?: { day?: number }) => ['schedules', 'list', params] as const,
    detail: (id: string) => ['schedules', 'detail', id] as const,
    students: (id: string) => ['schedules', 'students', id] as const,
  },
  rooms: {
    all: ['rooms'] as const,
    list: ['rooms', 'list'] as const,
    detail: (id: string) => ['rooms', 'detail', id] as const,
  },
  analytics: {
    metrics: ['analytics', 'metrics'] as const,
    dailyTrend: (days: number) => ['analytics', 'daily-trend', days] as const,
    weekdayBreakdown: ['analytics', 'weekday-breakdown'] as const,
    atRisk: ['analytics', 'at-risk'] as const,
    anomalies: ['analytics', 'anomalies'] as const,
    classOverview: (id: string) => ['analytics', 'class', id] as const,
  },
  attendance: {
    all: ['attendance'] as const,
    list: (params?: Record<string, unknown>) => ['attendance', 'list', params] as const,
    summaries: (date?: string) => ['attendance', 'summaries', date] as const,
    alerts: (params?: Record<string, unknown>) => ['attendance', 'alerts', params] as const,
    earlyLeaves: ['attendance', 'early-leaves'] as const,
    schedule: (id: string, date?: string) => ['attendance', 'schedule', id, date] as const,
    scheduleSummary: (id: string) => ['attendance', 'schedule-summary', id] as const,
    userHistory: (userId: string) => ['attendance', 'user', userId] as const,
  },
  face: {
    all: ['face'] as const,
    statistics: ['face', 'statistics'] as const,
  },
  audit: {
    all: ['audit'] as const,
    logs: (params?: Record<string, unknown>) => ['audit', 'logs', params] as const,
  },
  edge: {
    all: ['edge'] as const,
    status: ['edge', 'status'] as const,
  },
  notifications: {
    all: ['notifications'] as const,
    list: ['notifications', 'list'] as const,
    unreadCount: ['notifications', 'unread-count'] as const,
    preferences: ['notifications', 'preferences'] as const,
  },
  settings: {
    all: ['settings'] as const,
  },
}

// ── Users ───────────────────────────────────────────────────

export function useUsers(params?: { role?: UserRole }) {
  return useQuery({
    queryKey: queryKeys.users.list(params),
    queryFn: () => usersService.list(params),
  })
}

export function useUser(id: string) {
  return useQuery({
    queryKey: queryKeys.users.detail(id),
    queryFn: () => usersService.getById(id),
    enabled: !!id,
  })
}

export function useUserStatistics() {
  return useQuery({
    queryKey: queryKeys.users.statistics,
    queryFn: () => usersService.statistics(),
  })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: AdminCreateUser) => usersService.create(data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.users.all })
    },
  })
}

export function useCreateStudentRecord() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateStudentRecord) => usersService.createStudentRecord(data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.users.all })
      void qc.invalidateQueries({ queryKey: queryKeys.studentRecords.all })
    },
  })
}

export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UserUpdate }) => usersService.update(id, data),
    onSuccess: (_, { id }) => {
      void qc.invalidateQueries({ queryKey: queryKeys.users.all })
      void qc.invalidateQueries({ queryKey: queryKeys.users.detail(id) })
    },
  })
}

export function useDeactivateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => usersService.deactivate(id),
    onSuccess: (_, id) => {
      void qc.invalidateQueries({ queryKey: queryKeys.users.all })
      void qc.invalidateQueries({ queryKey: queryKeys.users.detail(id) })
    },
  })
}

export function useReactivateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => usersService.reactivate(id),
    onSuccess: (_, id) => {
      void qc.invalidateQueries({ queryKey: queryKeys.users.all })
      void qc.invalidateQueries({ queryKey: queryKeys.users.detail(id) })
    },
  })
}

// ── Student Records ────────────────────────────────────────

export function useStudentRecords() {
  return useQuery({
    queryKey: queryKeys.studentRecords.list,
    queryFn: () => usersService.listStudentRecords(),
  })
}

export function useStudentRecord(studentId: string) {
  return useQuery({
    queryKey: queryKeys.studentRecords.detail(studentId),
    queryFn: () => usersService.getStudentRecord(studentId),
    enabled: !!studentId,
  })
}

export function useUpdateStudentRecord() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ studentId, data }: { studentId: string; data: UpdateStudentRecord }) =>
      usersService.updateStudentRecord(studentId, data),
    onSuccess: (_, { studentId }) => {
      void qc.invalidateQueries({ queryKey: queryKeys.studentRecords.all })
      void qc.invalidateQueries({ queryKey: queryKeys.studentRecords.detail(studentId) })
    },
  })
}

export function useDeactivateStudentRecord() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (studentId: string) => usersService.deactivateStudentRecord(studentId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.studentRecords.all })
    },
  })
}

// ── Schedules ───────────────────────────────────────────────

export function useSchedules(params?: { day?: number }) {
  return useQuery({
    queryKey: queryKeys.schedules.list(params),
    queryFn: () => schedulesService.list(params),
  })
}

export function useSchedule(id: string) {
  return useQuery({
    queryKey: queryKeys.schedules.detail(id),
    queryFn: () => schedulesService.getById(id),
    enabled: !!id,
  })
}

export function useScheduleStudents(id: string) {
  return useQuery({
    queryKey: queryKeys.schedules.students(id),
    queryFn: () => schedulesService.getEnrolledStudents(id),
    enabled: !!id,
  })
}

export function useCreateSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ScheduleCreate) => schedulesService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: queryKeys.schedules.all }) },
  })
}

export function useUpdateSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ScheduleUpdate }) => schedulesService.update(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: queryKeys.schedules.all }) },
  })
}

export function useDeleteSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => schedulesService.delete(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: queryKeys.schedules.all }) },
  })
}

// ── Rooms ───────────────────────────────────────────────────

export function useRooms() {
  return useQuery({
    queryKey: queryKeys.rooms.list,
    queryFn: () => roomsService.list(),
  })
}

export function useRoom(id: string) {
  return useQuery({
    queryKey: queryKeys.rooms.detail(id),
    queryFn: () => roomsService.getById(id),
    enabled: !!id,
  })
}

export function useCreateRoom() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: RoomCreate) => roomsService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: queryKeys.rooms.all }) },
  })
}

export function useUpdateRoom() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: RoomUpdate }) => roomsService.update(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: queryKeys.rooms.all }) },
  })
}

export function useDeleteRoom() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => roomsService.delete(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: queryKeys.rooms.all }) },
  })
}

// ── Analytics ───────────────────────────────────────────────

export function useSystemMetrics() {
  return useQuery({
    queryKey: queryKeys.analytics.metrics,
    queryFn: async () => {
      const res = await analyticsService.systemMetrics()
      return (res as any).data ?? res
    },
    refetchInterval: 60_000,
  })
}

export function useDailyTrend(days = 30) {
  return useQuery({
    queryKey: queryKeys.analytics.dailyTrend(days),
    queryFn: () => analyticsService.dailyTrend(days),
  })
}

export function useWeekdayBreakdown() {
  return useQuery({
    queryKey: queryKeys.analytics.weekdayBreakdown,
    queryFn: () => analyticsService.weekdayBreakdown(),
  })
}

export function useAtRiskStudents() {
  return useQuery({
    queryKey: queryKeys.analytics.atRisk,
    queryFn: () => analyticsService.atRisk(),
  })
}

export function useAnomalies() {
  return useQuery({
    queryKey: queryKeys.analytics.anomalies,
    queryFn: () => analyticsService.anomalies(),
  })
}

export function useResolveAnomaly() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => analyticsService.resolveAnomaly(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: queryKeys.analytics.anomalies }) },
  })
}

// ── Attendance ──────────────────────────────────────────────

export function useAttendanceList(params?: Record<string, unknown>) {
  return useQuery({
    queryKey: queryKeys.attendance.list(params),
    queryFn: () => attendanceService.list(params as any),
  })
}

export function useScheduleSummaries(date?: string) {
  return useQuery({
    queryKey: queryKeys.attendance.summaries(date),
    queryFn: () => attendanceService.getScheduleSummaries(date),
  })
}

export function useAttendanceAlerts(params?: { filter?: string; schedule_id?: string }) {
  return useQuery({
    queryKey: queryKeys.attendance.alerts(params),
    queryFn: () => attendanceService.getAlerts(params),
  })
}

export function useEarlyLeaves() {
  return useQuery({
    queryKey: queryKeys.attendance.earlyLeaves,
    queryFn: () => attendanceService.getEarlyLeaves(),
  })
}

export function useUserAttendance(userId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.attendance.userHistory(userId),
    queryFn: () => attendanceService.list({ student_id: userId }),
    enabled: !!userId && enabled,
  })
}

export function useScheduleAttendanceSummary(scheduleId: string) {
  return useQuery({
    queryKey: queryKeys.attendance.scheduleSummary(scheduleId),
    queryFn: () => attendanceService.getScheduleSummary(scheduleId),
    enabled: !!scheduleId,
  })
}

// ── Face ────────────────────────────────────────────────

export function useFaceStatistics() {
  return useQuery({
    queryKey: queryKeys.face.statistics,
    queryFn: async () => {
      const res = await faceService.statistics()
      return (res as any).data ?? res
    },
  })
}

export function useDeregisterFace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => faceService.deregister(userId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.face.all })
      void qc.invalidateQueries({ queryKey: queryKeys.users.all })
    },
  })
}

// ── Audit Logs ─────────────────────────────────────────────

export function useAuditLogs(params?: Record<string, unknown>) {
  return useQuery({
    queryKey: queryKeys.audit.logs(params),
    queryFn: () => auditService.getLogs(params as any),
    placeholderData: keepPreviousData,
  })
}

// ── Edge Devices ───────────────────────────────────────────

export function useEdgeStatus() {
  return useQuery({
    queryKey: queryKeys.edge.status,
    queryFn: () => edgeService.getStatus(),
    refetchInterval: 30_000,
    retry: false,
  })
}

// ── Notifications ───────────────────────────────────────────

export function useNotifications() {
  return useQuery({
    queryKey: queryKeys.notifications.list,
    queryFn: () => notificationsService.list(),
  })
}

export function useUnreadCount() {
  return useQuery({
    queryKey: queryKeys.notifications.unreadCount,
    queryFn: () => notificationsService.unreadCount(),
    refetchInterval: 30_000,
  })
}

export function useMarkNotificationRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => notificationsService.markRead(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.notifications.all })
    },
  })
}

export function useBroadcastNotification() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: BroadcastNotificationRequest) => notificationsService.broadcast(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: queryKeys.notifications.all }) },
  })
}

export function useNotificationPreferences() {
  return useQuery({
    queryKey: queryKeys.notifications.preferences,
    queryFn: () => notificationsService.getPreferences(),
  })
}

export function useUpdateNotificationPreferences() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: NotificationPreferenceUpdate) => notificationsService.updatePreferences(data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.notifications.preferences })
    },
  })
}

// ── Settings ────────────────────────────────────────────────

export function useSettings() {
  return useQuery({
    queryKey: queryKeys.settings.all,
    queryFn: () => settingsService.getAll(),
  })
}

export function useUpdateSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (settings: Record<string, string>) => settingsService.update(settings),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: queryKeys.settings.all }) },
  })
}
