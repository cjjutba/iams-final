# AI Task Prompt Template (MOD-05)

## Standard Prompt
```text
Implement: MOD-05 / FUN-05-XX

Read first:
- docs/modules/MOD-05-schedules-and-enrollments/README.md
- docs/modules/MOD-05-schedules-and-enrollments/02-specification/function-specifications.md
- docs/modules/MOD-05-schedules-and-enrollments/03-api/api-inventory.md
- docs/modules/MOD-05-schedules-and-enrollments/10-traceability/traceability-matrix.md

Scope:
- Implement only the selected FUN-05-* function.
- Follow API/data/screen contracts in this module pack.
- Do not add out-of-scope features.

Output required:
- Files changed
- Function IDs implemented
- Tests executed
- Risks/blockers
```

## Review Prompt
```text
Review MOD-05 implementation against:
- acceptance criteria
- schedule/enrollment business rules
- traceability matrix
Return: findings by severity with file references.
```
