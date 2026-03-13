# CI/CD Pipeline Design — Component-Based (Approach B)

**Date:** 2026-03-13
**Status:** Approved
**Trigger:** PR to `main` branch

## Overview

Component-based GitHub Actions CI/CD with path-filtered workflows. Only runs checks for components that changed. Auto-deploys backend to VPS on merge to `main`.

## Architecture

```
.github/workflows/
├── backend-ci.yml      # backend/** changes
├── mobile-ci.yml       # mobile/** changes
├── edge-ci.yml         # edge/** changes
└── deploy.yml          # merge to main (backend/deploy changes)
```

## Workflow 1: Backend CI (`backend-ci.yml`)

**Trigger:** PR to `main` touching `backend/**`

### Job 1: Lint & Type Check
- Runner: `ubuntu-latest`
- Python 3.11
- `pip install -r requirements.txt`
- `ruff check backend/app/` — linting
- `ruff format --check backend/app/` — formatting
- `mypy backend/app/ --ignore-missing-imports` — type checking

### Job 2: Test (depends on lint)
- Runner: `ubuntu-latest`
- Python 3.11
- `pytest --cov=app --cov-report=xml -v`
- Uses SQLite in-memory (existing conftest.py supports this)
- Upload coverage as artifact

### Job 3: Docker Build Validation (parallel with test)
- `docker build --target runtime -t iams-backend:test .`
- Validates multi-stage Dockerfile compiles
- Does NOT push image

## Workflow 2: Mobile CI (`mobile-ci.yml`)

**Trigger:** PR to `main` touching `mobile/**`

### Job 1: Lint & Type Check
- Runner: `ubuntu-latest`
- Node 20 + pnpm
- `pnpm install`
- `npx tsc --noEmit` — TypeScript validation
- `npx eslint .` — ESLint check

### Job 2: Build Validation (depends on lint)
- `npx expo export --platform web`
- Validates app bundles without errors
- No native builds on PRs (too expensive)

## Workflow 3: Edge CI (`edge-ci.yml`)

**Trigger:** PR to `main` touching `edge/**`

### Job 1: Lint & Validate
- Runner: `ubuntu-latest`
- Python 3.11
- `pip install -r requirements.txt`
- `ruff check edge/` — linting
- `python -m py_compile` on all `.py` files

## Workflow 4: Deploy (`deploy.yml`)

**Trigger:** Push to `main` when `backend/**` or `deploy/**` changed

### Job 1: Deploy to VPS
- SSH into `167.71.217.44` via stored key
- Steps mirror `deploy/deploy.sh`:
  1. rsync backend + deploy configs
  2. `docker compose build --no-cache`
  3. `docker compose down && docker compose up -d`
  4. Poll `/api/v1/health` (max 150s, 5s intervals)
- On health check failure: workflow fails, sends notification

## New Config Files

| File | Purpose |
|------|---------|
| `backend/ruff.toml` | Ruff linting rules (line-length, isort, etc.) |
| `edge/ruff.toml` | Ruff linting rules for edge device code |
| `mobile/.eslintrc.js` | ESLint for React Native + Expo + TypeScript |

## GitHub Secrets Required

| Secret | Purpose |
|--------|---------|
| `VPS_SSH_KEY` | Private SSH key for root@167.71.217.44 |
| `VPS_HOST` | `167.71.217.44` |
| `VPS_USER` | `root` |

## Dependencies

- **ruff** — added to backend & edge requirements.txt (dev dependency)
- **mypy** — added to backend requirements.txt (dev dependency)
- **eslint** + plugins — added to mobile devDependencies

## Pipeline Flow

```
PR opened/updated to main
    ├── backend/** → Lint (ruff+mypy) → Test (pytest+coverage) + Docker Build
    ├── mobile/** → Lint (tsc+eslint) → Build Validation (expo export)
    └── edge/**   → Lint (ruff) + Syntax Check

All checks pass → PR mergeable

PR merged to main
    └── backend/** or deploy/** → SSH → rsync → docker build → deploy → health check
```

## Design Decisions

1. **Path filters over matrix** — avoids wasting CI minutes on unchanged components
2. **No staging environment** — single VPS, thesis project scope
3. **No native mobile builds on PR** — EAS builds are slow/expensive; web export catches most issues
4. **SQLite for CI tests** — existing conftest.py already supports this, no need for CI Postgres service
5. **Ruff over flake8/pylint** — single fast tool for linting + formatting
6. **Health check as deploy gate** — reuses existing `/api/v1/health` endpoint

## GitHub Secrets Setup

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

1. **`VPS_SSH_KEY`** — Paste the **private** SSH key for root@167.71.217.44
   - Generate if needed: `ssh-keygen -t ed25519 -C "github-actions-deploy"`
   - Add public key to VPS: `ssh-copy-id -i ~/.ssh/id_ed25519.pub root@167.71.217.44`
   - Copy private key: `cat ~/.ssh/id_ed25519` and paste into the secret
2. **`VPS_HOST`** — `167.71.217.44`
3. **`VPS_USER`** — `root`

### Verifying Secrets Work

After adding secrets, push any change to `backend/` on a PR to `main`. The Backend CI workflow will run. The Deploy workflow only triggers on merge to `main`.
