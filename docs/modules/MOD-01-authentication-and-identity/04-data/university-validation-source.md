# University Validation Source

## Purpose
Provide authoritative student/faculty identity records used during auth-related checks.

## Used By
- `FUN-01-01` Verify student identity.
- `FUN-01-02` Student registration validation.

## Expected Student Columns
- `student_id`
- `last_name`
- `first_name`
- `course`
- `year`
- `section`
- `email` (optional)

## Expected Faculty Columns (for pre-seeding)
- `employee_id`
- `last_name`
- `first_name`
- `department`
- `email`

## Data Quality Rules
- `student_id` must be unique.
- Name fields should be normalized to avoid case mismatch.
- Missing required columns blocks import usage.

## Operational Notes
- Import handled by data seed process module (`MOD-11`).
- MOD-01 consumes validation data; it does not own import pipeline.
