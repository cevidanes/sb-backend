-- Migration: Add payments table for tracking credit purchases
-- This table tracks all Stripe payment transactions for auditing and idempotency

-- Create enum for payment status
DO $$ BEGIN
    CREATE TYPE payment_status AS ENUM ('pending', 'completed', 'failed', 'refunded');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create payments table
CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Stripe identifiers for idempotency
    stripe_checkout_session_id VARCHAR(255) UNIQUE,
    stripe_payment_intent_id VARCHAR(255) UNIQUE,
    
    -- Payment details
    amount_cents INTEGER NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'usd',
    credits_amount INTEGER NOT NULL,
    
    -- Status
    status payment_status NOT NULL DEFAULT 'pending',
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    
    -- Package info
    package_id VARCHAR(50)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_payment_user_id ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_stripe_session ON payments(stripe_checkout_session_id);
CREATE INDEX IF NOT EXISTS idx_payment_stripe_intent ON payments(stripe_payment_intent_id);
CREATE INDEX IF NOT EXISTS idx_payment_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payment_created_at ON payments(created_at DESC);

-- Add comment for documentation
COMMENT ON TABLE payments IS 'Tracks all credit purchase transactions via Stripe';
COMMENT ON COLUMN payments.stripe_checkout_session_id IS 'Stripe Checkout Session ID for idempotency';
COMMENT ON COLUMN payments.stripe_payment_intent_id IS 'Stripe Payment Intent ID';
COMMENT ON COLUMN payments.amount_cents IS 'Amount paid in cents (e.g., 999 = $9.99)';
COMMENT ON COLUMN payments.credits_amount IS 'Number of AI credits purchased';

