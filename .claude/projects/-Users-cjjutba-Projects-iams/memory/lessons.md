# Lessons

## 2026-04-03: Admin portal API integration findings
- The admin portal uses FastAPI backend for all data — NOT Supabase directly (except email-confirmed.tsx for mobile user redirect links)
- Backend error format: `{"success": false, "error": {"code": "AuthenticationError", "message": "..."}}` — admin portal extracts `error.response?.data?.error?.message`
- Admin calls `/analytics/at-risk` but backend has `/analytics/at-risk-students` — path mismatch causes 404
- Admin calls `/analytics/class/{id}` but backend has `/analytics/class/{id}/overview` — path mismatch
- Password `"123"` doesn't meet `validate_password_strength()` rules (>=8 chars) but that validation is only on API endpoints, not seed scripts which call `hash_password()` directly — login just uses `verify_password()` which is hash-only
- The Vite dev server proxy in `vite.config.ts` routes `/api/*` → `http://localhost:8000`, so no CORS issues in dev
- The audit_logs migration already exists (`c3d4e5f6a7b8`) with columns: id, admin_id, action, target_type, target_id, details, created_at — model must match

## 2026-04-04: FAISS user_map must always pair with index reload
- Every `faiss_manager.load_or_create_index()` MUST be followed by `faiss_manager.rebuild_user_map_from_db()` — forgetting this causes FAISS to find matching vectors but return None for user_id, making registered faces show as "Unknown"
- Three call sites (main.py startup, main.py self-heal, presence.py manual start) were missing the rebuild call; the Redis pubsub listener was the only one doing it correctly
- Unknown tracks need spatial deduplication by IoU just like recognized tracks need user_id deduplication — ByteTrack can assign different track IDs to overlapping detections of the same face
- Hardcoded UX delays in overlays (e.g., 2s UNKNOWN_LABEL_DELAY_MS) compound with real pipeline latency and should be zero for real-time systems
