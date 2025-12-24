-- Add preferred_language column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(2) DEFAULT 'pt';

-- Add index for faster lookups (optional)
CREATE INDEX IF NOT EXISTS idx_user_preferred_language ON users(preferred_language) WHERE preferred_language IS NOT NULL;


