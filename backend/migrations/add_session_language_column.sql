-- Add language column to sessions table
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS language VARCHAR(10);

-- Create index for language column
CREATE INDEX IF NOT EXISTS idx_sessions_language ON sessions(language) WHERE language IS NOT NULL;

