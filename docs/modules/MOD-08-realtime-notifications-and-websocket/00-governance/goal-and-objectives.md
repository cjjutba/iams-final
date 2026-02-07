# Goal and Objectives

## Module Goal
Deliver stable realtime attendance and early-leave notifications from backend to mobile clients using authenticated WebSocket connections.

## Problem Statement
Attendance and early-leave state changes are time-sensitive. Polling APIs alone can cause delay, stale screens, and weak classroom monitoring.

## Objectives
1. Open and maintain authenticated WebSocket sessions per user.
2. Publish standardized events for attendance updates, early-leave alerts, and session-end summaries.
3. Keep mobile notification screens in sync without app restart.
4. Handle disconnect/reconnect and stale connection cleanup safely.
5. Preserve clean boundaries with attendance and presence modules.

## MVP Success Signals
- Faculty sees attendance updates in near real time during live class.
- Faculty receives early-leave alert events during session.
- Student and faculty notification screens reflect new events after reconnect.
- No unbounded growth in connection map or stale sessions.

## Non-Goals for MOD-08
- Push notifications through FCM/APNs.
- Guaranteed durable message queue for offline clients.
- Analytics dashboards for notification metrics.
