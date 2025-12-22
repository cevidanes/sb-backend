-- Migration: Add NO_CREDITS status to sessionstatus enum
-- This migration adds the new NO_CREDITS status to the existing sessionstatus enum type
-- Run this migration before deploying the new code
-- Note: PostgreSQL creates enum types in lowercase by default (sessionstatus, not session_status)

-- Add the new enum value
ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'no_credits';

-- Note: PostgreSQL doesn't support removing enum values, so RAW_ONLY remains for backward compatibility
-- New sessions without credits will use NO_CREDITS status
-- Existing RAW_ONLY sessions will continue to work normally

