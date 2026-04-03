---
name: Token Management Architecture
description: Volatile cache pattern for TokenManager and Mutex-based refresh serialization in TokenAuthenticator
type: project
---

## TokenManager Volatile Cache
- 4 `@Volatile` backing fields: `_accessToken`, `_refreshToken`, `_userRole`, `_userId`
- `init {}` block launches coroutine on `Dispatchers.IO + SupervisorJob()` to load from DataStore
- Public getters return volatile fields directly (zero blocking)
- `saveTokens()` sets volatile fields BEFORE awaiting DataStore write
- `clearTokens()` nulls volatile fields BEFORE clearing DataStore
- Tradeoff: very brief window after construction where tokens are null until DataStore loads

**Why:** `runBlocking` on DataStore access caused ANR risk on main thread and perf issues on OkHttp threads.

**How to apply:** Any new token fields should follow the same pattern -- add volatile backing field, load in init, update in save/clear.

## TokenAuthenticator Mutex Pattern
- `private val refreshMutex = Mutex()` serializes all refresh attempts
- Inside lock: compare `response.request.header("Authorization")` with `tokenManager.accessToken`
- If tokens differ, another thread already refreshed -- skip refresh, retry with new token
- All `tokenManager.clearTokens()` calls are now inside the `runBlocking` coroutine scope (suspend-friendly)

**Why:** Without serialization, N concurrent 401s trigger N refresh calls, wasting the refresh token and causing race conditions.

**How to apply:** If refresh endpoint ever changes (e.g., different response shape), update the freshTokens parsing inside the lock.
