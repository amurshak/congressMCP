# key_management.py
import os
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .auth import generate_api_key, generate_jwt_token, SubscriptionTier

# Configure logger
logger = logging.getLogger(__name__)

# Load environment variables
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
ENABLE_KEY_MANAGEMENT = os.getenv("ENABLE_KEY_MANAGEMENT", "false").lower() == "true"

# Create router
router = APIRouter()

# Define request and response models
class KeyGenerationRequest(BaseModel):
    user_id: str
    tier: str
    token_type: str = "api_key"  # "api_key" or "jwt"

class KeyResponse(BaseModel):
    user_id: str
    tier: str
    token: str
    token_type: str

def verify_admin_key(admin_key: Optional[str] = Header(None)) -> bool:
    """Verify that the request is from an admin."""
    if not ADMIN_API_KEY:
        logger.warning("Admin API key not configured")
        return False
    
    if not admin_key:
        raise HTTPException(status_code=401, detail="Admin API key missing")
    
    if admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    
    return True

@router.post("/admin/keys", response_model=KeyResponse)
async def generate_key(request: KeyGenerationRequest, is_admin: bool = Depends(verify_admin_key)):
    """Generate an API key or JWT token for a user."""
    if not ENABLE_KEY_MANAGEMENT:
        logger.warning("Key management is disabled")
        raise HTTPException(status_code=403, detail="Key management is disabled")
    
    # Validate the tier
    try:
        tier = SubscriptionTier(request.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {request.tier}. Valid tiers are: {[t.value for t in SubscriptionTier]}")
    
    # Generate the token
    if request.token_type == "api_key":
        token = generate_api_key(request.user_id, tier)
    elif request.token_type == "jwt":
        token = generate_jwt_token(request.user_id, tier)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid token type: {request.token_type}. Valid types are: api_key, jwt")
    
    # Log the key generation
    logger.info(f"Generated {request.token_type} for user {request.user_id} with tier {tier.value}")
    
    # Return the response
    return KeyResponse(
        user_id=request.user_id,
        tier=tier.value,
        token=token,
        token_type=request.token_type
    )

@router.get("/admin/keys/test")
async def test_key_management(is_admin: bool = Depends(verify_admin_key)):
    """Test the key management API."""
    return {"status": "ok", "message": "Key management API is working"}
