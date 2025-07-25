-- Code Extraction Settings Migration
-- Adds configurable settings for the code extraction service

-- Insert Code Extraction Configuration Settings
INSERT INTO settings (key, value, is_encrypted, category, description) VALUES
-- Length Settings
('MIN_CODE_BLOCK_LENGTH', '250', false, 'code_extraction', 'Base minimum length for code blocks in characters'),
('MAX_CODE_BLOCK_LENGTH', '5000', false, 'code_extraction', 'Maximum length before stopping code block extension in characters'),
('CONTEXT_WINDOW_SIZE', '1000', false, 'code_extraction', 'Number of characters of context to preserve before and after code blocks'),

-- Detection Features
('ENABLE_COMPLETE_BLOCK_DETECTION', 'true', false, 'code_extraction', 'Extend code blocks to natural boundaries like closing braces'),
('ENABLE_LANGUAGE_SPECIFIC_PATTERNS', 'true', false, 'code_extraction', 'Use specialized patterns for different programming languages'),
('ENABLE_CONTEXTUAL_LENGTH', 'true', false, 'code_extraction', 'Adjust minimum length based on surrounding context (example, snippet, implementation)'),

-- Content Filtering
('ENABLE_PROSE_FILTERING', 'true', false, 'code_extraction', 'Filter out documentation text mistakenly wrapped in code blocks'),
('MAX_PROSE_RATIO', '0.15', false, 'code_extraction', 'Maximum allowed ratio of prose indicators (0-1) in code blocks'),
('MIN_CODE_INDICATORS', '3', false, 'code_extraction', 'Minimum number of code patterns required (brackets, operators, keywords)'),
('ENABLE_DIAGRAM_FILTERING', 'true', false, 'code_extraction', 'Exclude diagram languages like Mermaid, PlantUML from code extraction'),

-- Processing Settings
('CODE_EXTRACTION_MAX_WORKERS', '3', false, 'code_extraction', 'Number of parallel workers for generating code summaries'),
('ENABLE_CODE_SUMMARIES', 'true', false, 'code_extraction', 'Generate AI-powered summaries and names for extracted code examples')

-- Only insert if they don't already exist
ON CONFLICT (key) DO NOTHING;

-- Add a comment to document when this migration was added
COMMENT ON TABLE settings IS 'Stores application configuration including API keys, RAG settings, and code extraction parameters';