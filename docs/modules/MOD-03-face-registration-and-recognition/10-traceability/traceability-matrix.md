# Traceability Matrix (MOD-03)

| Function ID | API | Data | Screens | Tests | Implementation Targets |
|---|---|---|---|---|---|
| FUN-03-01 | POST /face/register | face_registrations | SCR-009, SCR-017 | T03-U1, T03-U2, T03-I1, T03-I2, T03-I7, T03-I8, T03-I12, T03-E1, T03-E6 | backend face router/service (Supabase JWT auth) |
| FUN-03-02 | POST /face/register | FAISS model pipeline | SCR-009, SCR-017 | T03-U3, T03-U7, T03-I1 | backend face ML service (resize to 160x160 + FaceNet) |
| FUN-03-03 | POST /face/register | face_registrations, FAISS index | SCR-009, SCR-017 | T03-U6, T03-U9, T03-I1, T03-E2, T03-E5 | backend face service + repository + MOD-02 deletion cleanup |
| FUN-03-04 | POST /face/recognize | FAISS index, users | edge context | T03-U4, T03-U5, T03-U8, T03-I3, T03-I4, T03-I10, T03-I11, T03-E3, T03-E4 | backend face recognition service (API key auth) |
| FUN-03-05 | GET /face/status | face_registrations | SCR-009, SCR-017 | T03-I5, T03-I6, T03-I9 | backend face status endpoint (Supabase JWT auth) |

## Traceability Rule
Every commit touching MOD-03 should map to at least one matrix row.
