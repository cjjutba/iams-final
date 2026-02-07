# Mobile Local State Model

## Suggested Store Domains
| Store | Purpose |
|---|---|
| `authStore` | Faculty session tokens and auth state |
| `facultyScheduleStore` | Schedules, active class, selected class |
| `liveAttendanceStore` | Live roster, scan metadata, session state |
| `manualEntryStore` | Manual attendance draft and submission state |
| `alertStore` | Early-leave alerts and summary cards |
| `profileStore` | Faculty profile and edit form state |
| `notificationStore` | Notification feed and websocket status |

## Common State Fields
- `isLoading`
- `error`
- `lastUpdatedAt`
- `items` / `data`

## Lifecycle Rules
- Hydrate auth and selected cache on app start.
- Clear protected state on logout/session invalidation.
- Keep per-screen transient form errors local to screen state.
