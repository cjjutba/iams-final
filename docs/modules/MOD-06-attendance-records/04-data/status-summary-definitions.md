# Status and Summary Definitions

## Attendance Status Values
| Status | Description | Trigger |
|---|---|---|
| `present` | Detected on time and participated sufficiently | System (FUN-06-01) or manual (FUN-06-05) |
| `late` | First detection after grace period | System (FUN-06-01) based on schedule start_time |
| `absent` | Never detected during class session | System (end-of-session) or manual (FUN-06-05) |
| `early_leave` | Left before class ended (3 consecutive missed scans) | MOD-07 presence tracking updates status |

## Status Transitions
- `present` → `early_leave`: MOD-07 detects 3 consecutive missed 60-second scans.
- `absent` → `present`/`late`: Manual override by faculty (FUN-06-05) with remarks.
- Any status can be overridden by faculty manual entry (FUN-06-05) with required `remarks`.

## Summary Metrics
Typical summary block (used in FUN-06-02 Get Today's Attendance):
```json
{
  "total": 30,
  "present": 25,
  "late": 2,
  "absent": 2,
  "early_leave": 1
}
```

All 4 status counts are always included (never optional).

## Consistency Rule
Summary counts must equal filtered record totals for the same query scope:
- `total = present + late + absent + early_leave`
- Summary is computed server-side, not client-side.
