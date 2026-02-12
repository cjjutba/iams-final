# Module Dependency Order

## Prerequisites Before MOD-10
| Module | What MOD-10 Needs | Auth Note |
|---|---|---|
| MOD-01 | Login, refresh, me endpoints | Pre-auth (login, forgot-password) / Post-auth (refresh, me) |
| MOD-02 | Profile fetch/update endpoints | Post-auth |
| MOD-05 | Schedule and class roster data | Post-auth |
| MOD-06 | Live/today/manual attendance endpoints | Post-auth |
| MOD-07 | Early-leave alerts and presence logs | Post-auth |
| MOD-08 | WebSocket real-time transport | Post-auth (JWT via query param) |

## Adjacent Modules
- `MOD-02` User and Profile Management (profile update endpoints)
- `MOD-09` Student Mobile App (shared mobile architecture patterns, Axios interceptors, SecureStore, design system)

## Auth Dependencies
- MOD-01 must provide `POST /auth/login` (pre-auth) and `POST /auth/refresh` (post-auth).
- MOD-01 must provide `GET /auth/me` (post-auth) for faculty profile context.
- MOD-08 must accept JWT via `token` query parameter for WebSocket connection.
- MOD-08 must return close codes 4001 (unauthorized) and 4003 (forbidden).

## Sequence Note
Implement MOD-10 after core attendance/presence/realtime contracts are stable for mobile consumption.
