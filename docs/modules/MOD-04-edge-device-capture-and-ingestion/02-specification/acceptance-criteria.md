# Acceptance Criteria

## Function-Level Acceptance

### FUN-04-01
- Given available camera, runtime captures frames at configured settings.
- Given camera disconnect, runtime retries and recovers.

### FUN-04-02
- Given frame with faces, crops and bbox metadata are produced.
- Given frame without faces, pipeline continues without errors.

### FUN-04-03
- Given valid crop payload, request to `/face/process` succeeds.
- Given send error, failure is reported to queue path.

### FUN-04-04
- Given send failure, payload is queued.
- Given full queue, oldest entries are dropped.
- Given expired entries, TTL removal occurs.

### FUN-04-05
- Given queued items and restored connectivity, retries deliver payloads.
- Retry behavior does not block capture loop.

## Module-Level Acceptance
- Queue policy behavior matches documented values.
- Edge runtime remains stable during intermittent backend outages.
- Logs provide enough detail for troubleshooting queue/retry behavior.
