# CRITICAL: Test Safety Guidelines

## ⚠️ IMPORTANT: Tests Were Saving to Production Database!

A critical issue was discovered where integration tests were using REAL services and saving data to the production database. This has been fixed, but all developers must follow these guidelines.

## Test Safety Rules

### 1. NEVER Use Real Services in Tests
- ❌ NEVER import `get_supabase_client()` directly
- ❌ NEVER import `get_crawler()` directly  
- ❌ NEVER use real API keys or credentials
- ❌ NEVER make real HTTP requests
- ❌ NEVER connect to production databases

### 2. ALWAYS Use Mocks
- ✅ Use mock fixtures from `conftest.py`
- ✅ Use `mock_supabase_client` fixture
- ✅ Use `mock_crawler` fixture
- ✅ Mock all external services
- ✅ Mock all API calls

### 3. Fixed Test Files
The following files were using real services and have been fixed:
- `test_background_tasks_integration.py` - Was using real Supabase client and crawler

### 4. How to Write Safe Tests

```python
# BAD - Uses real services
from src.server.services.client_manager import get_supabase_client
client = get_supabase_client()  # THIS CONNECTS TO REAL DATABASE!

# GOOD - Uses mock
def test_something(mock_supabase_client):
    client = mock_supabase_client  # Safe mock that won't touch real DB
```

### 5. Running Tests Safely

Always verify tests are not making real connections:
```bash
# Check for dangerous imports
grep -r "get_supabase_client()" tests/
grep -r "get_crawler()" tests/
grep -r "create_client" tests/

# Run tests with safety checks
docker exec Archon-Server pytest tests/ -v
```

### 6. Environment Variables

Tests should override production environment variables:
- Set `TESTING=true`
- Use mock URLs for services
- Use test API keys

## What Happened

The test file `test_background_tasks_integration.py` was crawling a real URL (https://raw.githubusercontent.com/anthropics/anthropic-cookbook/main/README.md) and saving it to the production Supabase database. This has been fixed by replacing real service calls with mocks.

## Prevention

1. Code review all test files for real service usage
2. Add CI checks to prevent real service imports in tests
3. Use fixture-based mocking consistently
4. Document testing best practices

## If You Find Real Service Usage in Tests

1. STOP and fix immediately
2. Replace with appropriate mocks
3. Verify no production data was affected
4. Update this document with the fix