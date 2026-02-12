# UI State Matrix

| State | Onboarding Screens | Registration Screens | Attendance/Schedule Screens | Profile Screens | Notifications Screen |
|---|---|---|---|---|---|
| Initial loading | Splash evaluation | Step skeleton/loading indicator | Skeleton/list loader | Profile skeleton | Feed skeleton |
| Valid data loaded | Route determined | Enable continue action | Render lists/cards/details | Render profile fields | Render notification feed |
| Empty state | N/A | Initial form state | Show empty message and CTA | Show empty placeholders | Show no-notifications message |
| Validation error | N/A | Field errors + block next step | Filter/input errors | Field-level errors | Parse-safe fallback |
| API error | N/A | Retry + keep draft values | Retry and preserve filters | Retry + preserve unsaved edits | Reconnect/retry indicator |
| Auth error (401) | N/A | N/A (pre-auth) or refresh+login | Refresh attempt → login redirect | Refresh attempt → login redirect | Refresh attempt → login redirect |
| WebSocket close 4001 | N/A | N/A | N/A | N/A | Redirect to login screen |
| WebSocket close 4003 | N/A | N/A | N/A | N/A | Show permission error message |
| Offline/transient loss | N/A | Save draft locally | Show cached data if available | Keep editable local state | Show reconnecting status + backoff |

## Auth-Specific State Notes
- Pre-auth screens (SCR-001 to SCR-008): No 401 handling needed — endpoints don't require JWT.
- Post-auth screens (SCR-009 to SCR-018): All must handle 401 → refresh → login redirect.
- WebSocket screen (SCR-018): Must handle close codes 4001 (→ login) and 4003 (→ error message).

## UX Rules
1. All data-driven screens must implement loading, empty, and error states.
2. Pull-to-refresh available on list screens (schedule, history, notifications).
3. Show reconnecting badge/indicator when WebSocket is disconnected.
4. Auth errors redirect to login; do not show raw error messages.
5. Preserve form state across validation errors (do not clear inputs).
6. Timestamps displayed in Asia/Manila timezone format (+08:00).
7. Use exponential backoff for WebSocket reconnect attempts.
