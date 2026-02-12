# Traceability Matrix (MOD-04)

| Function ID | API | Data | Runtime Interface | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-04-01 | n/a | frame stream (640x480) | camera runtime (picamera2/OpenCV) | T04-U1, T04-S3 | edge camera module |
| FUN-04-02 | n/a | face crops (~112x112) + bbox | MediaPipe detector/cropper | T04-U2, T04-U8 | edge detector/processor |
| FUN-04-03 | POST /face/process | outbound payload + `X-API-Key` | sender | T04-U3, T04-U7, T04-I1, T04-I2, T04-I5, T04-I6, T04-I7 | edge sender module (API key auth) |
| FUN-04-04 | POST /face/process fallback | bounded queue (500 max, 5-min TTL) | queue manager | T04-U4, T04-U5, T04-I3, T04-S1, T04-S4 | edge queue manager |
| FUN-04-05 | POST /face/process retry | retry metadata (10s, 3 attempts) | retry worker | T04-U6, T04-I4, T04-S2 | edge retry loop (with `X-API-Key`) |

## Traceability Rule
Every commit touching MOD-04 should map to at least one matrix row.
