# Test Cases (MOD-04)

## Unit Tests
| ID | Function | Scenario | Expected |
|---|---|---|---|
| T04-U1 | FUN-04-01 | camera frame read success | frame emitted |
| T04-U2 | FUN-04-02 | frame with faces | crops generated |
| T04-U3 | FUN-04-03 | payload build + send success | request accepted |
| T04-U4 | FUN-04-04 | queue overflow | oldest dropped |
| T04-U5 | FUN-04-04 | queue ttl expiry | stale entries removed |
| T04-U6 | FUN-04-05 | retry cycle with failures | requeue and continue |

## Integration Tests
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T04-I1 | POST /face/process | valid payload | `200`, processed/matched fields |
| T04-I2 | POST /face/process | invalid payload | `400` |
| T04-I3 | POST /face/process | backend unavailable | send failure queued |
| T04-I4 | POST /face/process | endpoint restored | queued sends eventually delivered |

## Scenario Tests
| ID | Flow | Expected |
|---|---|---|
| T04-S1 | RPi queue when server down | queue fills to bound without crash |
| T04-S2 | backend restart recovery | queued payloads drained |
| T04-S3 | camera disconnect | reconnect attempts every 5s |
