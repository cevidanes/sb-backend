-- Migration: Add OPEN status to sessionstatus enum
-- This migration adds the 'open' status to the existing sessionstatus enum type
-- Run this migration to fix the "invalid input value for enum sessionstatus: 'open'" error
-- Note: PostgreSQL creates enum types in lowercase by default (sessionstatus, not session_status)

-- First, check if enum type exists, if not create it with all values
DO $$
BEGIN
    -- Check if enum type exists
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sessionstatus') THEN
        -- Create enum type with all values
        CREATE TYPE sessionstatus AS ENUM (
            'open',
            'pending_processing',
            'processing',
            'processed',
            'raw_only',
            'no_credits',
            'failed'
        );
    ELSE
        -- Enum exists, add 'open' if it doesn't exist
        -- Note: PostgreSQL doesn't support IF NOT EXISTS for ADD VALUE, so we check first
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumlabel = 'open' 
            AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'sessionstatus')
        ) THEN
            ALTER TYPE sessionstatus ADD VALUE 'open';
        END IF;
    END IF;
END $$;

