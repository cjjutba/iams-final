# Data Model Inventory

## Local Mobile Data Domains
- Auth session state (token metadata, user identity)
- Registration draft state (step-wise inputs)
- Attendance and schedule view state
- Profile form state
- Notification feed state
- UI state flags (loading, empty, error)

## Backend Data Domains (Consumed)
- `users`
- `face_registrations`
- `schedules`
- `attendance_records`
- Notification events from websocket stream

## Module Note
Module 9 primarily owns client-side state and does not own backend table schemas.
