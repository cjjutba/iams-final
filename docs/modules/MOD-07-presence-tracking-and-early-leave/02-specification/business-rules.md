# Business Rules

## Session Rules
1. Presence processing is scoped to one schedule/date session.
2. Session uses configured start/end boundaries.
3. Only enrolled students are tracked for session state.

## Scan and Counter Rules
1. Scan interval defaults to 60 seconds unless configured.
2. Detected student resets miss counter to 0.
3. Undetected student increments miss counter by 1.

## Early-Leave Rules
1. Default threshold is 3 consecutive misses (configurable).
2. Early-leave event should be created once per relevant attendance context.
3. Flagging should trigger downstream notification workflows (handled by other modules).

## Score Rules
1. Presence score = `(scans_detected / total_scans) * 100`.
2. Score updates should remain consistent with presence log totals.

## Data Integrity Rules
1. Presence logs must reference valid attendance rows.
2. Event timestamps should be monotonic within session context.
3. Duplicate early-leave events for same context should be avoided.
