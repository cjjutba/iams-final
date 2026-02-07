# Environment Config

## Backend Variables (Recommended)
| Variable | Description | Default |
|---|---|---|
| `API_BASE_URL` | HTTP API base URL | `http://localhost:8000/api/v1` |
| `WS_HEARTBEAT_INTERVAL` | Heartbeat interval seconds | `30` |
| `WS_STALE_TIMEOUT` | Time to mark connection stale (seconds) | `60` |
| `WS_MAX_CONNECTIONS_PER_USER` | Safety cap per user | `3` |
| `WS_ENABLE_DELIVERY_LOGS` | Enable optional delivery logging | `false` |

## Mobile Variables (Recommended)
| Variable | Description | Default |
|---|---|---|
| `WS_BASE_URL` | WebSocket base URL | `ws://localhost:8000/api/v1` |
| `WS_RECONNECT_BASE_DELAY_MS` | Initial reconnect delay | `1000` |
| `WS_RECONNECT_MAX_DELAY_MS` | Max reconnect delay | `10000` |
| `WS_RECONNECT_MAX_ATTEMPTS` | Retry cap for reconnect loop | `0` (infinite) |

## Notes
- Keep mobile and backend URL/protocol aligned by environment.
- Use `wss://` in production over HTTPS.
