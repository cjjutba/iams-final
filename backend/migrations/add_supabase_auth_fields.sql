-- Migration: Add Supabase Auth fields to users table
-- Part of MOD-01 Authentication and Identity migration
-- Run this migration BEFORE enabling USE_SUPABASE_AUTH=true

-- Add Supabase Auth user ID reference
ALTER TABLE users
ADD COLUMN IF NOT EXISTS supabase_user_id UUID UNIQUE;

-- Add email verification fields
ALTER TABLE users
ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP;

-- Make password_hash nullable (Supabase-managed users won't have one)
ALTER TABLE users
ALTER COLUMN password_hash DROP NOT NULL;

-- Index for fast Supabase user lookups
CREATE INDEX IF NOT EXISTS idx_users_supabase_user_id
ON users(supabase_user_id);

-- Mark existing users as email-verified (they registered before verification was enforced)
UPDATE users
SET email_verified = TRUE,
    email_verified_at = NOW()
WHERE email_verified = FALSE
  AND is_active = TRUE;
