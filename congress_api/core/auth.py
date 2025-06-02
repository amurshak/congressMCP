# auth.py
import os
import time
import logging
import jwt
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Import database functionality
from .database import validate_api_key as db_validate_api_key, track_usage as db_track_usage

# Configure logger
logger = logging.getLogger(__name__)

# Load environment variables
JWT_SECRET = os.getenv("LAWGIVER_JWT_SECRET", "")
API_KEYS = os.getenv("LAWGIVER_API_KEYS", "").split(",")
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"
ENABLE_DATABASE = os.getenv("ENABLE_DATABASE", "true").lower() == "true"

# Define subscription tiers
class SubscriptionTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

# Define rate limits and feature access for each tier
TIER_CONFIG = {
    SubscriptionTier.FREE: {
        "rate_limit": 200,  # 50 calls per week * 4 weeks = 200 per month
        "features": ["bills", "members", "committees", "congress_info"]  # Basic tools only
    },
    SubscriptionTier.PRO: {
        "rate_limit": 5000,  # 5,000 calls per month
        "features": ["bills", "members", "committees", "congress_info", 
                    "amendments", "summaries", "committee_reports", 
                    "committee_prints", "committee_meetings", "hearings",
                    "congressional_record", "daily_congressional_record", 
                    "bound_congressional_record", "house_communications",
                    "house_requirements", "senate_communications",
                    "nominations", "crs_reports", "treaties"]  # All 23 tool categories
    },
    SubscriptionTier.ENTERPRISE: {
        "rate_limit": 100000,  # Very high limit (effectively unlimited)
        "features": ["bills", "members", "committees", "congress_info", 
                    "amendments", "summaries", "committee_reports", 
                    "committee_prints", "committee_meetings", "hearings",
                    "congressional_record", "daily_congressional_record", 
                    "bound_congressional_record", "house_communications",
                    "house_requirements", "senate_communications", 
                    "nominations", "crs_reports", "treaties"]  # All tools + future features
    }
}

# In-memory storage for rate limiting
# In production, this should be replaced with Redis or another distributed cache
class RateLimitStorage:
    def __init__(self):
        self.storage: Dict[str, Dict[str, Any]] = {}
    
    def get_user_requests(self, user_id: str) -> Tuple[int, datetime]:
        """Get the number of requests made by a user today."""
        if user_id not in self.storage:
            self.storage[user_id] = {"count": 0, "reset_time": datetime.now() + timedelta(days=1)}
            return 0, self.storage[user_id]["reset_time"]
        
        # Check if we need to reset the counter
        if datetime.now() > self.storage[user_id]["reset_time"]:
            self.storage[user_id] = {"count": 0, "reset_time": datetime.now() + timedelta(days=1)}
            return 0, self.storage[user_id]["reset_time"]
        
        return self.storage[user_id]["count"], self.storage[user_id]["reset_time"]
    
    def increment_user_requests(self, user_id: str) -> int:
        """Increment the number of requests made by a user today."""
        count, _ = self.get_user_requests(user_id)
        self.storage[user_id]["count"] = count + 1
        return self.storage[user_id]["count"]

# Initialize rate limit storage
rate_limit_storage = RateLimitStorage()

# Security scheme for API key authentication
security = HTTPBearer()

def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decode a JWT token and return the payload."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError as e:
        logger.error(f"JWT decode error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")

async def validate_api_key(api_key: str) -> Dict[str, Any]:
    """Validate an API key and return the associated metadata."""
    if ENABLE_DATABASE:
        # Use database validation
        result = await db_validate_api_key(api_key)
        if not result:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return result
    else:
        # Fallback to simple validation for development
        # Format: tier:user_id:key
        if not api_key or ":" not in api_key:
            raise HTTPException(status_code=401, detail="Invalid API key format")
        
        parts = api_key.split(":")
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Invalid API key format")
        
        tier, user_id, key = parts
        
        # Check if the key is in our list of valid keys
        if api_key not in API_KEYS and ENABLE_AUTH:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Validate the tier
        if tier not in [t.value for t in SubscriptionTier]:
            tier = SubscriptionTier.FREE.value
        
        return {
            "user_id": user_id,
            "tier": SubscriptionTier(tier),
            "email": f"user_{user_id}@example.com",
            "is_active": True
        }

async def get_token_from_request(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Extract and validate the token from the request."""
    token = credentials.credentials
    
    # Try JWT first
    if token.startswith("eyJ"):
        user_info = decode_jwt_token(token)
        if user_info:
            return user_info
    
    # Try API key validation
    return await validate_api_key(token)

async def check_rate_limit(user_id: str, tier: str, feature: str = "general", endpoint: str = "") -> None:
    """Check if a user has exceeded their rate limit."""
    if ENABLE_DATABASE:
        # Track usage in database
        await db_track_usage(user_id, feature, endpoint)
        
        # Get daily usage from database
        from .database import db_client
        daily_usage = await db_client.get_daily_usage(user_id)
        rate_limit = TIER_CONFIG.get(SubscriptionTier(tier), {}).get("rate_limit", 100)
        
        if daily_usage >= rate_limit:
            raise HTTPException(
                status_code=429, 
                detail=f"Daily rate limit ({rate_limit}) exceeded. Usage: {daily_usage}"
            )
    else:
        # Use in-memory rate limiting
        rate_limit = TIER_CONFIG.get(SubscriptionTier(tier), {}).get("rate_limit", 100)
        count, reset_time = rate_limit_storage.get_user_requests(user_id)
        
        if count >= rate_limit:
            reset_time_str = reset_time.strftime("%Y-%m-%d %H:%M:%S UTC")
            raise HTTPException(
                status_code=429, 
                detail=f"Rate limit exceeded. Limit: {rate_limit} requests per day. Resets at {reset_time_str}"
            )
        
        rate_limit_storage.increment_user_requests(user_id)

def check_feature_access(feature: str, tier: str) -> bool:
    """Check if a user's tier has access to a specific feature."""
    return feature in TIER_CONFIG[tier]["features"]

async def auth_middleware(request: Request, call_next):
    """Middleware to handle authentication and rate limiting."""
    # Skip authentication for OPTIONS requests and if auth is disabled
    if request.method == "OPTIONS" or not ENABLE_AUTH:
        return await call_next(request)
    
    # Skip authentication for certain paths
    skip_auth_paths = ["/docs", "/redoc", "/openapi.json", "/health", "/stripe/webhook", "/stripe/", "/keys/"]
    if any(request.url.path.startswith(path) for path in skip_auth_paths):
        return await call_next(request)
    
    try:
        # Extract the token from the Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="Authorization header missing")
        
        # Validate the token
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            try:
                # Try to decode as JWT
                payload = decode_jwt_token(token)
            except:
                # If JWT decode fails, try as API key
                payload = await validate_api_key(token)
        else:
            # Treat as API key
            payload = await validate_api_key(auth_header)
        
        # Check rate limit
        await check_rate_limit(payload["user_id"], payload["tier"])
        
        # Check feature access based on the path
        path_parts = request.url.path.strip("/").split("/")
        if len(path_parts) > 0:
            feature = path_parts[0]
            if feature and not check_feature_access(feature, payload["tier"]):
                raise HTTPException(
                    status_code=403, 
                    detail=f"Your subscription tier ({payload['tier']}) does not have access to this feature"
                )
        
        # Add user info to request state
        request.state.user = payload
        
        # Continue with the request
        return await call_next(request)
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

async def generate_api_key(user_id: str, tier: SubscriptionTier) -> str:
    """Generate an API key for a user."""
    if ENABLE_DATABASE:
        from .database import db_client
        api_key = await db_client.create_api_key(user_id, tier)
        if not api_key:
            raise HTTPException(status_code=500, detail="Failed to generate API key")
        return api_key
    else:
        # Simple key generation for development
        key = f"{tier.value}:{user_id}:{int(time.time())}"
        return key

def generate_jwt_token(user_id: str, tier: SubscriptionTier, expiry_days: int = 30) -> str:
    """Generate a JWT token for a user."""
    payload = {
        "user_id": user_id,
        "tier": tier.value,
        "exp": datetime.utcnow() + timedelta(days=expiry_days)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return token
