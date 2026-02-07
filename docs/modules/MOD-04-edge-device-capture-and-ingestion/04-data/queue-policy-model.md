# Queue Policy Model

## Queue Parameters
| Parameter | Value | Description |
|---|---|---|
| max_size | 500 | drop oldest if full |
| ttl | 5 minutes | discard stale entries |
| retry_interval | 10 seconds | delay between retry rounds |
| retry_max_attempts | 3 per batch | then requeue and retry later |
| batch_size | 1 face/request | aligned to API contract |

## Queue Entry Fields
- payload body
- enqueue timestamp
- retry count
- last error (optional)

## Policy Rules
1. Enforce hard cap to bound memory.
2. Remove stale entries before retry.
3. Log drop events and queue depth changes.
