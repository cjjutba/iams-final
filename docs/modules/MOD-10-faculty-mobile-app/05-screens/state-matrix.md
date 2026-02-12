# UI State Matrix

| State | Auth Screens | Schedule/Home Screens | Live/Class Screens | Manual Entry Screen | Profile Screens | Notifications Screen |
|---|---|---|---|---|---|---|
| Initial loading | Show login form | Show schedule/home skeleton | Show roster/detail skeleton | Show form loading state | Show profile skeleton | Show feed skeleton |
| Data loaded | N/A | Render classes and active indicator | Render roster/summary/alerts | Enable submit with valid inputs | Render profile fields | Render event feed |
| Empty state | N/A | Show no-classes message | Show inactive-session or no-alerts message | Show no-edit-needed guidance | Show empty profile placeholders | Show no-notifications message |
| Validation error | Show credential error | N/A | N/A | Field-level errors + block submit | Field-level errors | Parse-safe event fallback |
| API error | Show login error | Retry and preserve filter/context | Retry and preserve selected class | Show error, keep draft values | Retry and preserve edits | Reconnect/retry indicator |
| Auth error (401) | N/A | Attempt refresh → login redirect | Attempt refresh → login redirect | Attempt refresh → login redirect | Attempt refresh → login redirect | Attempt refresh → login redirect |
| WS close 4001 | N/A | N/A | Redirect to login | N/A | N/A | Redirect to login |
| WS close 4003 | N/A | N/A | Show forbidden error | N/A | N/A | Show forbidden error |
| Offline/transient loss | Show network error | Show cached data if available | Show reconnecting status | Keep local draft until network restore | Keep editable local state | Show reconnecting status |

## Auth-Specific State Notes
- Auth screens (SCR-005, SCR-006) are pre-auth — no JWT needed.
- All other screens are post-auth — JWT required for every API call.
- On 401: Axios interceptor attempts refresh. If refresh fails, redirect to login.
- WebSocket close code 4001 clears session and redirects to login.
- WebSocket close code 4003 shows error but does not redirect.

## UX Rules
1. Every API-driven screen must implement loading, empty, and error states.
2. Reconnecting indicator must be visible during WebSocket disconnect.
3. Form drafts survive network errors — never clear user input on transient failure.
4. Auth errors always redirect to login (never show generic error for expired sessions).
5. Active class indicator uses Asia/Manila timezone for resolution.
6. Status badges use `colors.status` tokens only: `present`, `late`, `absent`, `early_leave`.
7. All timestamps display in +08:00 format.
