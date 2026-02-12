# Glossary

- **Embedding:** Numeric vector representation of a face image (512 dimensions from FaceNet).
- **FAISS:** Vector similarity index for nearest-neighbor search (`IndexFlatIP`).
- **Cosine Similarity:** Distance metric used for face matching.
- **Match Threshold:** Minimum confidence/similarity to accept identity match (default 0.6, configurable).
- **Re-registration:** Process of replacing old face embedding with a new one.
- **Active Face Registration:** Current valid face mapping for a user (one per user).
- **Supabase JWT:** JSON Web Token issued by Supabase Auth, verified by backend middleware on student-facing endpoints (register, status). Established in MOD-01.
- **API Key (Edge Auth):** Shared secret sent via `X-API-Key` header by edge devices (RPi) to authenticate recognition requests. Validated against `EDGE_API_KEY` env variable.
- **FaceNet:** Face recognition model (InceptionResnetV1) producing 512-d embeddings from 160x160 RGB input.
- **Model Input Resize:** Backend responsibility to resize incoming face crops (e.g., 112x112 from edge) to model-required 160x160 before inference.
