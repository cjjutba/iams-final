# Logging and Observability

## Required Log Events
- camera init/reconnect attempts
- send success/failure
- queue enqueue/dequeue
- queue drop due to overflow/TTL
- retry cycle summary

## Minimum Metrics
- current queue depth
- dropped payload count
- send success rate
- retry attempts per minute

## Logging Rules
- avoid logging raw image content
- include correlation/timestamp fields for diagnostics
- keep logs rotation-friendly on constrained storage
