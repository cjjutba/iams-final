# Session 04 — TimeSyncClient

**Deliverable:** a lightweight HTTP-based clock-skew estimator for the Android app.
**Blocks:** session 06, 09.
**Blocked by:** session 05 must ship the `/health/time` endpoint **before** Session 04 can integration-test, but Session 04 can implement against the contract while 05 is in flight.
**Est. effort:** 2 hours.

Read [00-master-plan.md](00-master-plan.md) §5.4.

---

## 1. Scope

Implement `com.iams.app.data.sync.TimeSyncClient` and its default implementation. This measures the delta between the device clock and the backend clock so the matcher can (eventually) align timestamps in backend WS messages with phone wall-clock. Also exposes RTT for the diagnostic HUD (session 08).

**No NTP library. No external deps.** Just an existing OkHttp client + a simple algorithm.

## 2. Files

| Path | New? |
|------|------|
| `android/app/src/main/java/com/iams/app/data/sync/TimeSyncClient.kt` | NEW |
| `android/app/src/main/java/com/iams/app/di/TimeSyncModule.kt` | NEW |

## 3. Algorithm

Classic "Cristian" clock synchronisation:

```
t0 = device_ms before request
response = GET /api/v1/health/time   → { server_time_ms }
t1 = device_ms after response
rtt = t1 - t0
estimated_server_ms_at_t1 = server_time_ms + rtt/2
skew_ms = estimated_server_ms_at_t1 - t1          (can be positive or negative)
```

Keep a rolling window of 5 samples. Use the **median** for robust skew, **min** for last RTT. Discard any sample where `rtt > 2000ms` (bad network).

Poll every 60 seconds when the Live Feed is open. Poll once immediately on `start()`.

## 4. Interface (frozen — master §5.4)

```kotlin
interface TimeSyncClient {
    val skewMs: StateFlow<Long>
    val lastRttMs: StateFlow<Long>
    fun start(baseUrl: String)
    fun stop()
}
```

## 5. Implementation steps

### Step 1 — `TimeSyncClient.kt`

```kotlin
@Singleton
class DefaultTimeSyncClient @Inject constructor(
    private val okHttpClient: OkHttpClient,   // from existing NetworkModule
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO),
) : TimeSyncClient {

    private val _skewMs = MutableStateFlow(0L)
    override val skewMs: StateFlow<Long> = _skewMs.asStateFlow()
    private val _lastRttMs = MutableStateFlow(-1L)
    override val lastRttMs: StateFlow<Long> = _lastRttMs.asStateFlow()

    private var job: Job? = null
    private val samples = ArrayDeque<Long>()

    override fun start(baseUrl: String) {
        if (job != null) return
        job = scope.launch {
            while (isActive) {
                try { pollOnce(baseUrl) } catch (_: Exception) {}
                delay(60_000)
            }
        }
    }

    override fun stop() {
        job?.cancel(); job = null
        samples.clear()
        _skewMs.value = 0L
        _lastRttMs.value = -1L
    }

    private suspend fun pollOnce(baseUrl: String) { /* see Step 2 */ }
}
```

### Step 2 — `pollOnce`

```kotlin
private suspend fun pollOnce(baseUrl: String) = withContext(Dispatchers.IO) {
    val url = "$baseUrl/api/v1/health/time"
    val t0 = System.currentTimeMillis()
    val body = okHttpClient.newCall(Request.Builder().url(url).build()).execute().use { resp ->
        if (!resp.isSuccessful) return@withContext
        resp.body?.string() ?: return@withContext
    }
    val t1 = System.currentTimeMillis()
    val rtt = t1 - t0
    if (rtt > 2_000) return@withContext

    val serverMs = JSONObject(body).optLong("server_time_ms", -1L)
    if (serverMs <= 0) return@withContext

    val skew = (serverMs + rtt / 2) - t1

    samples.addLast(skew)
    while (samples.size > 5) samples.removeFirst()
    _skewMs.value = samples.sorted()[samples.size / 2]  // median
    _lastRttMs.value = rtt
}
```

Use `org.json.JSONObject` — no Moshi/Gson coupling needed, one field.

### Step 3 — `TimeSyncModule.kt` (Hilt)

```kotlin
@Module
@InstallIn(SingletonComponent::class)
abstract class TimeSyncModule {
    @Binds
    abstract fun bindTimeSync(impl: DefaultTimeSyncClient): TimeSyncClient
}
```

## 6. Acceptance criteria

- [ ] Compiles.
- [ ] When the backend `/api/v1/health/time` endpoint is up, `skewMs` is set within 2 seconds of `start()`.
- [ ] With the backend down, `skewMs` stays at `0L` and `lastRttMs` stays at `-1L`.
- [ ] Calling `start()` twice is a no-op (idempotent).
- [ ] `stop()` cleans up the coroutine (verified via `job.isActive == false` in a test).
- [ ] No memory growth (`samples` capped at 5).
- [ ] No crash when the JSON body is malformed (missing `server_time_ms` → skip sample).

## 7. Anti-goals

- Do not add SNTP.
- Do not poll more often than every 60 s (would spam the backend).
- Do not use `System.nanoTime()` — we need wall-clock to compare to `server_time_ms`.
- Do not block the main thread.
- Do not expose the sample buffer.

## 8. Handoff notes

**For Session 06:** inject via Hilt, call `start(backendBaseUrl)` in the Live Feed ViewModel `init`. Call `stop()` in `onCleared()`.

**For Session 09 (fallback):** the fallback controller reads `lastRttMs` to decide if the WebSocket is healthy (if RTT > 1 s consistently, prefer fallback mode).

## 9. Risks

- **Timezone mismatch:** `server_time_ms` MUST be UTC epoch. Session 05 must enforce this. If the phone's clock is set wrong (user travel), skew estimate will be large but still valid for aligning frame timestamps.
- **Network quantisation:** first RTT after app resume can be inflated by connection warm-up. The 2000 ms sample-rejection threshold prevents pollution.

## 10. Commit message template

```
hybrid(04): add TimeSyncClient for phone/backend clock skew

Lightweight Cristian-style clock sync over GET /api/v1/health/time.
Exposes skewMs + lastRttMs StateFlows for the matcher and diagnostic HUD.

Session 05 ships the server endpoint; session 06 wires this into the
Live Feed ViewModel.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## 11. Lessons

- Cristian's algorithm is enough for < 100 ms accuracy; skipping NTP removed a heavy dependency.
- Median of 5 samples > mean: rejects single bad RTT without math.
