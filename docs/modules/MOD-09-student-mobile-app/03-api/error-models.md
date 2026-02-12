# Error Models

## HTTP Response Envelope
Success:
```json
{ "success": true, "data": { ... }, "message": "..." }
```

Error:
```json
{ "success": false, "error": { "code": "...", "message": "..." } }
```
**Important**: Error responses have NO `details` array — only `code` and `message`. Do not assume or parse a `details` field.

## API Error Categories
| Category | Typical Codes | Auth Context | Client Handling |
|---|---|---|---|
| Validation | 400 | Any | Show field-level errors from `error.message`, keep form state |
| Unauthorized | 401 | Post-auth | Attempt `/auth/refresh`, then route to login |
| Forbidden | 403 | Post-auth | Show access message and block action |
| Not Found | 404 | Post-auth | Show empty/not found state |
| Server Error | 500 | Any | Show retry option and non-blocking message |

## Registration-Specific Errors
| Error Code | Endpoint | Description |
|---|---|---|
| `STUDENT_NOT_FOUND` | `/auth/verify-student-id` | Student ID not in `student_records` table |
| `ALREADY_REGISTERED` | `/auth/verify-student-id` | Student ID already has an account |
| `VALIDATION_ERROR` | `/auth/register` | Invalid registration payload |
| `FACE_QUALITY_ERROR` | `/face/register` | Face image quality/quantity rejection |

## WebSocket Close Codes
| Code | Meaning | Client Action |
|---|---|---|
| 4001 | Unauthorized (missing/invalid/expired JWT) | Redirect to login screen |
| 4003 | Forbidden (user_id mismatch with JWT sub) | Show permission error message |
| 1000 | Normal close | No action needed |
| 1011 | Server error | Retry with exponential backoff |

## WebSocket Event Errors
- Invalid event payload → ignore safely (no crash).
- Unknown event type → ignore (additive-only versioning means new types may appear).
- Connection timeout → show reconnecting indicator, retry with backoff.

## Logging Guidance
Capture non-sensitive diagnostics only:
- Screen ID
- Endpoint path or event type
- HTTP status code or WebSocket close code
- Request correlation ID if available
- **Never** log token values, passwords, or sensitive user data.
