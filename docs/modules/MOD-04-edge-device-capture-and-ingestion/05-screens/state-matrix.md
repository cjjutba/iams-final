# Runtime State Matrix

| Runtime Component | Normal State | Failure State | Recovery Action |
|---|---|---|---|
| Camera | capturing | disconnected | retry every 5s |
| Sender | posting payload | network/server error | enqueue + retry later |
| Queue | bounded active | overflow risk | drop oldest + log |
| Retry worker | periodic resend | repeated failure | requeue + backoff interval |

## Required Runtime Rules
- Capture loop should continue during sender failures.
- Queue policy should remain bounded at all times.
