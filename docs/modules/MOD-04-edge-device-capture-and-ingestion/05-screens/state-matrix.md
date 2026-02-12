# Runtime State Matrix

| Runtime Component | Normal State | Failure State | Recovery Action |
|---|---|---|---|
| Camera | Capturing (640x480, 15 FPS) | Disconnected | Retry every 5s |
| Sender | POSTing payload with `X-API-Key` | Network/server error | Enqueue + retry later |
| Sender | POSTing payload with `X-API-Key` | 401 auth failure | Log error, check config (do NOT queue) |
| Queue | Bounded active (max 500) | Overflow risk | Drop oldest + log |
| Retry worker | Periodic resend (10s interval) | Repeated failure | Requeue + backoff interval |

## Required Runtime Rules
- Capture loop should continue during sender failures (non-blocking).
- Queue policy should remain bounded at all times (500 max, 5-min TTL).
- Auth failures (401) should be logged and NOT queued for retry (configuration issue, not transient).
