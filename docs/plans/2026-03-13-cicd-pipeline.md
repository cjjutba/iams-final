# CI/CD Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add component-based GitHub Actions CI/CD with path-filtered workflows — lint/test on PRs, auto-deploy backend on merge to main.

**Architecture:** Four separate workflow files triggered by path filters (`backend/**`, `mobile/**`, `edge/**`). A deploy workflow fires on push to `main` for backend/deploy changes. New linting configs (ruff, eslint) are added per component.

**Tech Stack:** GitHub Actions, Ruff (Python linting), mypy (type checking), pytest, ESLint + TypeScript, Expo CLI, Docker, SSH/rsync

**Design Doc:** `docs/plans/2026-03-13-cicd-pipeline-design.md`

---

### Task 1: Add Ruff config for backend

**Files:**
- Create: `backend/ruff.toml`
- Modify: `backend/requirements.txt` (add ruff + mypy dev deps)

**Step 1: Create `backend/ruff.toml`**

```toml
# Ruff linting configuration for IAMS backend
target-version = "py311"
line-length = 120
src = ["app"]

[lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking
]
ignore = [
    "E501",   # line too long (handled by formatter)
    "B008",   # do not perform function calls in argument defaults (FastAPI Depends pattern)
    "B905",   # zip without strict= (Python 3.10+)
    "SIM108", # use ternary operator (readability preference)
]

[lint.isort]
known-first-party = ["app"]

[format]
quote-style = "double"
indent-style = "space"
```

**Step 2: Add ruff and mypy to `backend/requirements.txt`**

Append to the `# ===== Testing =====` section:

```
ruff>=0.8.0
mypy>=1.13.0
```

**Step 3: Run ruff to verify config works**

Run: `cd backend && pip install ruff mypy && ruff check app/ --statistics`
Expected: Output showing any existing violations (informational — we'll fix or suppress later)

**Step 4: Commit**

```bash
git add backend/ruff.toml backend/requirements.txt
git commit -m "chore: add ruff and mypy config for backend CI"
```

---

### Task 2: Add Ruff config for edge

**Files:**
- Create: `edge/ruff.toml`

**Step 1: Create `edge/ruff.toml`**

```toml
# Ruff linting configuration for IAMS edge device
target-version = "py311"
line-length = 120

[lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
]
ignore = [
    "E501",   # line too long (handled by formatter)
]

[format]
quote-style = "double"
indent-style = "space"
```

**Step 2: Run ruff to verify**

Run: `cd edge && ruff check . --statistics`
Expected: Output showing any existing violations

**Step 3: Commit**

```bash
git add edge/ruff.toml
git commit -m "chore: add ruff config for edge CI"
```

---

### Task 3: Add ESLint config for mobile

**Files:**
- Create: `mobile/.eslintrc.js`
- Create: `mobile/.eslintignore`
- Modify: `mobile/package.json` (add eslint devDependencies and script)

**Step 1: Install ESLint packages**

Run: `cd mobile && pnpm add -D eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin eslint-plugin-react eslint-plugin-react-hooks`

**Step 2: Create `mobile/.eslintrc.js`**

```js
module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: "module",
    ecmaFeatures: { jsx: true },
  },
  plugins: ["@typescript-eslint", "react", "react-hooks"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended",
  ],
  settings: {
    react: { version: "detect" },
  },
  env: {
    es2022: true,
    node: true,
  },
  rules: {
    "react/react-in-jsx-scope": "off",        // Not needed with React 19
    "react/prop-types": "off",                 // Using TypeScript
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    "@typescript-eslint/no-explicit-any": "warn",
    "@typescript-eslint/no-require-imports": "off", // Expo uses require()
  },
};
```

**Step 3: Create `mobile/.eslintignore`**

```
node_modules/
.expo/
dist/
android/
ios/
babel.config.js
metro.config.js
```

**Step 4: Add lint script to `mobile/package.json`**

Add to `"scripts"`:
```json
"lint": "eslint . --ext .ts,.tsx",
"typecheck": "tsc --noEmit"
```

**Step 5: Run ESLint to verify**

Run: `cd mobile && pnpm lint -- --max-warnings=999`
Expected: Output showing any existing warnings (informational)

**Step 6: Commit**

```bash
git add mobile/.eslintrc.js mobile/.eslintignore mobile/package.json mobile/pnpm-lock.yaml
git commit -m "chore: add ESLint config for mobile CI"
```

---

### Task 4: Create Backend CI workflow

**Files:**
- Create: `.github/workflows/backend-ci.yml`

**Step 1: Create the workflow file**

```yaml
name: Backend CI

on:
  pull_request:
    branches: [main]
    paths:
      - "backend/**"
      - ".github/workflows/backend-ci.yml"

jobs:
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
          cache-dependency-path: backend/requirements.txt

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Ruff lint
        run: ruff check app/

      - name: Ruff format check
        run: ruff format --check app/

      - name: Mypy type check
        run: mypy app/ --ignore-missing-imports --no-error-summary || true

  test:
    name: Test
    needs: lint
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    env:
      DATABASE_URL: "sqlite:///./test.db"
      JWT_SECRET_KEY: "ci-test-secret-key-not-for-production"
      SUPABASE_URL: "https://placeholder.supabase.co"
      SUPABASE_ANON_KEY: "placeholder-key"
      SUPABASE_SERVICE_KEY: "placeholder-service-key"
      DEBUG: "true"
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
          cache-dependency-path: backend/requirements.txt

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tests with coverage
        run: pytest --cov=app --cov-report=xml --cov-report=term -v

      - name: Upload coverage artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: backend/coverage.xml

  docker-build:
    name: Docker Build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build --target runtime -t iams-backend:ci-test ./backend
```

**Step 2: Verify YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/backend-ci.yml'))"`
Expected: No errors

**Step 3: Commit**

```bash
git add .github/workflows/backend-ci.yml
git commit -m "ci: add backend CI workflow (lint, test, docker build)"
```

---

### Task 5: Create Mobile CI workflow

**Files:**
- Create: `.github/workflows/mobile-ci.yml`

**Step 1: Create the workflow file**

```yaml
name: Mobile CI

on:
  pull_request:
    branches: [main]
    paths:
      - "mobile/**"
      - ".github/workflows/mobile-ci.yml"

jobs:
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: mobile
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "pnpm"
          cache-dependency-path: mobile/pnpm-lock.yaml

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: TypeScript check
        run: npx tsc --noEmit

      - name: ESLint check
        run: pnpm lint

  build:
    name: Build Validation
    needs: lint
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: mobile
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "pnpm"
          cache-dependency-path: mobile/pnpm-lock.yaml

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Export web build (validates bundling)
        run: npx expo export --platform web
```

**Step 2: Verify YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/mobile-ci.yml'))"`
Expected: No errors

**Step 3: Commit**

```bash
git add .github/workflows/mobile-ci.yml
git commit -m "ci: add mobile CI workflow (lint, typecheck, build)"
```

---

### Task 6: Create Edge CI workflow

**Files:**
- Create: `.github/workflows/edge-ci.yml`

**Step 1: Create the workflow file**

```yaml
name: Edge CI

on:
  pull_request:
    branches: [main]
    paths:
      - "edge/**"
      - ".github/workflows/edge-ci.yml"

jobs:
  lint:
    name: Lint & Validate
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: edge
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
          cache-dependency-path: edge/requirements.txt

      - name: Install dependencies
        run: |
          pip install ruff
          pip install -r requirements.txt

      - name: Ruff lint
        run: ruff check .

      - name: Python syntax validation
        run: python -m py_compile run.py && python -c "
          import glob, py_compile, sys
          errors = []
          for f in glob.glob('**/*.py', recursive=True):
              try:
                  py_compile.compile(f, doraise=True)
              except py_compile.PyCompileError as e:
                  errors.append(str(e))
          if errors:
              print('\n'.join(errors))
              sys.exit(1)
          print('All Python files compile successfully')
          "
```

**Step 2: Verify YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/edge-ci.yml'))"`
Expected: No errors

**Step 3: Commit**

```bash
git add .github/workflows/edge-ci.yml
git commit -m "ci: add edge CI workflow (lint, syntax check)"
```

---

### Task 7: Create Deploy workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

**Step 1: Create the workflow file**

```yaml
name: Deploy to VPS

on:
  push:
    branches: [main]
    paths:
      - "backend/**"
      - "deploy/**"
      - ".github/workflows/deploy.yml"

jobs:
  deploy:
    name: Deploy Backend
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup SSH key
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.VPS_SSH_KEY }}" > ~/.ssh/id_rsa
          chmod 600 ~/.ssh/id_rsa
          ssh-keyscan -H ${{ secrets.VPS_HOST }} >> ~/.ssh/known_hosts

      - name: Sync backend code
        run: |
          rsync -avz --delete \
            --exclude 'venv/' \
            --exclude '__pycache__/' \
            --exclude '*.pyc' \
            --exclude '.pytest_cache/' \
            --exclude 'data/faiss/' \
            --exclude 'data/uploads/' \
            --exclude 'data/hls/' \
            --exclude 'data/.models/' \
            --exclude 'logs/' \
            --exclude 'test.db' \
            --exclude '.env' \
            backend/ ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }}:/opt/iams/backend/

      - name: Sync deploy configs
        run: |
          rsync -avz \
            deploy/docker-compose.prod.yml \
            deploy/nginx.conf \
            deploy/mediamtx.yml \
            ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }}:/opt/iams/deploy/

      - name: Build and restart containers
        run: |
          ssh ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }} << 'EOF'
            cd /opt/iams/deploy
            echo "Building Docker image..."
            docker compose -f docker-compose.prod.yml build --no-cache
            echo "Restarting containers..."
            docker compose -f docker-compose.prod.yml down || true
            docker compose -f docker-compose.prod.yml up -d
          EOF

      - name: Wait for health check
        run: |
          echo "Waiting for backend to be healthy..."
          for i in $(seq 1 30); do
            STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://${{ secrets.VPS_HOST }}/api/v1/health" || echo "000")
            if [ "$STATUS" = "200" ]; then
              echo "Backend is healthy! (attempt $i)"
              exit 0
            fi
            echo "  Waiting... ($i/30) - status: $STATUS"
            sleep 5
          done
          echo "ERROR: Health check failed after 150s"
          exit 1
```

**Step 2: Verify YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))"`
Expected: No errors

**Step 3: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: add auto-deploy workflow on merge to main"
```

---

### Task 8: Fix existing lint violations (backend)

This task ensures backend CI will pass on the first real PR.

**Step 1: Run ruff and auto-fix what's safe**

Run: `cd backend && ruff check app/ --fix`
Expected: Some violations auto-fixed (unused imports, isort, etc.)

**Step 2: Run ruff format**

Run: `cd backend && ruff format app/`
Expected: Files reformatted

**Step 3: Run tests to verify nothing broke**

Run: `cd backend && pytest -x -q`
Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/app/
git commit -m "style: auto-fix ruff lint violations in backend"
```

---

### Task 9: Fix existing lint violations (edge)

**Step 1: Run ruff and auto-fix**

Run: `cd edge && ruff check . --fix`

**Step 2: Run ruff format**

Run: `cd edge && ruff format .`

**Step 3: Commit**

```bash
git add edge/
git commit -m "style: auto-fix ruff lint violations in edge"
```

---

### Task 10: Fix existing ESLint violations (mobile)

**Step 1: Run ESLint and auto-fix**

Run: `cd mobile && pnpm lint -- --fix`

**Step 2: Run typecheck**

Run: `cd mobile && npx tsc --noEmit`
Expected: Check for any type errors. If there are errors, note them but do NOT fix them in this task — suppress with `// @ts-expect-error` comments only if they block CI. Existing type errors are a separate concern.

**Step 3: Commit**

```bash
git add mobile/
git commit -m "style: auto-fix ESLint violations in mobile"
```

---

### Task 11: Test full pipeline locally

**Step 1: Simulate backend CI locally**

Run in sequence:
```bash
cd backend
ruff check app/
ruff format --check app/
pytest --cov=app -v -x
docker build --target runtime -t iams-backend:ci-test .
```
Expected: All pass

**Step 2: Simulate mobile CI locally**

```bash
cd mobile
npx tsc --noEmit
pnpm lint
npx expo export --platform web
```
Expected: All pass (or known suppressions in place)

**Step 3: Simulate edge CI locally**

```bash
cd edge
ruff check .
python -m py_compile run.py
```
Expected: All pass

**Step 4: Final commit — all lint configs and workflows**

```bash
git add -A
git commit -m "ci: complete CI/CD pipeline setup with lint fixes"
```

---

### Task 12: Document GitHub Secrets setup

**Files:**
- Modify: `docs/plans/2026-03-13-cicd-pipeline-design.md` (add setup instructions)

**Step 1: Add setup instructions to design doc**

Append a section:

```markdown
## GitHub Secrets Setup

Go to GitHub repo → Settings → Secrets and variables → Actions → New repository secret:

1. **`VPS_SSH_KEY`**: Paste the private SSH key for root@167.71.217.44
   - Generate if needed: `ssh-keygen -t ed25519 -C "github-actions-deploy"`
   - Add public key to VPS: `ssh-copy-id -i ~/.ssh/id_ed25519.pub root@167.71.217.44`
2. **`VPS_HOST`**: `167.71.217.44`
3. **`VPS_USER`**: `root`
```

**Step 2: Commit**

```bash
git add docs/plans/2026-03-13-cicd-pipeline-design.md
git commit -m "docs: add GitHub Secrets setup instructions for CI/CD"
```
