# Test Cases

## Unit Tests
- `T09-U1`: Startup routing chooses correct entry screen.
- `T09-U2`: Login validator rejects invalid credentials format.
- `T09-U3`: Registration step guard blocks step skip.
- `T09-U4`: Face image count validator enforces 3-5 range.
- `T09-U5`: Attendance filter/date validator handles invalid ranges.
- `T09-U6`: Notification event parser handles unknown payload safely.

## Integration Tests
- `T09-I1`: Login + token persistence + session restore.
- `T09-I2`: Registration flow API chain (verify -> register -> face register).
- `T09-I3`: Schedule and attendance history fetch/render.
- `T09-I4`: Profile update round-trip via API.
- `T09-I5`: Face re-registration status update flow.
- `T09-I6`: WebSocket connect/reconnect updates student notification feed.

## Scenario Tests
- `T09-S1`: First-time user reaches student home after complete registration.
- `T09-S2`: Returning user with valid session bypasses onboarding.
- `T09-S3`: API failure shows error state and retry path on history screen.
- `T09-S4`: Temporary network drop recovers notification stream.
