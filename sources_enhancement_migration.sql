-- Migration: Enhance sources table with title and metadata
-- Date: 2025-06-01
-- Description: Add title and metadata JSONB columns to sources table for better organization and categorization

-- Add title column to store descriptive titles like "Pydantic AI API Reference"
ALTER TABLE sources 
ADD COLUMN IF NOT EXISTS title TEXT;

-- Add metadata JSONB column to store knowledge_type, tags, and other metadata
ALTER TABLE sources 
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_sources_title ON sources(title);
CREATE INDEX IF NOT EXISTS idx_sources_metadata ON sources USING GIN(metadata);

-- Create index for knowledge_type specifically since it will be commonly queried
CREATE INDEX IF NOT EXISTS idx_sources_knowledge_type ON sources((metadata->>'knowledge_type'));

-- Update existing records to have empty metadata if null
UPDATE sources 
SET metadata = '{}' 
WHERE metadata IS NULL;

-- Add comments to document the new columns
COMMENT ON COLUMN sources.title IS 'Descriptive title for the source (e.g., "Pydantic AI API Reference")';
COMMENT ON COLUMN sources.metadata IS 'JSONB field storing knowledge_type, tags, and other metadata';

-- Example of metadata structure:
-- {
--   "knowledge_type": "technical" | "business",
--   "tags": ["python", "ai", "framework"],
--   "category": "documentation",
--   "language": "python",
--   "difficulty": "intermediate",
--   "last_updated": "2025-06-01"
-- } 