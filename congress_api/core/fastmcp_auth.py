"""
FastMCP-native authentication provider for Congressional MCP
Uses FastMCP's built-in auth system instead of custom middleware
"""

import asyncio
import logging
import time
from typing import Any, Dict

from mcp.server.auth.provider import AccessToken
from fastmcp.server.auth import BearerAuthProvider

logger = logging.getLogger(__name__)

class CongressionalMCPAuthProvider(BearerAuthProvider):
    """
    Custom FastMCP auth provider that validates Congressional MCP API keys
    Uses our existing Supabase authentication and rate limiting
    """
    
    def __init__(self):
        # Initialize with dummy values since we're overriding the validation
        super().__init__(
            public_key="dummy",  # Not used - we override validation
            issuer="https://congressmcp.lawgiver.ai",
            audience="congressional-mcp",
            required_scopes=["mcp:access"]
        )
        
        # Import here to avoid circular imports
        from .auth import validate_api_key, check_rate_limit, get_user_info
        self.validate_api_key = validate_api_key
        self.check_rate_limit = check_rate_limit
        self.get_user_info = get_user_info
        
        # Set up thread pool for database operations
        import concurrent.futures
        self._db_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)
    
    async def load_access_token(self, token: str) -> AccessToken | None:
        """
        Validates Congressional MCP API keys using our existing auth system
        
        Args:
            token: The API key token (format: "tier_sub_apikey")
            
        Returns:
            AccessToken object if valid, None if invalid
        """
        try:
            # Run the sync database operations in a thread pool
            loop = asyncio.get_event_loop()
            
            # Validate API key
            user_info = await loop.run_in_executor(
                self._db_thread_pool, 
                self.validate_api_key, 
                token
            )
            
            if not user_info:
                logger.debug(f"Invalid API key: {token[:20]}...")
                return None
            
            # Check rate limiting  
            try:
                await loop.run_in_executor(
                    self._db_thread_pool,
                    lambda: asyncio.run(self.check_rate_limit(user_info["user_id"], user_info["tier"]))
                )
            except Exception as rate_error:
                if "rate limit" in str(rate_error).lower():
                    logger.warning(f"Rate limit exceeded for user {user_info['user_id']}: {rate_error}")
                    return None
                logger.error(f"Rate limit check error: {rate_error}")
            
            # Return valid access token
            return AccessToken(
                token=token,
                client_id=user_info["user_id"],
                scopes=["mcp:access", f"tier:{user_info['tier'].lower()}"],
                expires_at=int(time.time()) + 3600,  # 1 hour from now
            )
            
        except Exception as e:
            logger.error(f"Error in Congressional MCP auth validation: {e}")
            return None
