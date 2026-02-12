# Demo Checklist (MOD-04)

- [ ] Edge runtime starts and captures frames (640x480, 15 FPS).
- [ ] Face crops are produced from detected faces (~112x112 via MediaPipe).
- [ ] Crops are NOT resized to 160x160 on edge (backend responsibility).
- [ ] `X-API-Key` header is present on every `POST /face/process` request.
- [ ] Valid payload with valid API key reaches `/face/process` successfully.
- [ ] Missing API key returns 401 from backend.
- [ ] Invalid API key returns 401 from backend.
- [ ] Server-down condition queues payloads (not auth failures).
- [ ] Queue does not exceed max size (500 items).
- [ ] Expired queue entries (>5 min) are discarded before retry.
- [ ] Retry resumes after backend is restored (with `X-API-Key` header).
- [ ] Queue depth and drop logs are visible.
- [ ] Auth failure (401) is logged and NOT queued for retry.
- [ ] Runtime remains stable during intermittent failures.
- [ ] `EDGE_API_KEY` is not logged in startup output.
