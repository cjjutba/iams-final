# Endpoint Contract: WS /ws/{user_id}

## Purpose
Open and maintain authenticated realtime channel for user-scoped event delivery.

## Route
- Method: `WS`
- Path: `/ws/{user_id}`

## Path Params
| Name | Type | Required | Notes |
|---|---|---|---|
| `user_id` | UUID/string | Yes | Must match authenticated identity |

## Auth Rules
- Connection requires valid auth token.
- If auth fails, connection is rejected.
- If `user_id` does not match auth identity, connection is rejected.

## Connection Lifecycle
1. Client opens socket to `/ws/{user_id}`.
2. Server validates auth and user binding.
3. Server registers connection in active map.
4. Server sends realtime events while connected.
5. On disconnect/error/timeout, server removes stale mapping.

## Message Envelope
```json
{
  "type": "attendance_update",
  "data": {}
}
```

## Close/Error Cases
- Unauthorized: reject handshake or close immediately.
- Forbidden/mismatch: reject when user binding fails.
- Server error: close and log for observability.
