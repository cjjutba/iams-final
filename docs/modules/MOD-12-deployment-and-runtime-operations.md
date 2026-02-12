# MOD-12: Deployment and Runtime Operations

This file is a module-level source of truth derived from `docs/main/master-blueprint.md` section 6.
Update both files together when module scope changes.

## Specification

Purpose:
- Deploy backend, edge, and mobile with stable environment configs.

Functions:
- `FUN-12-01`: Configure environment files per runtime.
- `FUN-12-02`: Start backend, edge, and mobile services.
- `FUN-12-03`: Health checks and monitoring basics.
- `FUN-12-04`: Backup FAISS and database data.
- `FUN-12-05`: Rollback procedure for failed deployments.

Docs:
- `docs/main/deployment.md`
- `docs/main/architecture.md`

Done Criteria:
- Local pilot deployment works on same network.
- Cloud deployment path documented for future.
- Backup and rollback steps are tested.


## Implementation Rule
- Implement only the listed `FUN-*` items for this module when this doc is referenced.
- If scope/API/data/screen changes are needed, update docs first before code.
