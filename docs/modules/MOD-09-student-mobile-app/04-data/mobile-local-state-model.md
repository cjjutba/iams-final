# Mobile Local State Model

## Suggested Store Domains
| Store | Purpose |
|---|---|
| `authStore` | Session tokens, user identity, auth status |
| `registrationStore` | Step data and validation across registration flow |
| `attendanceStore` | Home/history/detail data and filters |
| `scheduleStore` | Student schedule list and selected schedule |
| `profileStore` | Profile details and edit state |
| `notificationStore` | Student notification feed and connection state |

## Common State Fields
- `isLoading`
- `error`
- `lastUpdatedAt`
- `items` / `data`

## Lifecycle Notes
- Hydrate auth and selected caches on app start.
- Clear protected state on logout/token invalidation.
- Keep transient form errors scoped to active screen.
