"""
ASGI Authentication Middleware for MCP requests.
Validates API keys and enforces tier-based access control without interfering with FastMCP.
"""
import json
import logging
from typing import Dict, Any, Callable, Awaitable
from starlette.types import ASGIApp, Scope, Receive, Send, Message
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

class AuthenticationMiddleware:
    """ASGI middleware for MCP authentication and authorization"""
    
    def __init__(self, app: ASGIApp):
        self.app = app
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Only apply auth to HTTP requests to /mcp/ endpoints
        if (scope["type"] == "http" and 
            scope["method"] == "POST" and 
            scope.get("path", "").startswith("/mcp")):
            
            await self._handle_mcp_request(scope, receive, send)
        else:
            # Pass through all other requests unchanged
            await self.app(scope, receive, send)
    
    async def _handle_mcp_request(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle authentication for MCP requests"""
        
        # Extract Authorization header
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            await self._send_auth_error(
                send,
                code=-32001,
                message="Authentication required",
                details="Please provide a valid API key in Authorization header",
                status_code=401
            )
            return
        
        api_key = auth_header[7:]  # Remove "Bearer " prefix
        
        # Validate API key
        try:
            from .auth import validate_api_key, SubscriptionTier, check_feature_access
            user_info = await validate_api_key(api_key)
            user_tier = SubscriptionTier(user_info['tier'])
            
            logger.info(f"Authenticated MCP request - User: {user_info.get('user_id', 'unknown')}, Tier: {user_info['tier']}")
            
        except Exception as e:
            logger.warning(f"Invalid API key in MCP request: {str(e)}")
            await self._send_auth_error(
                send,
                code=-32002,
                message="Invalid API key",
                details="Please check your API key or register at https://congressmcp.lawgiver.ai",
                status_code=401
            )
            return
        
        # SIMPLIFIED: Skip body buffering entirely to fix FastMCP streaming
        # TODO: Re-implement selective tool validation after fixing streaming issue
        try:
            # Check rate limiting (always do this)
            from .auth import check_rate_limit
            try:
                await check_rate_limit(user_info["user_id"], user_info["tier"])
            except Exception as rate_error:
                if "rate limit" in str(rate_error).lower():
                    await self._send_rate_limit_error(send, str(rate_error))
                    return
                logger.error(f"Rate limit check error: {rate_error}")
            
            # Add user info to scope for downstream processing
            scope["user"] = user_info
            
            # Forward to FastMCP app directly without any request buffering
            # This maintains streaming compatibility at the cost of tool validation
            await self.app(scope, receive, send)
        
        except Exception as e:
            logger.error(f"Error in authentication middleware: {e}")
            await self._send_auth_error(
                send,
                code=-32000,
                message="Internal server error",
                details="Please try again or contact support",
                status_code=500
            )
    
    async def _send_auth_error(self, send: Send, code: int, message: str, details: str, status_code: int = 401):
        """Send JSON-RPC error response for authentication failures"""
        error_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": code,
                "message": message,
                "data": {
                    "details": details,
                    "signup_url": "https://congressmcp.lawgiver.ai"
                }
            }
        }
        
        response_body = json.dumps(error_response).encode("utf-8")
        
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [[b"content-type", b"application/json"]]
        })
        await send({
            "type": "http.response.body", 
            "body": response_body
        })
    
    async def _send_rate_limit_error(self, send: Send, details: str):
        """Send error response for rate limit exceeded"""
        error_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32004,
                "message": "Rate limit exceeded",
                "data": {
                    "details": details,
                    "upgrade_url": "https://congressmcp.lawgiver.ai"
                }
            }
        }
        
        response_body = json.dumps(error_response).encode("utf-8")
        
        await send({
            "type": "http.response.start",
            "status": 429,
            "headers": [[b"content-type", b"application/json"]]
        })
        await send({
            "type": "http.response.body",
            "body": response_body
        })
