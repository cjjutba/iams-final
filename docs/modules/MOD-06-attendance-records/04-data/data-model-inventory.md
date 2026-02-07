# Data Model Inventory

## Primary Data Stores Used by MOD-06
1. `attendance_records`
2. `schedules`
3. `users`

## Entities
- Attendance row per student/schedule/date
- Daily status and check-in/check-out timestamps
- Optional manual remarks/audit context

## Ownership
- Attendance persistence: backend attendance service/repository
- Schedule/user linkage: upstream modules (`MOD-05`, `MOD-01/02`)
