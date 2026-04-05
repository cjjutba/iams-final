---
name: Security Audit 2026-03-30
description: Comprehensive security audit findings for IAMS backend and Android client - 5 Critical, 8 High, 10 Medium, 6 Low issues found
type: project
---

## Security Audit Completed 2026-03-30

**Why:** Full audit requested to identify vulnerabilities before production deployment.

**Key Critical Findings:**
- WebSocket endpoints (attendance + alerts) have ZERO authentication
- Edge API endpoints (/face/process, /face/gone, /face/recognize) have no auth — EDGE_API_KEY exists in config but is never checked
- JWT SECRET_KEY has a weak default fallback in config.py
- RefreshToken model exists in DB but is completely unused — no rotation, no revocation, logout is a no-op
- Rate limiting only on check-student-id and verify-student-id; missing on login, register, refresh, change-password
- CORS is wildcard ["*"] with allow_credentials=True
- Faculty can update any user's profile and deregister any user's face (privilege escalation)
- No content-type/magic-byte validation on face image uploads
- Android uses cleartext HTTP, no cert pinning, tokens in unencrypted DataStore, debug logging in prod builds

**How to apply:** When implementing fixes, prioritize: (1) WebSocket auth, (2) Edge API key auth, (3) rate limiting on auth endpoints, (4) refresh token rotation using existing RefreshToken model, (5) CORS lockdown for production.
