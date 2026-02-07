# Test Cases

## Unit Tests
- `T10-U1`: Faculty login validator handles invalid credential formats.
- `T10-U2`: Session restore routes to faculty stack only with valid role/session.
- `T10-U3`: Active-class resolver returns correct class for time window.
- `T10-U4`: Manual entry validator enforces status enum and required fields.
- `T10-U5`: Early-leave filter builder formats schedule/date queries correctly.
- `T10-U6`: Notification event parser handles unknown payload safely.

## Integration Tests
- `T10-I1`: Login + token persistence + session restore for faculty.
- `T10-I2`: Schedule retrieval and active class navigation.
- `T10-I3`: Live attendance fetch and roster render.
- `T10-I4`: Manual attendance update request/response round-trip.
- `T10-I5`: Early-leave alerts and class summary data retrieval.
- `T10-I6`: WebSocket connect/reconnect updates live and notification screens.

## Scenario Tests
- `T10-S1`: Faculty monitors active class end-to-end.
- `T10-S2`: Manual override appears in live/today views.
- `T10-S3`: Alert screen shows early-leave event in-class.
- `T10-S4`: Session-end summary appears post-class.
- `T10-S5`: Reconnect after network drop resumes realtime updates.
