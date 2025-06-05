---
trigger: manual
---

trigger: always_on
---

# Congressional MCP Development Rules

## Critical Architecture Rules
1. **Production deployment uses Procfile**: `web: uvicorn asgi:app --host=0.0.0.0 --port=$PORT --workers=1`
2. **asgi.py is the main entry point** - Direct FastMCP ASGI deployment with authentication middleware
3. **production_server.py is NOT used for Heroku** - It's kept for alternative deployment scenarios only
4. **API endpoint is /mcp/** not root - Requires MCP protocol headers and session authentication
5. **Single worker only** - MCP servers require single worker for proper session management


## MCP Tool Function Requirements
1. **All MCP tools MUST have ctx: Context parameter** - Required for make_api_request calls
2. **Use @mcp.tool() decorator** - Not @mcptool()
3. **Import Context from mcp** - Essential for authentication and session management
4. **ctx must be first parameter** in function signature

## Error Handling Patterns
1. **Check for "error" in data response** - `if "error" in data: return f"Error: {data['error']}"`
2. **Handle empty results** - Check if results list is empty and return helpful message
3. **Return user-friendly errors** - Convert API errors to readable messages
4. **Use consistent error message format** - "Error [action]: [details]"

## Deployment Verification
1. **Check API health**: `curl -s https://api-cmcp.lawgiver.ai/mcp/` should return MCP protocol error (not 404)
2. **Verify proper headers**: API requires `Accept: text/event-stream` and session management
3. **Test through MCP tools**: Use actual MCP tool calls to verify fixes work end-to-end
4. **Monitor for authentication issues**: MCP session management can cause temporary test failures

## Code Structure Rules
1. **Features are modular** - Each feature has its own file in `congress_api/features/`
2. **All features import from congress_api.mcp_app** - Use `from congress_api.mcp_app import mcp`
3. **Features auto-register** - Import in `congress_api/main.py` to register with MCP server
4. **Use proper type hints** - Optional[int], Optional[str] for optional parameters

## Testing Organization Rules
1. **All test files must be placed in `/tests/` directory** - Never create test files in root or other directories
2. **Use naming convention**: `test_[feature_name].py` for test files, `run_[category]_tests.py` for test runners
3. **Test files must use relative imports**: `sys.path.append(os.path.join(os.path.dirname(__file__), '..'))`
4. **Create mock data files** as `mock_[api_endpoint].json` in `tests/fixtures/` subdirectory
5. **All new backend features must include corresponding tests** with mock data based on actual API responses
6. **Test runners must provide clear pass/fail summaries** and be runnable from tests directory
7. **Test categories**: API functionality, database operations, email services, authentication, integration tests
8. **Tests must be executable without external API dependencies** using mock data
9. **Use comprehensive test coverage** - formatting functions, error handling, edge cases, search logic
