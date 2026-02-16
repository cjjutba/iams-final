# Mobile Frontend Specialist - Agent Memory

## Key Patterns

### Type Naming Convention (CRITICAL)
- Backend API returns **snake_case** fields (e.g., `subject_name`, `start_time`, `day_of_week`, `check_in_time`, `presence_score`, `scan_number`, `scan_time`)
- TypeScript types in `mobile/src/types/` use snake_case to match backend
- Some hooks (`useSchedule`) had bugs using camelCase (e.g., `schedule.dayOfWeek` instead of `schedule.day_of_week`) -- the hooks/stores are being fixed by another agent
- Screens MUST use snake_case to match the type definitions

### Day of Week Convention
- Schedule type: `day_of_week` where 0=Monday, 6=Sunday (see `schedule.types.ts`)
- JavaScript `Date.getDay()`: 0=Sunday, 6=Saturday
- Conversion: `jsDay === 0 ? 6 : jsDay - 1`
- `getDayName()` and `getShortDayName()` in formatters use 0=Monday convention

### Navigation Params (StudentStack)
- `AttendanceDetail`: `{ attendanceId: string; scheduleId: string; date: string }`
- `FaceRegister`: `{ mode: 'register' | 'reregister' }`
- `EditProfile`: `undefined`
- `Notifications`: `undefined`
- See `navigation.types.ts` for complete list

### Store Field Names
- `attendanceStore`: `myAttendance` (not `history`), `todayAttendance`, `presenceLogs`, `summary`
- `useAttendance` hook wraps store and may rename fields (e.g., `history` maps to `myAttendance`)
- `scheduleStore`: `schedules`, `getSchedulesByDay()`, `getTodaySchedules()`

### Design System
- Colors: see `constants/colors.ts` -- uses `theme.colors.success`, `theme.colors.error`, `theme.colors.warning` etc.
- Status colors: `theme.colors.status.present`, `.late`, `.absent`, `.early_leave` (each has `.bg`, `.fg`, `.border`)
- Background variants: `theme.colors.background` (white), `theme.colors.secondary` (light gray #F5F5F5)
- The old code used `theme.colors.backgroundSecondary` which should be `theme.colors.secondary`
- The old code used `theme.colors.status.success/error/warning` which should be `theme.colors.success/error/warning`

### Screen Pattern Template
Every student screen should have:
1. Loading state (ActivityIndicator or Loader component)
2. Error state with retry button (RefreshCw icon + error message + retry Button)
3. Empty state (icon + message + subtext)
4. Pull-to-refresh via RefreshControl
5. Use `getErrorMessage()` from utils for consistent error messages

### API Integration
- `api` from `utils/api.ts` -- Axios instance with auth interceptors
- Services in `services/` wrap API calls with typed responses
- Use `ApiResponse<T>` wrapper type for standard API responses
- Direct `api.get`/`api.post` for endpoints not in services (e.g., notifications)

### Component Prop Constraints (CRITICAL for TS)
- **Text `weight` prop**: ONLY accepts `'400' | '500' | '600' | '700'` -- NOT "bold", "semibold", "medium", "regular"
- **Avatar**: Does NOT accept `style` prop. Wrap in `<View style={...}>` for layout spacing.
- **Card `style` prop**: Typed as `ViewStyle` (not `StyleProp<ViewStyle>`), so arrays fail. Use spread: `style={{ ...styles.a, ...(!cond ? styles.b : {}) }}`
- **Divider `spacing` prop**: Takes `SpacingKey` (number: 0|1|2|3|4|5|6|8|10|12|16|20|24), NOT string like "lg"
- **authService.changePassword**: Takes TWO separate string args: `(oldPassword, newPassword)` -- NOT an object
- **authService.updateProfile**: Takes `(userId: string, data: ProfileUpdatePayload)` -- needs userId as first arg
- **AttendanceStatus**: Use enum values (`AttendanceStatus.PRESENT`, `.LATE`, `.ABSENT`, `.EARLY_LEAVE`), NOT string literals
- **ManualAttendanceRequest**: Uses snake_case fields: `student_id`, `schedule_id`, `date`, `status`, `remarks`

### Component Library
- UI: `Text`, `Button`, `Card`, `Badge`, `Avatar`, `Divider`, `Loader`, `Input`
- Layouts: `ScreenLayout`, `Header`
- Cards: `AttendanceCard`, `ScheduleCard`, `StudentCard`, `AlertCard`
- Forms: `FormInput`, `FormPassword`, `FormSelect`

### Navigation Params (FacultyStack)
- `LiveAttendance`: `{ scheduleId: string; subjectCode: string; subjectName: string }`
- `LiveFeed`: `{ scheduleId: string; roomId: string; subjectName: string }`
- `ClassDetail`: `{ scheduleId: string; date: string }`
- `StudentDetail`: `{ studentId: string; scheduleId: string }`
- `ManualEntry`: `{ scheduleId: string }`
- `Reports`: `{ scheduleId?: string }` -- scheduleId is optional
- `EditProfile`: `undefined`
- `Notifications`: `undefined`
- `Settings`: `undefined`

### Preferences Storage
- Notification prefs stored via `expo-secure-store` with `@iams/pref_*` prefix keys
- `config.APP_VERSION`, `config.APP_NAME` from `constants/config.ts`

## Files Modified (Student Screens - Session 1)
- `screens/student/StudentNotificationsScreen.tsx` - Replaced mock data with real API calls
- `screens/student/StudentHomeScreen.tsx` - Fixed property names, added error/loading states
- `screens/student/StudentScheduleScreen.tsx` - Fixed day numbering, added states
- `screens/student/StudentHistoryScreen.tsx` - Fixed data flow, added states
- `screens/student/StudentAttendanceDetailScreen.tsx` - Fixed property names, added error/retry
- `screens/student/StudentEditProfileScreen.tsx` - Added user reload after profile update
- `screens/student/StudentFaceRegisterScreen.tsx` - Added route params, better UX
- `screens/student/StudentProfileScreen.tsx` - Fixed FaceRegister navigation params

## Files Modified (Faculty/Common Screens - Session 2)
- `screens/faculty/FacultyAlertsScreen.tsx` - Removed MOCK_ALERTS, real API with filter param
- `screens/faculty/FacultyNotificationsScreen.tsx` - Removed MOCK_NOTIFICATIONS, real API + optimistic mark-as-read
- `screens/faculty/FacultyStudentDetailScreen.tsx` - Removed hardcoded mock stats, parallel API fetching
- `screens/faculty/FacultyReportsScreen.tsx` - Removed fake setTimeout + hardcoded CLASS_OPTIONS, uses real schedules
- `screens/faculty/FacultyLiveAttendanceScreen.tsx` - Improved WebSocket integration, added connection indicator
- `screens/faculty/FacultyClassDetailScreen.tsx` - Added loading/error/empty states, real API
- `screens/faculty/FacultyManualEntryScreen.tsx` - Improved error handling, "Add Another" flow
- `screens/faculty/FacultyHomeScreen.tsx` - Fixed LiveAttendance nav params, removed invalid section ref
- `screens/faculty/FacultyEditProfileScreen.tsx` - NEW FILE: profile update + password change forms
- `screens/faculty/index.ts` - Added FacultyEditProfileScreen export
- `screens/common/SettingsScreen.tsx` - Real notification toggles (SecureStore), about section, legal links

## Files Modified (Faculty TS Error Fixes - Session 3)
- `FacultyHomeScreen.tsx` - weight props, snake_case fields, backgroundSecondary
- `FacultyEditProfileScreen.tsx` - updateProfile(userId, data), changePassword(old, new)
- `FacultyManualEntryScreen.tsx` - AttendanceStatus enum, snake_case ManualAttendanceRequest fields
- `FacultyNotificationsScreen.tsx` - Card style spread instead of array
- `FacultyProfileScreen.tsx` - Avatar wrapped in View, weight props, Divider spacing, colors.error
- `FacultyScheduleScreen.tsx` - weight props, backgroundSecondary

## Files Modified (Student TS Error Fixes - Session 4)
- `StudentEditProfileScreen.tsx` - updateProfile(user!.id, data), changePassword(old, new), weight/spacing
- `StudentAttendanceDetailScreen.tsx` - getTodayAttendance returns array (extract [0]), weight props, Divider spacing
- `StudentHomeScreen.tsx` - weight props (semibold->600, bold->700)
- `StudentHistoryScreen.tsx` - conditional weight mapping (regular->400, semibold->600)
- `StudentFaceRegisterScreen.tsx` - weight props
- `StudentScheduleScreen.tsx` - conditional weight mapping, weight props
- `StudentNotificationsScreen.tsx` - Card style array -> StyleSheet.flatten, weight props
- `StudentProfileScreen.tsx` - Avatar wrapped in View, weight/medium props, Divider spacing

### WebSocket Patterns
- App-level WS: `config.WS_URL` = `ws://<host>:8000/api/v1/ws` -- used by `useWebSocket` hook
- Camera stream WS: `ws://<host>:8000/api/v1/stream/{scheduleId}` -- raw WebSocket, NOT the hook
- Derive WS URL from `config.API_BASE_URL` by replacing `http` with `ws`
- Auth token passed as query param: `?token=<jwt>`
- Always clean up WS on unmount: null out all handlers before `.close()`
- Use `isMountedRef` to prevent state updates after unmount

### Service Return Types (GOTCHA)
- `attendanceService.getTodayAttendance()` returns `AttendanceRecord[]` (array), NOT single record
- `attendanceService.getAttendanceDetail()` returns single `AttendanceRecord`
- When consuming array returns, use `data?.[0] ?? null` to extract first element

## Files Modified (LiveFeed Screen - Session 5)
- `screens/faculty/FacultyLiveFeedScreen.tsx` - NEW FILE: camera feed via raw WS with face detection overlays
- `types/navigation.types.ts` - Added `LiveFeed` route params to FacultyStackParamList
- `screens/faculty/index.ts` - Added FacultyLiveFeedScreen export
