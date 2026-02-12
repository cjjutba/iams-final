# Test Cases

## Unit Tests
- `T09-U1`: Startup routing chooses correct entry screen (onboarding vs home based on session state).
- `T09-U2`: Login validator rejects invalid credentials format (empty email, short password).
- `T09-U3`: Registration step guard blocks step skip (cannot reach Step 3 without Step 2 complete).
- `T09-U4`: Face image count validator enforces 3-5 range (rejects 2 or 6+).
- `T09-U5`: Attendance date filter validator handles invalid date ranges gracefully.
- `T09-U6`: Notification event parser handles unknown payload type safely (no crash).
- `T09-U7`: Timestamp formatter converts ISO-8601+08:00 to display format correctly.
- `T09-U8`: Error envelope parser extracts `error.code` and `error.message` without assuming `details` array.
- `T09-U9`: SecureStore helper stores and retrieves tokens correctly (mock SecureStore).

## Integration Tests
- `T09-I1`: Login → token persistence → session restore on app restart.
- `T09-I2`: Registration flow API chain (verify-student-id → register → face register with JWT).
- `T09-I3`: Schedule and attendance history fetch/render with correct snake_case field access.
- `T09-I4`: Profile update round-trip via `PATCH /users/{id}` (with JWT).
- `T09-I5`: Face re-registration status update flow (check status → upload → verify update).
- `T09-I6`: WebSocket connect/reconnect updates student notification feed.
- `T09-I7`: Pre-auth endpoint (`/auth/login`) works without JWT.
- `T09-I8`: Post-auth endpoint (`/schedules/me`) returns 401 without JWT.
- `T09-I9`: WebSocket close code 4001 triggers login redirect.

## Scenario Tests
- `T09-S1`: First-time user completes full registration (4 steps) and reaches student home.
- `T09-S2`: Returning user with valid session bypasses onboarding and reaches home.
- `T09-S3`: API failure shows error state and retry path on history screen.
- `T09-S4`: Temporary network drop recovers notification stream via reconnect.
- `T09-S5`: Expired token triggers refresh → on refresh failure → redirects to login.
- `T09-S6`: All timestamps on attendance screens display in Asia/Manila timezone.
