-- Add fcm_token column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_token VARCHAR(512);

-- Add index for faster lookups (optional, but useful if you query by token)
CREATE INDEX IF NOT EXISTS idx_user_fcm_token ON users(fcm_token) WHERE fcm_token IS NOT NULL;

