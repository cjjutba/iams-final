# Data Model Inventory

## Primary Data Stores Used by MOD-05
1. `rooms`
2. `schedules`
3. `enrollments`
4. `users` (faculty/student linkage)

## Entities
- room metadata
- schedule slot metadata
- student-schedule enrollment mapping
- faculty user mapping

## Ownership
- Schedule/enrollment persistence: backend data layer
- CSV import source mapping: `MOD-11` integration
