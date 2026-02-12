# Test Cases

## Unit Tests
- `T10-U1`: Faculty login validator handles invalid credential formats.
- `T10-U2`: Session restore routes to faculty stack only with valid role/session.
- `T10-U3`: Active-class resolver returns correct class for time window (Asia/Manila timezone).
- `T10-U4`: Manual entry validator enforces status enum (`present`, `late`, `absent`, `early_leave`) and required fields.
- `T10-U5`: Early-leave filter builder formats schedule/date queries correctly (YYYY-MM-DD).
- `T10-U6`: Notification event parser handles unknown payload safely (event envelope format).
- `T10-U7`: Timestamp formatter displays +08:00 offset correctly.
- `T10-U8`: Error envelope parser extracts error code and message without assuming `details` array.
- `T10-U9`: SecureStore helper reads/writes/clears tokens correctly.

## Integration Tests
- `T10-I1`: Login + token persistence in SecureStore + session restore for faculty.
- `T10-I2`: Schedule retrieval and active class navigation (post-auth, JWT required).
- `T10-I3`: Live attendance fetch and roster render (post-auth).
- `T10-I4`: Manual attendance update request/response round-trip with response envelope.
- `T10-I5`: Early-leave alerts and class summary data retrieval (post-auth).
- `T10-I6`: WebSocket connect/reconnect updates live and notification screens.
- `T10-I7`: Pre-auth endpoints (`/auth/login`, `/auth/forgot-password`) work without JWT.
- `T10-I8`: Post-auth endpoints reject with 401 when no JWT provided.
- `T10-I9`: WebSocket close code 4001 triggers login redirect.

## Scenario Tests
- `T10-S1`: Faculty monitors active class end-to-end (login → schedule → live → summary).
- `T10-S2`: Manual override appears in live/today views after submission.
- `T10-S3`: Alert screen shows early-leave event during active class.
- `T10-S4`: Session-end summary appears post-class via WebSocket event.
- `T10-S5`: Token refresh failure clears session and redirects to login.
- `T10-S6`: Reconnect after network drop resumes realtime updates.
- `T10-S7`: Timezone display shows +08:00 on all attendance screens.
