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
        
        # Check feature access for tool calls by examining request body
        try:
            # Collect request body
            body_parts = []
            while True:
                message = await receive()
                if message["type"] == "http.request":
                    body_parts.append(message.get("body", b""))
                    if not message.get("more_body", False):
                        break
            
            request_body = b"".join(body_parts)
            
            # Parse MCP request
            if request_body:
                try:
                    mcp_request = json.loads(request_body.decode('utf-8'))
                    
                    # Check tool access for tool calls
                    if mcp_request.get('method') == 'tools/call':
                        tool_name = mcp_request.get('params', {}).get('name', '')
                        if tool_name and not await self._check_tool_access(tool_name, user_tier, user_info):
                            await self._send_feature_access_error(send, user_info['tier'], tool_name)
                            return
                    
                    # Check rate limiting
                    from .auth import check_rate_limit
                    await check_rate_limit(user_info["user_id"], user_info["tier"])
                    
                except json.JSONDecodeError:
                    # If we can't parse JSON, let FastMCP handle it
                    logger.debug("Could not parse MCP request JSON, proceeding without feature check")
                except Exception as rate_error:
                    if "rate limit" in str(rate_error).lower():
                        await self._send_rate_limit_error(send, str(rate_error))
                        return
                    logger.error(f"Rate limit check error: {rate_error}")
            
            # Create new receive callable that replays the body
            async def replay_receive():
                return {
                    "type": "http.request", 
                    "body": request_body,
                    "more_body": False
                }
            
            # Add user info to scope for downstream processing
            scope["user"] = user_info
            
            # Create a streaming-aware send wrapper for FastMCP responses
            async def streaming_send(message):
                """Send wrapper that properly handles FastMCP streaming responses"""
                # Pass through all FastMCP streaming messages directly
                await send(message)
            
            # Forward to FastMCP app with streaming-aware send wrapper
            await self.app(scope, replay_receive, streaming_send)
            
        except Exception as e:
            logger.error(f"Error in authentication middleware: {e}")
            await self._send_auth_error(
                send,
                code=-32000,
                message="Internal server error",
                details="Please try again or contact support",
                status_code=500
            )
    
    async def _check_tool_access(self, tool_name: str, user_tier: "SubscriptionTier", user_info: Dict[str, Any]) -> bool:
        """Check if user's tier has access to the requested tool"""
        
        # Extract feature category from tool name
        feature_category = self._extract_feature_category(tool_name)
        
        # Import here to avoid circular imports
        from .auth import check_feature_access
        return check_feature_access(feature_category, user_info['tier'])  # Pass tier as string
    
    def _extract_feature_category(self, tool_name: str) -> str:
        """Extract feature category from tool name for access control"""
        
        # Handle MCP tool names like "mcp0_search_bills" -> "bills"
        if tool_name.startswith("mcp0_"):
            parts = tool_name.split("_")
            if len(parts) >= 2:
                # Extract the main feature (e.g., "search_bills" -> "bills", "get_bill_details" -> "bills")
                action_part = "_".join(parts[1:])
                if "bill" in action_part:
                    return "bills"
                elif "member" in action_part:
                    return "members"
                elif "committee" in action_part:
                    return "committees"
                elif "amendment" in action_part:
                    return "amendments"
                elif "congress" in action_part:
                    return "congress_info"
                elif "nomination" in action_part:
                    return "nominations"
                elif "treaty" in action_part:
                    return "treaties"
                elif "hearing" in action_part:
                    return "hearings"
                elif "record" in action_part:
                    return "congressional_record"
                elif "crs" in action_part:
                    return "crs_reports"
                elif "summary" in action_part:
                    return "summaries"
                else:
                    # Default to the first meaningful part
                    return parts[1] if len(parts) > 1 else "bills"
        
        # Handle direct tool names
        if "_" in tool_name:
            base = tool_name.split("_")[0]
            if base in ["get", "search"]:
                return tool_name.split("_")[1] if len(tool_name.split("_")) > 1 else "bills"
            return base
        
        # Default mapping for common tools
        tool_mappings = {
            "bills": "bills",
            "members": "members", 
            "committees": "committees",
            "congress": "congress_info"
        }
        
        return tool_mappings.get(tool_name, "bills")  # Default to bills for unknown tools
    
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
    
    async def _send_feature_access_error(self, send: Send, user_tier: str, tool_name: str):
        """Send error response for tier-based feature access denial"""
        
        available_features = {
            "FREE": "bills, members, committees, congress_info",
            "PRO": "All 23 tool categories", 
            "ENTERPRISE": "All tools + priority support"
        }
        
        error_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32003,
                "message": f"Tool '{tool_name}' not available in {user_tier} tier",
                "data": {
                    "current_tier": user_tier,
                    "available_features": available_features.get(user_tier, "Unknown"),
                    "upgrade_url": "https://congressmcp.lawgiver.ai",
                    "pricing_info": {
                        "PRO_MONTHLY": "$29/month - 5,000 calls/month, all tools",
                        "PRO_ANNUAL": "$299/year - 5,000 calls/month, all tools (save 14%)",
                        "ENTERPRISE": "Custom pricing - 100K calls/month, priority support"
                    }
                }
            }
        }
        
        response_body = json.dumps(error_response).encode("utf-8")
        
        await send({
            "type": "http.response.start",
            "status": 403,
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
