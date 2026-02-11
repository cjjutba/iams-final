# Capabilities Matrix

| Actor | Capability | Function ID(s) | Notes |
|---|---|---|---|
| Student | Register face images | FUN-03-01, FUN-03-02, FUN-03-03 | 3-5 images required; Supabase JWT auth |
| Student | Check face registration status | FUN-03-05 | Supabase JWT auth; used by app status checks |
| Edge caller (RPi) | Send crop for recognition | FUN-03-04 | API key auth (`X-API-Key`); backend resizes to 160x160 |
| Backend | Keep DB and FAISS synchronized | FUN-03-03 | lifecycle consistency critical |
| Backend | Clean up face data on user deletion | FUN-03-03 | triggered by MOD-02 delete; remove face_registrations + FAISS entry |
| Mobile app | Trigger re-registration flow | FUN-03-01..FUN-03-03 | via face capture screens; Supabase JWT auth |
