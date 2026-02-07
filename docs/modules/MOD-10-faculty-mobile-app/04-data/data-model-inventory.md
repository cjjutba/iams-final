# Data Model Inventory

## Local Mobile Data Domains
- Auth session state (tokens, faculty identity, role)
- Faculty schedule and active-class state
- Live attendance roster state
- Manual entry draft state
- Early-leave alert and class summary state
- Profile edit state
- Notification feed state
- UI state flags (loading, empty, error)

## Backend Data Domains (Consumed)
- `users`
- `schedules`
- `enrollments`
- `attendance_records`
- `presence_logs`
- `early_leave_events`

## Module Note
Module 10 owns client-side behavior and does not own backend table schemas.
