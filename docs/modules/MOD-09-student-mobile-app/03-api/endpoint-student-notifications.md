# Endpoint Contract: Student Notifications

## Scope
Realtime event subscription used by student notifications screen.

## Endpoint
- `WS /ws/{user_id}`

## Event Types (Student-Relevant)
- `attendance_update`
- `session_end`
- Optional `early_leave` visibility based on backend routing policy

## Client Rules
1. Connect only after auth state is ready.
2. Display connection status when disconnected/reconnecting.
3. Parse event envelope safely and ignore unknown types.
4. Resume stream on reconnect without app restart.

## Screen
- `SCR-018` StudentNotificationsScreen
