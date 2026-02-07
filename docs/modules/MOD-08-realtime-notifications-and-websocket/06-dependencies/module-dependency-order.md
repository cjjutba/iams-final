# Module Dependency Order

## Prerequisites Before MOD-08
1. `MOD-01` Authentication and Identity (token auth and identity checks)
2. `MOD-06` Attendance Records (attendance event sources)
3. `MOD-07` Presence Tracking and Early Leave (early-leave event sources)

## Downstream Consumers
- `MOD-09` Student Mobile App
- `MOD-10` Faculty Mobile App

## Sequence Note
MOD-08 should be integrated after core attendance/presence behaviors are stable enough to emit reliable events.
