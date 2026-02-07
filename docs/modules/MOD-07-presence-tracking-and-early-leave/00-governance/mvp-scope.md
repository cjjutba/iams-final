# MVP Scope

## In Scope
- Session state per schedule/date.
- Periodic scan evaluation loop.
- Miss counter updates per student.
- Early-leave flag generation.
- Presence score computation.
- Presence logs and early-leave event APIs.

## Out of Scope
- Realtime transport layer implementation.
- Cross-class predictive analytics.
- Advanced anomaly detection beyond configured threshold logic.

## MVP Constraints
- Default scan interval: 60 seconds.
- Default early-leave threshold: 3 consecutive misses.
- Presence score: `(scans_detected / total_scans) * 100`.

## MVP Gate Criteria
- `FUN-07-01` through `FUN-07-06` implemented and tested.
- Threshold/interval configuration works without code changes.
- Early-leave and recovery scenarios match documented behavior.
