---
name: Audit Stream A - Security Fixes Applied
description: Stream A of the security audit fix plan executed 2026-03-30 covering config validation, PyJWT migration, rate limiting, and threshold fix
type: project
---

## Stream A Security Fixes (2026-03-30)

**A1 - config.py:**
- Startup validation blocks SECRET_KEY and EDGE_API_KEY defaults when DEBUG=False (RuntimeError)
- CORS_ORIGINS default changed from `["*"]` to `[]` (must be explicitly set)
- Adaptive threshold floor/ceiling were inverted (floor=0.35 > ceiling=0.30); fixed to floor=0.30, ceiling=0.45

**A2 - security.py:**
- Migrated from python-jose to PyJWT (`import jwt` / `from jwt.exceptions import ...`)
- Replaced all `datetime.utcnow()` with `datetime.now(timezone.utc)` (5 occurrences)
- Exception class changed: `JWTError` -> `InvalidTokenError`
- PyJWT API: `jwt.encode()` uses singular `algorithm=`, `jwt.decode()` uses plural `algorithms=[]` (already correct)

**A3 - auth.py:**
- Added `@limiter.limit(settings.RATE_LIMIT_AUTH)` + `request: Request` param to `/refresh` and `/change-password`
- Note: `/login` and `/register` also lack limiter decorators but were out of scope for this stream

**A4 - requirements.txt:**
- Line 23: `python-jose==3.5.0` -> `PyJWT>=2.8.0`

**Why:** Security audit on 2026-03-30 identified these as critical/high findings.
**How to apply:** Remaining test file `backend/tests/unit/test_security.py` still imports from jose and will need updating separately.
