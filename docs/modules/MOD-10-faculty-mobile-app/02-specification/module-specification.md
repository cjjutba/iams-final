# Module Specification

## Module
- ID: `MOD-10`
- Name: Faculty Mobile App

## Purpose
Give faculty live visibility and control for class attendance.

## Auth Context
Faculty login (SCR-005, SCR-006) is pre-auth. All portal screens (SCR-019 to SCR-029) are post-auth. Backend-issued JWT stored in Expo SecureStore. WebSocket uses JWT via `token` query param.

## Functions
| Function ID | Function Name | Auth Type |
|---|---|---|
| FUN-10-01 | Faculty login and session restore | Pre-auth → Post-auth |
| FUN-10-02 | View schedule and active class | Post-auth |
| FUN-10-03 | Live attendance monitoring | Post-auth + WebSocket |
| FUN-10-04 | Manual attendance updates | Post-auth |
| FUN-10-05 | View early-leave alerts and class summaries | Post-auth + WebSocket |
| FUN-10-06 | Faculty profile and notifications | Post-auth + WebSocket |

## Screens
- Pre-auth: `SCR-005`, `SCR-006`
- Post-auth: `SCR-019`, `SCR-020`, `SCR-021`, `SCR-022`, `SCR-023`, `SCR-024`, `SCR-025`, `SCR-026`, `SCR-027`, `SCR-028`, `SCR-029`

## Cross-Module Dependencies
| Module | What MOD-10 Needs | Auth Note |
|---|---|---|
| MOD-01 | Login, refresh, me endpoints | Pre-auth (login) / Post-auth (refresh, me) |
| MOD-02 | Profile fetch/update endpoints | Post-auth |
| MOD-05 | Schedule and class roster data | Post-auth |
| MOD-06 | Live/today/manual attendance endpoints | Post-auth |
| MOD-07 | Early-leave alerts and presence logs | Post-auth |
| MOD-08 | WebSocket real-time transport | Post-auth (JWT via query param) |

## Done Criteria
- Faculty can monitor a live class end-to-end.
- Manual entry updates are reflected in live/history views.
- Alert screens show realtime events.
- Pre-auth endpoints work without JWT; post-auth endpoints reject without JWT (401).
- Tokens stored in Expo SecureStore, never AsyncStorage.
- Timestamps display in Asia/Manila timezone (+08:00).
- HTTP response envelope parsed without assuming `details` array.
- Design system constraints followed.
