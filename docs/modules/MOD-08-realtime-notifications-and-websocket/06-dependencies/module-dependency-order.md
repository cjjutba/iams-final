# Module Dependency Order

## Prerequisites Before MOD-08
| Module | Dependency | Specific Need |
|---|---|---|
| `MOD-01` | Authentication and Identity | Supabase JWT verification middleware (`get_current_user`) for WebSocket handshake auth |
| `MOD-02` | User Management | User identity context; user deletion triggers WS disconnect and map cleanup |
| `MOD-05` | Room and Schedule Management | Schedule and enrollment data for recipient resolution (fanout) |
| `MOD-06` | Attendance Records | Attendance event sources — invokes FUN-08-02 on status transitions |
| `MOD-07` | Presence Tracking and Early Leave | Early-leave event sources — invokes FUN-08-03 on threshold detection |

## Downstream Consumers
| Module | Consumption |
|---|---|
| `MOD-09` | Student mobile app — receives WebSocket events on SCR-018 |
| `MOD-10` | Faculty mobile app — receives WebSocket events on SCR-021, SCR-025, SCR-029 |

## Sequence Note
MOD-08 should be integrated after core attendance/presence behaviors (MOD-06, MOD-07) are stable enough to emit reliable events. JWT auth middleware (MOD-01) must be in place before WebSocket auth can work.
