# Error Models

## API Error Categories
| Category | Typical Codes | Client Handling |
|---|---|---|
| Validation | 400 | Show field-level errors and keep input state |
| Unauthorized | 401 | Attempt refresh then route to login |
| Forbidden | 403 | Show permission message and block action |
| Not Found | 404 | Show empty/not found state |
| Server Error | 500 | Show retry action and non-blocking message |

## Manual Attendance Error Cases
- Invalid status value.
- Missing required payload fields.
- Unauthorized role attempting manual entry.

## Realtime Error Cases
- WebSocket disconnect or timeout.
- Event payload parse failure.
- Reconnect attempt exhaustion if bounded retries are configured.

## Logging Guidance
Log only non-sensitive fields:
- screen ID
- endpoint/event type
- status/error code
- request correlation ID when available
