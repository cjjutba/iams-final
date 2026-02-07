# Demo Checklist

## Pre-Demo Setup
- [ ] Backend running with websocket endpoint enabled.
- [ ] Mobile app connected to correct WS base URL.
- [ ] At least one faculty client and one student client ready.

## Live Demo Steps
- [ ] Open faculty live attendance screen (`SCR-021`).
- [ ] Trigger attendance update and verify realtime roster update.
- [ ] Trigger early-leave event and verify alert appears.
- [ ] End session and verify session-end summary event is shown.
- [ ] Disable network briefly and verify reconnect behavior after restore.

## Pass Criteria
- [ ] All three event types observed with valid payload fields.
- [ ] No app restart needed to resume updates after reconnect.
- [ ] No duplicate spam events caused by reconnect.
