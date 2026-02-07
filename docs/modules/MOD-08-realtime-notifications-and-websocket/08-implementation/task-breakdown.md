# Task Breakdown

## Task Group A: Connection Auth (`FUN-08-01`)
1. Define handshake auth extraction/validation.
2. Validate path `user_id` against auth subject.
3. Add connection registration and cleanup hooks.

## Task Group B: Event Publication (`FUN-08-02`, `FUN-08-03`, `FUN-08-04`)
1. Implement event builders with strict schema checks.
2. Integrate publisher calls in attendance and presence flows.
3. Add optional delivery logging and error handling.

## Task Group C: Reliability (`FUN-08-05`)
1. Implement heartbeat/ping-pong handling.
2. Implement stale socket pruning.
3. Validate reconnect behavior with repeated network drops.

## Task Group D: Mobile Wiring
1. Subscribe screens to websocket service.
2. Map event types to UI updates.
3. Add connection-state indicators and fallback UI.

## Task Group E: Verification
1. Execute `T08-U*`, `T08-I*`, `T08-S*` tests.
2. Capture demo evidence and update checklist.
