# Capabilities Matrix

| Actor | Capability | Function ID(s) | Notes |
|---|---|---|---|
| Edge runtime | capture frames | FUN-04-01 | configured FPS/resolution |
| Edge runtime | detect/crop faces | FUN-04-02 | MediaPipe + OpenCV pipeline |
| Edge runtime | send payloads | FUN-04-03 | one face per request by policy |
| Edge runtime | queue failed sends | FUN-04-04 | bounded queue with TTL |
| Edge runtime | retry and recover delivery | FUN-04-05 | non-blocking retry behavior |
| Operations | monitor queue depth and failures | FUN-04-04, FUN-04-05 | logs/metrics required |
