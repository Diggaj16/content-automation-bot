-- Migration to add CFA Level 3 specific fields and new platforms

-- Add affected_segments to raw_content
ALTER TABLE raw_content ADD COLUMN IF NOT EXISTS affected_segments JSONB DEFAULT '[]'::jsonb;

-- Add target_persona to ideas
ALTER TABLE ideas ADD COLUMN IF NOT EXISTS target_persona TEXT;

-- Add target_persona and compliance_status to drafts
ALTER TABLE drafts ADD COLUMN IF NOT EXISTS target_persona TEXT;
ALTER TABLE drafts ADD COLUMN IF NOT EXISTS compliance_status TEXT DEFAULT 'pending';

-- Update Platform ENUM (Need to drop and recreate or add values)
-- PostgreSQL allows adding enum values using ALTER TYPE
ALTER TYPE platform_type ADD VALUE IF NOT EXISTS 'whatsapp';
ALTER TYPE platform_type ADD VALUE IF NOT EXISTS 'carousel';
ALTER TYPE platform_type ADD VALUE IF NOT EXISTS 'advisor_talking_points';
