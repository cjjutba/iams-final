# Traceability Matrix (MOD-04)

| Function ID | API | Data | Runtime Interface | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-04-01 | n/a | frame stream | camera runtime | T04-U1, T04-S3 | edge camera module |
| FUN-04-02 | n/a | face crops + bbox | detector/cropper | T04-U2 | edge detector/processor |
| FUN-04-03 | POST /face/process | outbound payload | sender | T04-U3, T04-I1, T04-I2 | edge sender module |
| FUN-04-04 | POST /face/process fallback | bounded queue | queue manager | T04-U4, T04-U5, T04-I3, T04-S1 | edge queue manager |
| FUN-04-05 | POST /face/process retry | retry metadata | retry worker | T04-U6, T04-I4, T04-S2 | edge retry loop |

## Traceability Rule
Every commit touching MOD-04 should map to at least one matrix row.
