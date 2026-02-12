# Mobile Local State Model

## Suggested Store Domains
| Store | Auth Context | Purpose |
|---|---|---|
| `authStore` | Post-auth | Faculty session tokens and auth state |
| `facultyScheduleStore` | Post-auth | Schedules, active class, selected class |
| `liveAttendanceStore` | Post-auth | Live roster, scan metadata, session state |
| `manualEntryStore` | Post-auth | Manual attendance draft and submission state |
| `alertStore` | Post-auth | Early-leave alerts and summary cards |
| `profileStore` | Post-auth | Faculty profile and edit form state |
| `notificationStore` | Post-auth | Notification feed and websocket status |

## Auth Store Structure
```typescript
interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: {
    id: string;
    email: string;
    role: 'faculty';
    first_name: string;
    last_name: string;
  } | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}
```

## Storage Strategy
| Data | Storage | Reason |
|---|---|---|
| Access token | Expo SecureStore | Sensitive credential |
| Refresh token | Expo SecureStore | Sensitive credential |
| User ID / role | Expo SecureStore | Auth context |
| Schedule cache | AsyncStorage | Non-sensitive, faster startup |
| Notification cache | AsyncStorage | Non-sensitive, feed continuity |
| Onboarding flag | AsyncStorage | Non-sensitive preference |

## Common State Fields
- `isLoading`
- `error`
- `lastUpdatedAt`
- `items` / `data`

## Lifecycle Rules
- Hydrate auth from SecureStore and schedule cache from AsyncStorage on app start.
- Clear all protected state (SecureStore + AsyncStorage caches) on logout/session invalidation.
- Keep per-screen transient form errors local to screen state.
