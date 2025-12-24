-- Add stripe_customer_id column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255);

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_stripe_customer_id ON users(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

