# Acceptance Criteria

## Function-Level Acceptance

### FUN-04-01
- Given available camera, runtime captures frames at 640x480 and 15 FPS.
- Given camera disconnect, runtime retries connection every 5 seconds and recovers.

### FUN-04-02
- Given frame with faces, crops (~112x112) and bbox metadata are produced via MediaPipe.
- Given frame without faces, pipeline continues without errors.

### FUN-04-03
- Given valid crop payload and valid API key, request to `/face/process` succeeds.
- Given missing or invalid `X-API-Key` header, backend returns 401.
- Given send error (network/server), failure is reported to queue path.

### FUN-04-04
- Given send failure, payload is queued.
- Given full queue (500 items), oldest entries are dropped.
- Given expired entries (older than 5 minutes), TTL removal occurs before retry.

### FUN-04-05
- Given queued items and restored connectivity, retries deliver payloads (with `X-API-Key` header).
- Retry behavior does not block capture loop (non-blocking).
- Retry respects 10-second interval and 3-attempt max per batch.

## Module-Level Acceptance
- Queue policy behavior matches documented values (500 max, 5-min TTL, 10s retry, 3 attempts).
- Edge runtime remains stable during intermittent backend outages.
- Logs provide enough detail for troubleshooting queue/retry behavior.
- `X-API-Key` header is present on every outbound request.
- Edge crops at ~112x112; does NOT resize to 160x160.
