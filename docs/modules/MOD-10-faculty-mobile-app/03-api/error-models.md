# Error Models

## HTTP Response Envelope

**Success:**
```json
{ "success": true, "data": { ... }, "message": "..." }
```

**Error:**
```json
{ "success": false, "error": { "code": "ERROR_CODE", "message": "..." } }
```

> **Important:** Error responses do NOT contain a `details` array. Never assume one exists.

## API Error Categories
| Category | Auth Context | Typical Codes | Client Handling |
|---|---|---|---|
| Validation | Post-auth | 400 | Show field-level errors and keep input state |
| Unauthorized | Any | 401 | Attempt refresh then route to login |
| Forbidden | Post-auth | 403 | Show permission message and block action |
| Not Found | Post-auth | 404 | Show empty/not found state |
| Server Error | Any | 500 | Show retry action and non-blocking message |

## Auth-Specific Errors
| Code | HTTP Status | Context |
|---|---|---|
| `INVALID_CREDENTIALS` | 401 | Login with wrong email/password |
| `TOKEN_EXPIRED` | 401 | JWT expired, attempt refresh |
| `INSUFFICIENT_ROLE` | 403 | Student trying faculty-only endpoint |

## Manual Attendance Error Cases
- Invalid status value (not in allowed enum).
- Missing required payload fields (student_id, schedule_id, date, status).
- Unauthorized role attempting manual entry (403).
- Schedule not found (404).

## WebSocket Close Codes
| Code | Meaning | Client Action |
|---|---|---|
| 4001 | Unauthorized (invalid/expired JWT) | Clear session, redirect to login |
| 4003 | Forbidden (insufficient role) | Show forbidden error message |
| 1000 | Normal closure | No action needed |
| 1011 | Server error | Reconnect with exponential backoff |

## WebSocket Event Errors
- Event payload parse failure → log and ignore malformed event.
- Unknown event type → ignore silently.
- Reconnect attempt exhaustion → show persistent error state with manual retry option.

## Logging Guidance
Log only non-sensitive fields:
- screen ID
- endpoint/event type
- status/error code
- request correlation ID when available
