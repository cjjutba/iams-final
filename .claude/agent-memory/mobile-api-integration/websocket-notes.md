---
name: WebSocket Client Architecture
description: AttendanceWebSocketClient constructor change, auth headers, reconnect-on-close behavior
type: project
---

## Constructor Change (Stream J)
- Old: `AttendanceWebSocketClient(baseUrl: String)` -- created its own OkHttpClient internally
- New: `AttendanceWebSocketClient(baseUrl: String, client: OkHttpClient, tokenProvider: () -> String?)`
- Shared OkHttpClient avoids resource duplication; tokenProvider enables auth headers on WS connect

**Breaking change:** `FacultyLiveFeedViewModel.kt` line 51 must be updated to pass:
1. The shared Hilt-provided `OkHttpClient`
2. A `tokenProvider` lambda (e.g., `{ tokenManager.accessToken }`)

This requires injecting `OkHttpClient` and `TokenManager` into the ViewModel.

## Auth Header
- `doConnect()` adds `Authorization: Bearer <token>` header to the WS upgrade request
- Only added when `tokenProvider()` returns non-null

## Reconnect on Close
- `onClosed()` now calls `scheduleReconnect()` (previously only `onFailure` did)
- This handles server-initiated graceful close (e.g., session end, server restart)
- `disconnect()` sets `targetScheduleId = null` which prevents `scheduleReconnect()` from firing

## destroy() Safety
- No longer calls `client.dispatcher.executorService.shutdown()` or similar
- Just `disconnect()` + `scope.cancel()` since the client is shared
