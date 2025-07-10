-- Migration to remove update_frequency column from sources table
-- This column is being replaced with manual refresh functionality

-- Drop the index first
DROP INDEX IF EXISTS idx_sources_update_frequency;

-- Remove the column from the sources table
ALTER TABLE sources DROP COLUMN IF EXISTS update_frequency;

-- Remove the comment that was associated with the column
-- (Comments are automatically removed when column is dropped)