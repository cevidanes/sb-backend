-- Migration: Add PENDING_PROCESSING status to sessionstatus enum
-- This migration adds the pending_processing status to the existing sessionstatus enum type
-- Run this migration before deploying the new code

-- Add the new enum value
ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'pending_processing';

