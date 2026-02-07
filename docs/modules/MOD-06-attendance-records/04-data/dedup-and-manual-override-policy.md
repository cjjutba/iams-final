# Dedup and Manual Override Policy

## Dedup Policy
1. One attendance row per `(student_id, schedule_id, date)`.
2. Recognition updates should upsert existing row, not insert duplicates.

## Manual Override Policy
1. Faculty role required.
2. Manual entry can create missing row or update existing status.
3. Remarks should be stored for audit context.
4. Override operations should update `updated_at` timestamp.

## Conflict Handling
- If simultaneous updates occur, use deterministic upsert strategy and log conflicts.
