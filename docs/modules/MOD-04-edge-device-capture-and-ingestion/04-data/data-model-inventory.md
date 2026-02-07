# Data Model Inventory

## Primary Data Stores Used by MOD-04
1. In-memory bounded queue for unsent payloads
2. Runtime logs (optional local file/log sink)
3. Outbound payload model to backend API

## Entities
- Frame metadata
- Face crop payload objects
- Queue entries with enqueue timestamp and retry metadata

## Ownership
- Queue and payload model: edge runtime service
- Backend persistence: not owned by MOD-04
