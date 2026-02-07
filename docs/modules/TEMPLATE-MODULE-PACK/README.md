# TEMPLATE-MODULE-PACK

## Purpose
Use this folder as the starter template for new module documentation packs.

## How to Use
1. Copy this folder.
2. Rename to `MOD-XX-<module-name>`.
3. Replace all placeholders:
- `<MOD-ID>`
- `<MODULE-NAME>`
- `<FUN-ID>`
- `<SCR-ID>`
- `<ENDPOINT>`
4. Fill all sections before implementation starts.

Or generate automatically:
```powershell
powershell -ExecutionPolicy Bypass -File docs/modules/TEMPLATE-MODULE-PACK/create-module.ps1 -ModuleId MOD-03 -ModuleName "Face Registration and Recognition"
```

## Required Sections
- Governance
- Catalog
- Specification
- API
- Data
- Screens
- Dependencies
- Testing
- Implementation
- AI Execution
- Traceability

## Rule
Do not skip folders. Keep structure consistent across all modules.
