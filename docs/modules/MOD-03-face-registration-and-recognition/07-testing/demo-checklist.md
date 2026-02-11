# Demo Checklist (MOD-03)

- [ ] Student can capture and submit 3-5 face images.
- [ ] Invalid image inputs are rejected with clear reason.
- [ ] Registration success returns embedding metadata.
- [ ] Registration status endpoint reports correct state.
- [ ] Recognition returns matched result for known face.
- [ ] Recognition returns unmatched result for unknown face.
- [ ] Re-registration updates active mapping correctly.
- [ ] FAISS and DB mapping consistency is verified.
- [ ] Registration endpoint requires valid Supabase JWT (no JWT = 401).
- [ ] Status endpoint requires valid Supabase JWT (no JWT = 401).
- [ ] Recognize endpoint requires valid API key (no key = 401).
- [ ] Inactive or unconfirmed user cannot register face (403).
- [ ] Backend resizes face crops to 160x160 before inference.
- [ ] User deletion (MOD-02) cleans up face_registrations and FAISS entry.
- [ ] Threshold is configurable via RECOGNITION_THRESHOLD env var.
