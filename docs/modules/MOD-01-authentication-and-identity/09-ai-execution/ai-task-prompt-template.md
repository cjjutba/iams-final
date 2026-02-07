# AI Task Prompt Template (MOD-01)

## Standard Prompt
```text
Implement: MOD-01 / FUN-01-XX

Read first:
- docs/modules/MOD-01-authentication-and-identity/README.md
- docs/modules/MOD-01-authentication-and-identity/02-specification/function-specifications.md
- docs/modules/MOD-01-authentication-and-identity/03-api/api-inventory.md
- docs/modules/MOD-01-authentication-and-identity/10-traceability/traceability-matrix.md

Scope:
- Implement only the selected FUN-01-* function.
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
Review MOD-01 implementation against:
- acceptance criteria
- error model
- traceability matrix
Return: findings by severity with file references.
```
