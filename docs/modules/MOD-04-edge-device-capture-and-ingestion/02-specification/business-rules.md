# Business Rules

## Pipeline Rules
1. Capture -> detect -> crop -> compress -> send must run in ordered pipeline.
2. Send operation failure must not crash runtime.
3. Queue fallback is mandatory on backend unavailability.

## Queue Rules
1. Max queue size is 500 items.
2. Queue TTL is 5 minutes.
3. Retry interval is 10 seconds.
4. Retry max attempts is 3 per batch.
5. Batch size is 1 face per request.

## Reliability Rules
1. Drop oldest payload when queue is full.
2. Log queue depth, drops, and send failures.
3. Service restart should restore runtime cleanly.

## Security Rules
1. Use secure transport in production environments.
2. Do not log raw image payload contents.
3. Apply auth header when endpoint is protected.
