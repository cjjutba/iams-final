# Capabilities Matrix

| Actor | Capability | Function ID(s) | Notes |
|---|---|---|---|
| Student | Register face images | FUN-03-01, FUN-03-02, FUN-03-03 | 3-5 images required |
| Student | Check face registration status | FUN-03-05 | used by app status checks |
| Edge caller | Send crop for recognition | FUN-03-04 | typically from edge/processing flow |
| Backend | Keep DB and FAISS synchronized | FUN-03-03 | lifecycle consistency critical |
| Mobile app | Trigger re-registration flow | FUN-03-01..FUN-03-03 | via face capture screens |
