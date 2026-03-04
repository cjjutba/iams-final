# Backend Endpoint to Service Method Mapping

## Auth Router (/auth)
| Method | Backend Endpoint | Service Method | Notes |
|--------|-----------------|----------------|-------|
| POST | /auth/verify-student-id | authService.verifyStudentId() | Response shape transformed |
| POST | /auth/register | authService.register() | Returns RegisterResponse with nested tokens |
| POST | /auth/login | authService.login() | Body: { identifier, password } JSON |
| POST | /auth/refresh | authService.refreshToken() | Also handled by api.ts interceptor |
| GET | /auth/me | authService.getMe() | Returns UserResponse directly |
| POST | /auth/change-password | authService.changePassword() | Body: { old_password, new_password } |
| POST | /auth/logout | authService.logout() | Best-effort, always clears local storage |

## Users Router (/users)
| Method | Backend Endpoint | Service Method | Notes |
|--------|-----------------|----------------|-------|
| PATCH | /users/{user_id} | authService.updateProfile() | Profile update lives here, not auth |

## Attendance Router (/attendance)
| Method | Backend Endpoint | Service Method | Notes |
|--------|-----------------|----------------|-------|
| GET | /attendance/me | attendanceService.getMyAttendance() | Student only |
| GET | /attendance/today | attendanceService.getTodayAttendance() | Faculty only, returns List[] |
| GET | /attendance/me/summary | attendanceService.getAttendanceSummary() | Response shape transformed |
| GET | /attendance/live/{id} | attendanceService.getLiveAttendance() | Faculty only |
| GET | /attendance/{id} | attendanceService.getAttendanceDetail() | |
| GET | /attendance/{id}/logs | attendanceService.getPresenceLogs() | |
| POST | /attendance/manual | attendanceService.createManualEntry() | Faculty only, 201 |
| PATCH | /attendance/{id} | attendanceService.updateAttendanceStatus() | Faculty only |
| GET | /attendance/early-leaves/ | attendanceService.getEarlyLeaveEvents() | Faculty only |

## Schedules Router (/schedules)
| Method | Backend Endpoint | Service Method | Notes |
|--------|-----------------|----------------|-------|
| GET | /schedules/me | scheduleService.getMySchedules() | |
| GET | /schedules/{id} | scheduleService.getScheduleById() | |
| GET | /schedules/{id}/students | scheduleService.getScheduleStudents() | Returns ScheduleWithStudents |
| GET | /schedules/ | scheduleService.getAllSchedules() | Optional ?day= filter |

## Face Router (/face)
| Method | Backend Endpoint | Service Method | Notes |
|--------|-----------------|----------------|-------|
| POST | /face/register | faceService.registerFace() | multipart, 201, student only |
| POST | /face/reregister | faceService.reregisterFace() | multipart, student only |
| GET | /face/status | faceService.getFaceStatus() | |
| DELETE | /face/{user_id} | faceService.deleteFaceRegistration() | |

## Notifications Router (/notifications) -- NOT registered in main.py yet
| Method | Backend Endpoint | Service Method | Notes |
|--------|-----------------|----------------|-------|
| GET | /notifications/ | notificationService.getNotifications() | |
| PATCH | /notifications/{id}/read | notificationService.markAsRead() | |
| POST | /notifications/read-all | notificationService.markAllAsRead() | |
| GET | /notifications/unread-count | notificationService.getUnreadCount() | |

## WebSocket (/ws)
| Endpoint | Service | Notes |
|----------|---------|-------|
| ws://.../api/v1/ws/{userId} | websocketService.connect() | Singleton, auto-reconnect |
