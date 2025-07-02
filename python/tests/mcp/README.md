# MCP Container Tests

## Testing Strategy

Since our tests run in the Server container (for UI integration), we test MCP functionality from the Server's perspective:

1. **Server-side tests** - Located in `../server/test_mcp_*.py`
   - Test Server's API endpoints that interact with MCP
   - Mock MCP responses based on actual MCP implementation
   - Verify proper error handling and data transformation

2. **Direct MCP tests** - Would require:
   - Running tests inside the MCP container
   - Or creating a separate test runner for MCP container
   - Currently not implemented due to UI test execution requirements

## Current Test Coverage

MCP functionality is tested through:
- `../server/test_mcp_integration.py` - Integration tests
- `../server/test_mcp_tools_via_server.py` - Tool functionality tests
- `../server/test_mcp_api.py` - MCP management endpoints

## Future Improvements

If we need direct MCP tool testing:
1. Create a separate test suite that runs in MCP container
2. Add a test endpoint in MCP server for direct tool testing
3. Use container exec to run MCP-specific tests