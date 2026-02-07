# Goal and Objectives

## Module Goal
Continuously track in-session student presence and detect early-leave behavior with configurable thresholds and reliable logs.

## Primary Objectives
1. Start and maintain schedule-scoped session state.
2. Execute periodic scan logic at configured intervals.
3. Maintain per-student miss counters and detection state.
4. Flag early leave at configured threshold.
5. Compute presence score from scan outcomes.
6. Expose presence logs and early-leave events via API.

## Success Outcomes
- Session state is tied to schedule/date context consistently.
- Miss-counter logic is deterministic and test-covered.
- Early-leave events are generated only when threshold conditions are met.
- Presence logs are queryable and align with attendance records.

## Non-Goals (for MOD-07 MVP)
- Computer-vision face recognition model training.
- Realtime event transport implementation (owned by MOD-08).
- Full analytics dashboard.

## Stakeholders
- Faculty: consume early-leave and detailed presence data.
- Students: indirectly affected via attendance status outcomes.
- Backend services: use presence state to update attendance/alerts.
