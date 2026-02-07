# Error Models

## API Error Categories
| Category | Typical Codes | Client Handling |
|---|---|---|
| Validation | 400 | Show field-level errors, keep form state |
| Unauthorized | 401 | Attempt refresh or route to login |
| Forbidden | 403 | Show access message and block action |
| Not Found | 404 | Show empty/not found state |
| Server Error | 500 | Show retry option and non-blocking message |

## Registration-Specific Errors
- Invalid student ID verification result
- Invalid registration payload
- Face upload quality/quantity rejection

## Realtime Errors
- Websocket disconnect/timeouts
- Invalid event payload parsing
- Reconnect exhaustion (if bounded attempts configured)

## Logging Guidance
Capture non-sensitive diagnostics only:
- screen ID
- endpoint/event type
- status/error code
- request correlation ID if available
