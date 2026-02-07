# Glossary

- WebSocket: Bidirectional persistent protocol between client and server.
- Connection map: In-memory registry of active sockets by user.
- Fanout: Sending one logical event to one or more connected recipients.
- Stale connection: Socket entry that is no longer valid but still tracked.
- Heartbeat: Ping/pong exchange used to detect dead connections.
- Reconnect: Client-initiated new socket after disconnect.
- Event envelope: Standard top-level JSON shape with `type` and `data`.
- Session end: End-of-class summary event emitted after class closes.
