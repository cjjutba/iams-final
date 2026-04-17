# mediamtx WebRTC Setup Design

**Goal:** Get the existing WebRTC streaming path fully operational by running mediamtx as a FastAPI-managed subprocess, replacing HLS as the primary streaming mode with sub-500ms latency.

**Architecture:** FastAPI's lifespan handler starts mediamtx (a single binary) before serving requests. The mobile app already has a complete WebRTC implementation (`useWebRTC.ts`) and falls back to HLS automatically when mediamtx is unavailable — no changes needed on the mobile side.

**Tech Stack:** mediamtx v1.x (RTSP→WebRTC bridge), macOS arm64 binary, WHEP protocol, `react-native-webrtc` (already installed).

---

## Architecture

```
python run.py
└── FastAPI lifespan startup
    ├── mediamtx_service.start()   ← NEW
    ├── recognition_service.start() (existing)
    └── serve requests

Mobile WebRTC flow (already implemented):
  useWebRTC → POST /api/v1/webrtc/{id}/offer
            → FastAPI webrtc.py router
            → webrtc_service.forward_whep_offer()
            → mediamtx :8889/WHEP
            ← SDP answer
  Mobile ←←←← UDP RTP (~200ms) ←←← mediamtx ←←← RTSP camera

WebSocket stream router (existing):
  mediamtx healthy? → send mode=webrtc
  mediamtx down?    → send mode=hls  (existing fallback, unchanged)
```

## New Files

| File | Purpose |
|------|---------|
| `backend/bin/mediamtx` | macOS arm64 binary (gitignored, downloaded by script) |
| `backend/mediamtx.yml` | Static mediamtx config (API, WebRTC, log level) |
| `backend/scripts/download_mediamtx.sh` | One-time setup script to download correct binary |
| `backend/app/services/mediamtx_service.py` | Subprocess lifecycle manager |
| `backend/tests/unit/test_mediamtx_service.py` | Unit tests with mocked Popen + HTTP |

## Modified Files

| File | Change |
|------|--------|
| `backend/app/config.py` | Add `MEDIAMTX_BIN_PATH`, `MEDIAMTX_CONFIG_PATH` |
| `backend/main.py` | Add mediamtx start/stop to lifespan |
| `backend/.gitignore` | Ignore `bin/mediamtx` binary |

## Component Design

### `mediamtx.yml`

```yaml
logLevel: warn       # suppress routine logs from FastAPI terminal
api: yes
apiAddress: :9997    # FastAPI creates paths here (webrtc_service.ensure_path)
rtsp: yes
rtspAddress: :8554   # mediamtx pulls camera RTSP on demand
webrtc: yes
webrtcAddress: :8889 # WHEP endpoint (proxied by FastAPI webrtc router)
paths: {}            # empty — paths added dynamically via REST API
```

### `mediamtx_service.py`

```python
class MediamtxService:
    _process: Optional[subprocess.Popen] = None

    def start(self) -> bool:
        # 1. Resolve absolute paths for bin and config
        # 2. Check binary exists — log clear error if not ("run download_mediamtx.sh")
        # 3. subprocess.Popen([bin_path, config_path], stdout=DEVNULL, stderr=DEVNULL)
        # 4. Poll GET /v3/config (max 5s, 0.25s interval) until mediamtx is ready
        # 5. Return True on success, False on failure (FastAPI still starts)

    def stop(self) -> None:
        # SIGTERM → wait 5s → SIGKILL if still alive

    def is_healthy(self) -> bool:
        # process.poll() is None
```

### `main.py` lifespan

```python
@asynccontextmanager
async def lifespan(app):
    mediamtx_service.start()       # ← NEW (failure = warning, not crash)
    recognition_service.start()
    yield
    recognition_service.stop()
    await mediamtx_service.stop()  # ← NEW
```

### `download_mediamtx.sh`

Fetches latest mediamtx release for `darwin_arm64` from GitHub API, extracts the binary to `backend/bin/mediamtx`, and sets execute permission.

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Binary missing | Log "run scripts/download_mediamtx.sh", skip start; system uses HLS |
| mediamtx won't start | Log error, `start()` returns False; FastAPI still serves; HLS fallback active |
| Port 9997/8889 in use | mediamtx exits immediately; same fallback path |
| mediamtx crashes at runtime | Existing WebSocket router fallback sends `mode=hls` to mobile |

## Testing

Unit tests in `test_mediamtx_service.py`:
- `test_start_launches_process` — Popen called with correct args
- `test_start_returns_false_when_binary_missing` — FileNotFoundError handled
- `test_start_returns_false_when_api_does_not_come_up` — timeout path
- `test_stop_terminates_process` — SIGTERM sent, process waited
- `test_is_healthy_returns_false_when_not_started` — None process case
