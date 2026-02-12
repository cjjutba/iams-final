# Data Model Inventory

## Primary Data Stores Used by MOD-04
1. In-memory bounded queue for unsent payloads (`collections.deque(maxlen=500)`)
2. Runtime logs (optional local file/log sink)
3. Outbound payload model to backend API

## Entities
- Frame metadata (timestamp, resolution)
- Face crop payload objects (base64 JPEG ~112x112, bbox)
- Queue entries with enqueue timestamp and retry metadata

## Ownership
- Queue and payload model: edge runtime service
- Backend persistence: not owned by MOD-04

## Cross-Module Data Flow
- Edge sends face crops to backend `POST /face/process` (with `X-API-Key` header).
- Backend resizes crops to 160x160 and runs recognition (MOD-03).
- Recognition results flow to attendance (MOD-06) and presence (MOD-07).
- MOD-04 does not persist data to any database — all data is transient (in-memory queue, outbound HTTP).

## MOD-02 User Deletion Impact
When a user is deleted (MOD-02), MOD-03 removes their face registration. If edge has queued payloads containing that user's face, backend returns "unmatched" for that face on next send. No edge-side data cleanup is needed since edge does not store user identity information.
