# Migration Process Documentation

## Standard Migration Workflow

### 1. Generate Migration
```bash
cd backend
python -m alembic revision --autogenerate -m "descriptive_migration_name"
```

### 2. Review Generated Migration
- Check `backend/alembic/versions/` for new migration file
- Verify `upgrade()` function creates/modifies tables correctly
- Verify `downgrade()` function properly reverts changes
- Check for any data migrations that need manual handling

### 3. Apply Migration
```bash
python -m alembic upgrade head
```

### 4. Verify Migration
```bash
python -m alembic current   # Check current version
python -m alembic check     # Validate schema alignment
```

### 5. Test Rollback (Development Only)
```bash
python -m alembic downgrade -1   # Rollback one migration
python -m alembic upgrade head    # Re-apply
```

## Critical Notes

### Model Import Requirement
- **MUST import ALL models in `alembic/env.py`** before autogenerate runs
- Missing imports = autogenerate won't detect new tables
- Current pattern: `from app.models import *` ensures all models loaded

### Migration Testing
- Always test downgrade path in development
- Verify data is preserved after rollback/re-apply cycle
- Check foreign key constraints are properly created/dropped

### Supabase Connection
- Use pooler connection (IPv4) for migrations
- Direct connection (IPv6) may fail from development machine
- Connection string format: `postgresql://postgres.{project_ref}:{password}@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres`

### Data Migration Strategy
When adding non-nullable columns to existing tables:
1. First migration: Add column as NULLABLE
2. Backfill data with SQL UPDATE
3. Second migration: Alter column to NOT NULL

Example:
```python
# Migration 1: Add nullable
def upgrade():
    op.add_column('users', sa.Column('new_field', sa.String(100), nullable=True))
    # Backfill
    op.execute("UPDATE users SET new_field = 'default_value' WHERE new_field IS NULL")

# Migration 2: Make non-null
def upgrade():
    op.alter_column('users', 'new_field', nullable=False)
```

## Recent Migrations

### 86d63351d3e9: Add notifications table (2026-02-07)
- **Purpose:** Support in-app notifications for students and faculty
- **Changes:**
  - Created `notifications` table with user_id FK
  - Added indexes on user_id, type, created_at
  - Includes reference_id/reference_type for linking to attendance/early_leave events
- **Status:** Applied and tested
- **Rollback:** Clean, table drops successfully

## Troubleshooting

### "No new upgrade operations detected"
- Means schema is in sync with models
- Run `alembic check` to confirm
- If you expect changes, verify model imports in env.py

### Migration fails with "relation already exists"
- Database may be in inconsistent state
- Check `alembic_version` table: `SELECT * FROM alembic_version;`
- Manually stamp to correct version: `alembic stamp <revision_id>`

### Connection timeout during migration
- Supabase pooler may have rate limits
- Add timeout to alembic.ini: `pool_pre_ping = true`
- Retry after a few seconds

### UUID default issue
- Models use `default=uuid.uuid4` (Python-side)
- NOT `server_default=text('gen_random_uuid()')` (DB-side)
- UUIDs must be generated in application code before insert
