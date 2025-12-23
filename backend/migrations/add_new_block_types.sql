-- Migration: Add new BlockType values for backend processing
-- Adds 'text', 'transcription_backend', and 'image_description' to blocktype enum
-- If block_type is VARCHAR (not enum), this migration does nothing (safe to run)

DO $$
BEGIN
    -- Check if blocktype enum exists
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'blocktype') THEN
        -- Enum exists, add new values if they don't exist
        -- Add 'text'
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumlabel = 'text' 
            AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'blocktype')
        ) THEN
            ALTER TYPE blocktype ADD VALUE 'text';
        END IF;
        
        -- Add 'transcription_backend'
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumlabel = 'transcription_backend' 
            AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'blocktype')
        ) THEN
            ALTER TYPE blocktype ADD VALUE 'transcription_backend';
        END IF;
        
        -- Add 'image_description'
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumlabel = 'image_description' 
            AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'blocktype')
        ) THEN
            ALTER TYPE blocktype ADD VALUE 'image_description';
        END IF;
    END IF;
    -- If enum doesn't exist, column is likely VARCHAR and accepts any string value
END $$;

