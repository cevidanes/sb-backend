-- Migration: Add PROCESSING and FAILED statuses to sessionstatus enum
-- This migration adds the missing processing and failed statuses to the existing sessionstatus enum type
-- Run this migration to fix the "invalid input value for enum sessionstatus: 'processing'" and 'failed' errors

-- Add the new enum values (IF NOT EXISTS is supported in PostgreSQL 9.3+)
ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'processing';
ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'failed';

