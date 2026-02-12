# Mobile Local State Model

## Store Domains (Zustand)
| Store | Purpose | Auth Context |
|---|---|---|
| `authStore` | Session tokens, user identity, auth status | Post-auth (hydrated from SecureStore) |
| `registrationStore` | Step data and validation across registration flow | Pre-auth → Post-auth |
| `attendanceStore` | Home/history/detail data and filters | Post-auth |
| `scheduleStore` | Student schedule list and selected schedule | Post-auth |
| `profileStore` | Profile details and edit state | Post-auth |
| `notificationStore` | Student notification feed and connection state | Post-auth |

## Common State Fields
- `isLoading: boolean`
- `error: string | null`
- `lastUpdatedAt: string | null` (ISO-8601 with +08:00)
- `items` / `data`

## Auth Store Structure
```typescript
interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  error: string | null;
}
```

## Lifecycle Notes
- Hydrate auth from Expo SecureStore on app start (before rendering protected screens).
- Clear all protected state on logout/token invalidation.
- Keep transient form errors scoped to active screen.
- Registration draft data cleared on successful submit or explicit cancel.
- Notification store persists connection state for reconnect handling.

## Storage Strategy
| Data | Storage Mechanism | Reason |
|---|---|---|
| Auth tokens | Expo SecureStore | Security (encrypted) |
| First-launch flag | AsyncStorage | Non-sensitive |
| Attendance cache | AsyncStorage (optional) | Offline display fallback |
| Schedule cache | AsyncStorage (optional) | Faster startup |
| Notification cache | AsyncStorage (optional) | Preserve UX on reconnect |
