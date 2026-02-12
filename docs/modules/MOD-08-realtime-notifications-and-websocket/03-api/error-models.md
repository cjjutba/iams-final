# Error Models

## WebSocket Close Codes
| Code | Name | Condition | Description |
|---|---|---|---|
| 4001 | Unauthorized | Missing/invalid/expired JWT | Connection rejected — no valid auth token |
| 4003 | Forbidden | `user_id` mismatch | Path `user_id` does not match JWT `sub` claim |
| 1000 | Normal Close | Clean disconnect or stale timeout | Graceful connection close |
| 1011 | Internal Error | Server exception or send failure | Unexpected server-side error |

## Handshake/Auth Errors
| Condition | Close Code | Expected Handling |
|---|---|---|
| Missing `token` query parameter | 4001 | Reject connection immediately |
| Invalid JWT (bad signature) | 4001 | Reject connection immediately |
| Expired JWT | 4001 | Reject connection immediately |
| `user_id` does not match JWT `sub` | 4003 | Reject connection immediately |
| Invalid `user_id` format (not UUID) | 4001 | Reject connection with validation failure |

## Runtime Errors
| Condition | Expected Handling |
|---|---|
| Send failure | Log with `user_id` and `event_type`, mark connection for cleanup |
| Heartbeat timeout (no pong) | Close with code 1000, remove stale connection |
| Server exception | Close with code 1011, emit operational log |

## Envelope Validation Failures
- If event payload cannot satisfy documented schema:
  - Do not emit malformed event to any client.
  - Log validation error with `function_id` and `event_type`.

## HTTP Error Response Shape
If any REST endpoints are added to MOD-08 in the future, they must use:
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```
Note: No `details` array — consistent with MOD-01 through MOD-07 error envelope.

## Error Scenarios by Function
| Function | Scenario | Handling |
|---|---|---|
| FUN-08-01 | Missing JWT | Close 4001 |
| FUN-08-01 | Expired JWT | Close 4001 |
| FUN-08-01 | Invalid JWT signature | Close 4001 |
| FUN-08-01 | `user_id` mismatch | Close 4003 |
| FUN-08-01 | Invalid `user_id` format | Close 4001 |
| FUN-08-02 | Send failure to recipient | Log error, mark connection stale |
| FUN-08-02 | Invalid payload (missing required field) | Log validation error, do not emit |
| FUN-08-03 | Send failure to faculty | Log error, mark connection stale |
| FUN-08-04 | Send failure to recipients | Log error, mark connection stale |
| FUN-08-05 | Heartbeat timeout | Close 1000, remove from map |
| FUN-08-05 | Reconnect with stale entry | Evict stale, register new |

## Observability Fields
Recommended log keys for all error/warning logs:
- `module_id` (`MOD-08`)
- `function_id` (`FUN-08-*`)
- `event_type` (`attendance_update`, `early_leave`, `session_end`)
- `user_id`
- `schedule_id` (if available)
- `error_code` (close code or internal error code)
- `timestamp` (ISO-8601 with timezone offset)
