-- Migration: Add ai_summary and suggested_title columns to sessions table
-- These columns store the AI processing results

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS ai_summary TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS suggested_title VARCHAR(255);

