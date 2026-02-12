# Task Breakdown

## Task List
| Task ID | Function | Task | Owner/Agent |
|---|---|---|---|
| MOD1-T01 | Setup | Configure Supabase project (Auth + email templates + redirect URLs) | devops-deployment |
| MOD1-T02 | Setup | Implement Supabase JWT verification middleware for FastAPI | auth-security-specialist |
| MOD1-T03 | FUN-01-01 | Build verify-student-id endpoint + validation lookup | backend-core-specialist |
| MOD1-T04 | FUN-01-02 | Implement student register endpoint (Supabase Admin API + local DB + phone) | auth-security-specialist |
| MOD1-T05 | FUN-01-05 | Implement `/auth/me` protected endpoint (JWT verify + is_active + email_confirmed) | backend-core-specialist |
| MOD1-T06 | FUN-01-05 | Implement email_confirmed_at sync from Supabase Auth to local DB | auth-security-specialist |
| MOD1-T07 | FUN-01-03 | Set up Supabase client SDK in React Native + login integration | mobile-api-integration |
| MOD1-T08 | FUN-01-04 | Implement Supabase session persistence + auto-refresh on mobile | mobile-state-manager |
| MOD1-T09 | FUN-01-06, FUN-01-07 | Implement password reset flow (Supabase client + deep links) | mobile-api-integration |
| MOD1-T10 | SCR set | Integrate mobile auth screens with backend + Supabase client | mobile-frontend-specialist |
| MOD1-T11 | SCR-NEW | Implement EmailVerificationPendingScreen | mobile-frontend-specialist |
| MOD1-T12 | SCR-NEW | Implement SetNewPasswordScreen + deep link handler | mobile-frontend-specialist |
| MOD1-T13 | QA | Add auth unit/integration/E2E tests | test-automation-specialist |
| MOD1-T14 | QA | Test rate limiting on backend auth endpoints | test-automation-specialist |
| MOD1-T15 | Docs | Update traceability and changelog | docs-writer |

## Done Definition per Task
- Code merged
- Tests pass
- Traceability row updated
- Related docs updated when behavior changes
