# Goal and Objectives

## Module Goal
Deliver a complete faculty mobile experience for class monitoring, manual attendance control, early-leave visibility, and operational notifications.

## Auth Context
MOD-10 bridges pre-auth and post-auth within one mobile app. Faculty login (SCR-005, SCR-006) is pre-auth. All faculty portal screens (SCR-019 to SCR-029) are post-auth and require a backend-issued JWT. Faculty accounts are pre-seeded — no self-registration in MVP.

## Problem Statement
Faculty need real-time visibility and intervention tools during classes. Without a focused mobile interface, live monitoring and correction workflows become slow and unreliable.

## Stakeholders
| Stakeholder | Role | Module Reference |
|---|---|---|
| Faculty users | Primary users of MOD-10 screens | MOD-10 |
| Backend auth (MOD-01) | Issues JWT, validates credentials | MOD-01 |
| User profiles (MOD-02) | Profile fetch/update endpoints | MOD-02 |
| Schedule/enrollment (MOD-05) | Faculty schedule and class roster data | MOD-05 |
| Attendance records (MOD-06) | Live/today/manual attendance endpoints | MOD-06 |
| Presence tracking (MOD-07) | Early-leave alerts and presence logs | MOD-07 |
| WebSocket transport (MOD-08) | Real-time event delivery | MOD-08 |
| Student mobile (MOD-09) | Shared mobile architecture patterns | MOD-09 |

## Objectives
1. Provide secure faculty login with backend-issued JWT and stable session restore via Expo SecureStore.
2. Show faculty schedule and identify active class context with Asia/Manila timezone (+08:00).
3. Provide live attendance monitoring for in-session classes via WebSocket.
4. Enable manual attendance updates with clear feedback using HTTP response envelope.
5. Expose early-leave alerts and class summary views.
6. Provide faculty profile and notification experiences with WebSocket reconnect handling.

## MVP Success Signals
- Faculty can log in using pre-seeded credentials (pre-auth endpoint, no JWT needed).
- All post-auth endpoints reject requests without valid JWT (401).
- Faculty can monitor active class attendance in real time via WebSocket (JWT via query param).
- Manual attendance entry updates class data reliably with proper response envelope.
- Early-leave and summary signals are visible without app restart after reconnect.
- Timestamps display in Asia/Manila timezone (+08:00).

## Non-Goals for MOD-10
- Faculty self-registration (explicitly out of MVP).
- Admin-grade schedule management tools.
- Cross-campus analytics dashboards.
