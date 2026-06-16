-- Migration 005: CFA Level 3 specific fields and new platforms
--
-- NOTE: the platform columns in this schema are TEXT + CHECK constraints
-- (see 001_initial.sql), NOT a Postgres ENUM. An earlier version of this
-- migration used `ALTER TYPE platform_type ADD VALUE ...`, which fails with
-- "type platform_type does not exist". The correct approach is to replace the
-- CHECK constraint, which is what this migration now does.

-- 1. New columns -------------------------------------------------------------
ALTER TABLE raw_content ADD COLUMN IF NOT EXISTS affected_segments JSONB DEFAULT '[]'::jsonb;
ALTER TABLE ideas       ADD COLUMN IF NOT EXISTS target_persona     TEXT;
ALTER TABLE drafts      ADD COLUMN IF NOT EXISTS target_persona     TEXT;
ALTER TABLE drafts      ADD COLUMN IF NOT EXISTS compliance_status  TEXT DEFAULT 'pending';

-- 2. Extend platform CHECK constraints to allow the 3 new platforms ----------
--    The DO blocks drop whatever the existing platform check is named, so this
--    works regardless of the auto-generated constraint name.
DO $$
DECLARE c text;
BEGIN
  FOR c IN SELECT conname FROM pg_constraint
           WHERE conrelid = 'ideas'::regclass AND contype = 'c'
             AND pg_get_constraintdef(oid) ILIKE '%platform%'
  LOOP EXECUTE format('ALTER TABLE ideas DROP CONSTRAINT %I', c); END LOOP;
END $$;
ALTER TABLE ideas ADD CONSTRAINT ideas_platform_check
  CHECK (platform IN ('linkedin','twitter','blog','email','whatsapp','carousel','advisor_talking_points'));

DO $$
DECLARE c text;
BEGIN
  FOR c IN SELECT conname FROM pg_constraint
           WHERE conrelid = 'drafts'::regclass AND contype = 'c'
             AND pg_get_constraintdef(oid) ILIKE '%platform%'
  LOOP EXECUTE format('ALTER TABLE drafts DROP CONSTRAINT %I', c); END LOOP;
END $$;
ALTER TABLE drafts ADD CONSTRAINT drafts_platform_check
  CHECK (platform IN ('linkedin','twitter','blog','email','whatsapp','carousel','advisor_talking_points'));
