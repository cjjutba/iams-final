# Business Rules

## Auth Rules
1. Edge device must include `X-API-Key` header on every `POST /face/process` request.
2. API key is read from `EDGE_API_KEY` environment variable.
3. Edge does NOT use Supabase JWT (JWT is for student/faculty-facing endpoints only).
4. Backend returns 401 on missing or invalid API key.

## Pipeline Rules
1. Capture → detect → crop → compress → send must run in ordered pipeline.
2. Send operation failure must not crash runtime.
3. Queue fallback is mandatory on backend unavailability.

## Queue Rules
1. Max queue size is 500 items (`collections.deque(maxlen=500)`).
2. Queue TTL is 5 minutes.
3. Retry interval is 10 seconds.
4. Retry max attempts is 3 per batch.
5. Batch size is 1 face per request.

## Capture Rules
1. Frame resolution: 640x480.
2. Frame rate: 15 FPS.
3. Face crop size: ~112x112 (detection output; backend handles resize to 160x160).
4. JPEG compression: 70% quality.

## Reliability Rules
1. Drop oldest payload when queue is full.
2. Log queue depth, drops, and send failures.
3. Service restart should restore runtime cleanly.

## Security Rules
1. Use HTTPS in production environments.
2. Do not log raw image payload contents.
3. Include `X-API-Key` header on all requests to `/face/process`.
4. Never commit `EDGE_API_KEY` to source control.
