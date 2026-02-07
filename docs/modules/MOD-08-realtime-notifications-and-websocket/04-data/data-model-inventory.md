# Data Model Inventory

## Primary Module Data
- In-memory connection map (ephemeral)
- In-memory heartbeat/liveness metadata (ephemeral)
- Optional message delivery logs (persistent or file-based by implementation choice)

## Consumed Domain Data (Read/Input)
- `attendance_records` (source context for `attendance_update`)
- `early_leave_events` (source context for `early_leave`)
- `schedules` (source context for session metadata)
- `users` (recipient identity context)

## Persistence Note
Module 8 does not require new relational tables in MVP.
Persistent logging is optional and implementation-dependent.
