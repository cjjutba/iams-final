# Function Specifications

## FUN-10-01 Faculty Login and Session Restore
Goal:
- Authenticate faculty users and restore active session state across app restarts.

Inputs:
- Faculty credentials, auth API responses, local secure session data.

Process:
1. Submit faculty login credentials.
2. Validate token response and fetch current profile.
3. Persist session/token securely.
4. Restore session at startup before protected navigation.

Outputs:
- Active authenticated faculty session.

Validation Rules:
- Reject invalid credentials with clear UI feedback.
- Enforce fallback to login when session refresh fails.

## FUN-10-02 View Schedule and Active Class
Goal:
- Present faculty teaching schedule and determine active class context.

Inputs:
- Authenticated faculty context, schedule API response, current time/day.

Process:
1. Fetch schedules for current faculty.
2. Resolve active class based on schedule/time rules.
3. Route user to live class view when active class exists.

Outputs:
- Schedule list and active class indicator.

Validation Rules:
- Handle no-class/no-schedule states gracefully.
- Ensure only faculty-owned classes are shown.

## FUN-10-03 Live Attendance Monitoring
Goal:
- Provide realtime visibility of attendance during an active class.

Inputs:
- Live attendance endpoint data and websocket events.

Process:
1. Load live roster for selected schedule.
2. Subscribe to realtime updates.
3. Update roster rows as status changes.

Outputs:
- Live attendance roster with current status signals.

Validation Rules:
- Display inactive-session state clearly.
- Parse event payloads safely and ignore malformed items.

## FUN-10-04 Manual Attendance Updates
Goal:
- Allow faculty to manually insert/update attendance entries when needed.

Inputs:
- Student, schedule, date, status, remarks payload.

Process:
1. Validate manual entry fields.
2. Submit manual attendance update.
3. Refresh live/today views with updated values.

Outputs:
- Manual update acknowledgment and reflected roster changes.

Validation Rules:
- Restrict action to faculty role.
- Ensure status value uses allowed enum.

## FUN-10-05 Early-Leave Alerts and Class Summaries
Goal:
- Show early-leave warnings during session and summary outcomes after session.

Inputs:
- Presence endpoint responses, websocket alerts, session-end summary events.

Process:
1. Fetch early-leave list for schedule/date context.
2. Render alert feed in faculty alert screens.
3. Render summary totals after class/session completion.

Outputs:
- Alert visibility and class summary views.

Validation Rules:
- Alert list must filter by selected class/date context.
- Summary values must align with attendance totals.

## FUN-10-06 Faculty Profile and Notifications
Goal:
- Provide faculty profile management and notification feed experience.

Inputs:
- Profile APIs, websocket events, local notification state.

Process:
1. Load and render faculty profile data.
2. Submit profile edits with validation.
3. Stream and display notification events.

Outputs:
- Updated profile and live faculty notification feed.

Validation Rules:
- Profile edits respect backend field constraints.
- Notification screen supports reconnect behavior.
