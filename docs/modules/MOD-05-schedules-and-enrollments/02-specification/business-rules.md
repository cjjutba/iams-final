# Business Rules

## Schedule Rules
1. Schedule is defined by subject, faculty, room, day_of_week, start_time, end_time.
2. `start_time` must be earlier than `end_time`.
3. Active schedule uses `is_active=true` semantics.
4. Time comparisons must use consistent timezone assumptions.

## Enrollment Rules
1. Enrollment must map an existing student to an existing schedule.
2. `(student_id, schedule_id)` must remain unique.
3. Roster lookups must only include active/relevant student records per policy.

## Access Rules
1. Schedule creation is admin-only in MVP.
2. `GET /schedules/me` returns role-scoped data.
3. Roster visibility follows role/ownership policy.

## Integrity Rules
1. Referenced room/faculty IDs must exist.
2. Schedule retrieval should preserve deterministic ordering by day/time.
3. API responses should not leak unrelated private data.
