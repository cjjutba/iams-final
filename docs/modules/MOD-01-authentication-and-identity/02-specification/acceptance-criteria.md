# Acceptance Criteria

## Function-Level Acceptance

### FUN-01-01
- Given a valid student ID in dataset, endpoint returns `valid: true` and profile preview.
- Given unknown student ID, endpoint returns `valid: false`.

### FUN-01-02
- Given verified identity and valid payload, account is created and `201` returned.
- Given duplicate email/student_id, endpoint returns validation error.
- Given unverified identity, account creation is blocked.

### FUN-01-03
- Given valid credentials, endpoint returns access token and refresh token metadata.
- Given invalid credentials, returns `401`.

### FUN-01-04
- Given valid refresh token, endpoint returns new access token.
- Given invalid/expired refresh token, returns `401`.

### FUN-01-05
- Given valid access token, endpoint returns current user data.
- Given missing/invalid access token, returns `401`.

## Module-Level Acceptance
- Faculty self-registration remains blocked in all user flows.
- Auth responses follow standard success/error envelope.
- Auth behavior is consistent with screen-level flow in module docs.
