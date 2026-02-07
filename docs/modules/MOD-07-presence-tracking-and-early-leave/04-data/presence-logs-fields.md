# Presence Logs Fields

## Table
`presence_logs`

## Module-Relevant Columns
| Column | Type | Constraints | Use in MOD-07 |
|---|---|---|---|
| id | BIGSERIAL | PK | log row id |
| attendance_id | UUID | FK attendance_records | parent attendance record |
| scan_number | INTEGER | NOT NULL | scan sequence index |
| scan_time | TIMESTAMPTZ | NOT NULL | scan timestamp |
| detected | BOOLEAN | NOT NULL | detected/not-detected result |
| confidence | DECIMAL(5,4) | optional | match confidence |

## Indexes
- `idx_presence_attendance`
- `idx_presence_time`
