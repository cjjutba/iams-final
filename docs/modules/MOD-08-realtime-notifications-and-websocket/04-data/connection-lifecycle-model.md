# Connection Lifecycle Model

## Connection Map Shape (Conceptual)
```text
connections_by_user: {
  user_id: [
    {
      connection_id,    # unique ID per socket instance
      socket_ref,       # WebSocket object reference
      connected_at,     # ISO-8601 with timezone offset
      last_seen_at,     # updated on pong/message
      is_alive          # boolean, false after stale timeout
    }
  ]
}
```

## Auth Context
- Connection registration only occurs after successful JWT validation (FUN-08-01).
- `user_id` key in connection map is the verified JWT `sub` claim.
- Unauthenticated connections never enter the map.

## Lifecycle States
1. `connecting` — handshake initiated, JWT not yet validated
2. `authenticated` — JWT verified, `user_id` confirmed
3. `active` — registered in map, receiving events
4. `stale` — heartbeat timeout or send failure detected
5. `closed` — removed from map, socket closed

## Transition Rules
| From | To | Trigger |
|---|---|---|
| `connecting` | `authenticated` | JWT valid, `sub` matches `user_id` |
| `connecting` | `closed` | JWT invalid/expired (4001) or mismatch (4003) |
| `authenticated` | `active` | Map registration complete |
| `active` | `stale` | Heartbeat timeout (`WS_STALE_TIMEOUT`) or send failure |
| `stale` | `closed` | Cleanup removal |
| `active` | `closed` | Client disconnect or server-side close |

## Reconnect Rules
- Reconnect creates new `connecting` instance.
- Before registration, evict any stale/active entry for same `user_id` (idempotent).
- Only one active socket per `user_id` at a time.

## Cleanup Rules
- Remove stale entries on disconnect callback.
- Remove stale entries on failed send if socket is invalid.
- Periodic sweeper may remove old inactive entries beyond `WS_STALE_TIMEOUT`.
- On user deletion (MOD-02): close socket and remove from map.

## Heartbeat Behavior
- Server sends ping every `WS_HEARTBEAT_INTERVAL` seconds (default: 30).
- Client responds with pong.
- `last_seen_at` updated on each pong received.
- No pong within `WS_STALE_TIMEOUT` (default: 60s) → mark stale, close.
