# Error Models

## Handshake/Auth Errors
| Condition | Expected Handling |
|---|---|
| Missing/invalid token | Reject connection as unauthorized |
| `user_id` mismatch | Reject connection as forbidden |
| Invalid path param | Reject with validation failure |

## Runtime Errors
| Condition | Expected Handling |
|---|---|
| Send failure | Log and mark connection for cleanup |
| Heartbeat timeout | Close and remove stale connection |
| Server exception | Close socket and emit operational log |

## Envelope Validation Failures
- If event payload cannot satisfy documented schema:
  - Do not emit malformed event.
  - Log validation error with function ID and event type.

## Observability Fields
Recommended log keys:
- `module_id` (`MOD-08`)
- `function_id` (`FUN-08-*`)
- `event_type`
- `user_id`
- `schedule_id` (if available)
- `error_code`
