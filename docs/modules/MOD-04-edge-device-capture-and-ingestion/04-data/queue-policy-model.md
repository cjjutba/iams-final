# Queue Policy Model

## Queue Parameters
| Parameter | Value | Description |
|---|---|---|
| max_size | 500 | Drop oldest if full (`collections.deque(maxlen=500)`) |
| ttl | 5 minutes | Discard stale entries before retry |
| retry_interval | 10 seconds | Delay between retry rounds |
| retry_max_attempts | 3 per batch | Then requeue and retry later |

## Send Policy
| Parameter | Value | Description |
|---|---|---|
| batch_size | 1 face/request | Aligned to `POST /face/process` API contract |
| auth_header | `X-API-Key` | Required on every send and retry request |

## Queue Entry Fields
- payload body (JSON matching `/face/process` contract)
- enqueue timestamp
- retry count
- last error (optional)

## Policy Rules
1. Enforce hard cap (500 items) to bound memory.
2. Remove stale entries (older than 5 minutes) before retry.
3. Log drop events and queue depth changes.

## Idempotency Considerations
Edge may retry sending the same face crop multiple times due to transient failures. Backend `/face/process` should handle idempotent recognition (e.g., by tracking frame timestamps). MOD-06 attendance logic should ensure duplicate detections from the same timestamp are not counted twice.
