# Error Models

## Standard Error Shape
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": []
  }
}
```

## Auth-Related Error Codes
- `VALIDATION_ERROR` — invalid input data
- `UNAUTHORIZED` — missing or invalid credentials/token
- `FORBIDDEN` — access denied (inactive, email unverified, role restriction)
- `NOT_FOUND` — resource not found
- `CONFLICT` — duplicate resource (email, student_id)
- `RATE_LIMITED` — too many requests
- `SERVER_ERROR` — unexpected server error

## Status Mapping
| Status | Typical Auth Scenario |
|---|---|
| 400 | Invalid request body / malformed fields / weak password |
| 401 | Invalid or expired Supabase JWT |
| 403 | Inactive account, email not verified, role restriction, faculty self-registration attempt |
| 404 | User not found in local database |
| 409 | Duplicate email or student_id on registration |
| 429 | Rate limit exceeded on auth endpoint |
| 500 | Unexpected server or Supabase Auth error |

## Detailed Error Scenarios by Function

### FUN-01-01 (Verify Student ID)
| Scenario | Status | Code | Message |
|---|---|---|---|
| Empty student_id | 400 | VALIDATION_ERROR | Student ID is required |
| Invalid student_id format | 400 | VALIDATION_ERROR | Invalid student ID format |
| University data source unavailable | 500 | SERVER_ERROR | Identity verification service unavailable |

### FUN-01-02 (Register)
| Scenario | Status | Code | Message |
|---|---|---|---|
| Weak password (< 8 chars) | 400 | VALIDATION_ERROR | Password must be at least 8 characters |
| Invalid email format | 400 | VALIDATION_ERROR | Invalid email format |
| Missing required fields | 400 | VALIDATION_ERROR | Field X is required |
| Email already registered | 409 | CONFLICT | Email is already registered |
| Student ID already registered | 409 | CONFLICT | Student ID is already registered |
| Student ID not verified | 403 | FORBIDDEN | Student identity must be verified before registration |
| Faculty self-registration attempt | 403 | FORBIDDEN | Faculty registration is not available. Contact your administrator |
| Supabase Auth creation failure | 500 | SERVER_ERROR | Account creation failed |

### FUN-01-05 (Get Current User)
| Scenario | Status | Code | Message |
|---|---|---|---|
| Missing Authorization header | 401 | UNAUTHORIZED | Authentication required |
| Invalid/expired JWT | 401 | UNAUTHORIZED | Invalid or expired token |
| Inactive account | 403 | FORBIDDEN | Account is deactivated |
| Email not verified | 403 | FORBIDDEN | Email not verified. Please check your email for the verification link |
| User not in local DB | 404 | NOT_FOUND | User not found |

## Supabase Client Error Scenarios (Mobile-Side)

### FUN-01-03 (Login via Supabase)
| Scenario | Supabase Error | Mobile Action |
|---|---|---|
| Invalid credentials | AuthApiError: "Invalid login credentials" | Show error message on login screen |
| Email not confirmed | AuthApiError: "Email not confirmed" | Show message to check email |
| Network error | NetworkError | Show retry option |

### FUN-01-06 (Password Reset Request via Supabase)
| Scenario | Supabase Behavior | Mobile Action |
|---|---|---|
| Valid email | Sends reset email | Show "Check your email" message |
| Unknown email | No error (security) | Show "Check your email" message |
| Rate limited | AuthApiError | Show "Try again later" message |

### FUN-01-07 (Password Reset Completion via Supabase)
| Scenario | Supabase Error | Mobile Action |
|---|---|---|
| Weak new password | AuthApiError | Show password requirements |
| Expired reset link | AuthApiError | Show "Link expired, request new reset" |
