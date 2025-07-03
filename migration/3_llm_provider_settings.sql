-- Migration to add LLM Provider settings for multi-provider support
-- Supports OpenAI, OpenRouter, Ollama, and Google Gemini

-- Add LLM Provider configuration settings
INSERT INTO settings (key, value, is_encrypted, category, description) VALUES
('LLM_PROVIDER', 'openai', false, 'rag_strategy', 'LLM provider to use: openai, openrouter, ollama, or google'),
('LLM_BASE_URL', NULL, false, 'rag_strategy', 'Custom base URL for LLM provider (mainly for Ollama, e.g., http://localhost:11434/v1)'),
('EMBEDDING_MODEL', 'text-embedding-3-small', false, 'rag_strategy', 'Embedding model for vector search and similarity matching (required for all embedding operations)')
ON CONFLICT (key) DO NOTHING;

-- Add provider API key placeholders
INSERT INTO settings (key, encrypted_value, is_encrypted, category, description) VALUES
('openrouter_api_key', NULL, true, 'api_keys', 'OpenRouter API Key for accessing multiple models. Get from: https://openrouter.ai/keys'),
('google_api_key', NULL, true, 'api_keys', 'Google API Key for Gemini models. Get from: https://aistudio.google.com/apikey')
ON CONFLICT (key) DO NOTHING;

-- Note: Ollama doesn't require an API key since it runs locally