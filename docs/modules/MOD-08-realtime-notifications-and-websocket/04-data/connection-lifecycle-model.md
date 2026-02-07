# Connection Lifecycle Model

## Connection Map Shape (Conceptual)
```text
connections_by_user: {
  user_id: [
    {
      connection_id,
      socket_ref,
      connected_at,
      last_seen_at,
      is_alive
    }
  ]
}
```

## Lifecycle States
1. `connecting`
2. `authenticated`
3. `active`
4. `stale`
5. `closed`

## Transition Rules
- `connecting -> authenticated` after auth and user binding pass.
- `authenticated -> active` after map registration.
- `active -> stale` on heartbeat timeout or send failure.
- `stale -> closed` after cleanup removal.
- reconnect creates new `connecting` instance and should supersede stale entries.

## Cleanup Rules
- Remove stale entries on disconnect callback.
- Remove stale entries on failed send if socket is invalid.
- Periodic sweeper may remove old inactive entries.
