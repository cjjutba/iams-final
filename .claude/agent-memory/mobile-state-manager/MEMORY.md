# Mobile State Manager - Agent Memory

## Architecture Overview
- Zustand stores in `mobile/src/stores/` (authStore, attendanceStore, scheduleStore)
- Custom hooks in `mobile/src/hooks/` (useAuth, useAttendance, useSchedule, useWebSocket)
- Types in `mobile/src/types/` with snake_case field names matching backend API
- Services in `mobile/src/services/` (attendanceService, authService)
- Utils: `api.ts` (axios instance), `storage.ts` (SecureStore wrapper), `helpers.ts` (getErrorMessage)

## Critical Patterns & Gotchas

### Day-of-Week Conversion (IMPORTANT)
- Backend `Schedule.day_of_week`: 0=Monday, 6=Sunday (see `schedule.types.ts` DayOfWeek enum)
- JavaScript `Date.getDay()`: 0=Sunday, 1=Monday, 6=Saturday
- Conversion: `jsDay === 0 ? 6 : jsDay - 1`
- The `useSchedule` hook accepts JS day values and converts internally
- The `scheduleStore.getSchedulesByDay()` accepts backend day values directly
- Screens always pass JS day values via `new Date().getDay()`

### API Response Shape
- Most endpoints return `ApiResponse<T>` wrapper: `{ success, data: T, message?, error? }`
- Auth login/register returns `AuthResponse`: `{ access_token, refresh_token, token_type, user? }`
- `/auth/me` returns `ApiResponse<User>` -- access user via `response.data.data`, NOT `response.data.user`

### Property Naming
- All types use snake_case (matching backend): `day_of_week`, `start_time`, `end_time`, `student_id`
- Store property is `myAttendance`, screens may reference it as `history` via hook alias

### Store-Hook Relationship
- Screens use hooks, not stores directly (except `RootNavigator` and login screens which use `useAuthStore`)
- Hooks wrap stores and add computed properties + backward-compat aliases
- `useAttendance` exposes `history` as alias for `myAttendance`

## Bug History (2026-02-07)
- `useAttendance`: Destructured non-existent `history` instead of `myAttendance` -- crash
- `useAttendance`: Missing `presenceLogs` in destructure
- `useAttendance`: `hasAttendanceToday` checked `!== null` on array (always true)
- `useSchedule`: Used camelCase property names (`dayOfWeek`, `startTime`, `endTime`) instead of snake_case
- `useSchedule`: Missing day-of-week conversion in `getSchedulesByDay`
- `authStore.loadUser`: Used `response.data.user` instead of `response.data.data` for `/auth/me`
- `authStore`: Missing `changePassword`, `updateProfile`, `forgotPassword` actions
- `authStore.logout`: Did not reset state on storage clear failure

## File Locations
- Stores: `mobile/src/stores/{authStore,attendanceStore,scheduleStore}.ts`
- Hooks: `mobile/src/hooks/{useAuth,useAttendance,useSchedule}.ts`
- Types: `mobile/src/types/{auth,attendance,schedule}.types.ts`
- Services: `mobile/src/services/{authService,attendanceService}.ts`
