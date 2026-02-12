# Test Cases (MOD-04)

## Unit Tests
| ID | Function | Scenario | Expected |
|---|---|---|---|
| T04-U1 | FUN-04-01 | Camera frame read success | Frame emitted at 640x480 |
| T04-U2 | FUN-04-02 | Frame with faces | Crops (~112x112) generated via MediaPipe |
| T04-U3 | FUN-04-03 | Payload build + send success | Request includes `X-API-Key` header and correct schema |
| T04-U4 | FUN-04-04 | Queue overflow (>500 items) | Oldest dropped, queue size = 500 |
| T04-U5 | FUN-04-04 | Queue TTL expiry (>5 min) | Stale entries removed before retry |
| T04-U6 | FUN-04-05 | Retry cycle with failures | Requeue and continue, max 3 attempts per batch |
| T04-U7 | FUN-04-03 | API key header inclusion | `X-API-Key` header present on every request |
| T04-U8 | FUN-04-02 | Crop size verification | Crops are ~112x112, NOT resized to 160x160 |

## Integration Tests
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T04-I1 | POST /face/process | Valid payload + valid API key | `200`, processed/matched fields |
| T04-I2 | POST /face/process | Invalid payload + valid API key | `400` validation error |
| T04-I3 | POST /face/process | Backend unavailable | Send failure queued |
| T04-I4 | POST /face/process | Endpoint restored | Queued sends eventually delivered |
| T04-I5 | POST /face/process | Missing `X-API-Key` header | `401` UNAUTHORIZED |
| T04-I6 | POST /face/process | Invalid API key | `401` UNAUTHORIZED |
| T04-I7 | POST /face/process | Valid payload, deleted user face | `200`, user returned as unmatched |

## Scenario Tests
| ID | Flow | Expected |
|---|---|---|
| T04-S1 | RPi queue when server down | Queue fills to bound (500) without crash |
| T04-S2 | Backend restart recovery | Queued payloads drained with `X-API-Key` header |
| T04-S3 | Camera disconnect | Reconnect attempts every 5s |
| T04-S4 | Auth failure (401) | Error logged, NOT queued for retry |
