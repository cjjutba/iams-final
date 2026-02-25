# Step 4: Set Up the Backend Server

The backend is a Python FastAPI application that handles authentication, face recognition, attendance tracking, and the API.

---

## Step 4.1: Navigate to the backend folder

```bash
cd backend
```

---

## Step 4.2: Create a Python virtual environment

A virtual environment keeps the project's Python packages separate from your system Python.

**Windows:**
```bash
python -m venv venv
```

**Linux/Mac:**
```bash
python3 -m venv venv
```

---

## Step 4.3: Activate the virtual environment

**Windows (Command Prompt):**
```bash
venv\Scripts\activate
```

**Windows (PowerShell):**
```bash
venv\Scripts\Activate.ps1
```

**Windows (Git Bash):**
```bash
source venv/Scripts/activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

You should see `(venv)` appear at the beginning of your terminal prompt:
```
(venv) C:\Projects\iams\backend>
```

> **Important:** You must activate the virtual environment every time you open a new terminal to work with the backend.

---

## Step 4.4: Install Python dependencies

```bash
pip install -r requirements.txt
```

This will download and install all required packages. The first time takes a few minutes because it includes PyTorch (~200MB).

> **Note:** This step requires an internet connection. After installation, the packages are cached locally.

If you see errors with PyTorch, try installing it separately first:
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

---

## Step 4.5: Verify the environment configuration

```bash
python -m scripts.validate_env
```

You should see output like:
```
IAMS Backend - Environment Configuration Validation
============================================================

Required Variables:
------------------------------------------------------------
✓ DATABASE_URL: Custom PostgreSQL connection
✓ SECRET_KEY: Set (88 characters)

Optional Variables:
------------------------------------------------------------
⚠️  SUPABASE_SERVICE_KEY: Not set (required for admin operations)
⚠️  DEBUG: Enabled (disable in production!)
⚠️  CORS_ORIGINS: Wildcard detected (specify exact origins in production)

File Paths:
------------------------------------------------------------
✓ FAISS_INDEX_PATH: data/faiss/faces.index
✓ UPLOAD_DIR: data/uploads/faces
✓ LOG_FILE: logs/app.log

Numeric Settings:
------------------------------------------------------------
✓ RECOGNITION_THRESHOLD: 0.6
✓ ACCESS_TOKEN_EXPIRE_MINUTES: 30

============================================================
✓ All validations passed!
```

The warnings (⚠️) about Supabase and CORS are expected — they are not errors.

---

## What You Just Set Up

- **Virtual environment** — Isolated Python environment for the project
- **FastAPI** — The web framework that serves the API
- **SQLAlchemy** — Database ORM (talks to PostgreSQL)
- **FaceNet + FAISS** — Face recognition ML models
- **PyTorch** — ML framework used by FaceNet
- **Alembic** — Database migration tool

---

**Next step:** [05 - Run Migrations](../05-run-migrations/README.md)
