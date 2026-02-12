# Glossary

- **Faculty stack**: Authenticated faculty-only navigation scope (post-auth screens SCR-019 to SCR-029).
- **Active class**: Schedule context currently in-session by day/time, resolved using Asia/Manila timezone.
- **Live roster**: Dynamic per-student attendance state for current class, updated via WebSocket events.
- **Manual override**: Faculty-issued attendance correction via dedicated `POST /attendance/manual` API.
- **Alert feed**: Ordered list of early-leave and related warning events from `/presence/early-leaves`.
- **Session restore**: Token/session hydration from Expo SecureStore during app startup.
- **Summary card**: Class-level status totals shown at session end.
- **UI state triad**: Loading, empty, and error handling for each data view.
- **Pre-auth endpoint**: API endpoint that requires no JWT token (e.g., `/auth/login`, `/auth/forgot-password`).
- **Post-auth endpoint**: API endpoint that requires `Authorization: Bearer <token>` header.
- **Backend-issued JWT**: Access/refresh token pair issued by the FastAPI backend (not Supabase client SDK). Stored in Expo SecureStore.
- **Event envelope**: WebSocket message format `{ "type": "...", "data": { ... } }`. Distinct from HTTP response envelope.
- **HTTP response envelope**: Standard API response shape. Success: `{ "success": true, "data": {}, "message": "" }`. Error: `{ "success": false, "error": { "code": "", "message": "" } }`. No `details` array.
- **Timezone**: Asia/Manila (UTC+08:00). All timestamps use ISO-8601 with `+08:00` offset.
- **Expo SecureStore**: Encrypted key-value storage on device. Used for JWT tokens and sensitive auth data. Never use AsyncStorage for tokens.
- **Design system constraints**: Component-level restrictions — Text weight types, Avatar styling, Divider spacing, colors.status limits. See `mvp-scope.md`.
