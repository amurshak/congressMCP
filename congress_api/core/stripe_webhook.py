# stripe_webhook.py
import os
import json
import logging
import hmac
import hashlib
import time
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse

from .auth import generate_api_key, generate_jwt_token
from .user_service import UserService

# Configure logger
logger = logging.getLogger(__name__)

# Load environment variables
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
ENABLE_STRIPE = os.getenv("ENABLE_STRIPE", "true").lower() == "true"  # Default to true for testing
ENABLE_DATABASE = os.getenv("ENABLE_DATABASE", "true").lower() == "true"

# Create router
router = APIRouter()

# Initialize user service
user_service = UserService()

# Price ID mapping is handled by UserService._get_tier_from_price_id() 
# which reads from environment variables

def verify_stripe_signature(payload: bytes, sig_header: str) -> bool:
    """Verify that the webhook came from Stripe."""
    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("Stripe webhook secret not configured - skipping signature verification")
        return True  # Allow through for testing when secret not set
    
    try:
        # Extract timestamp and signature
        parts = sig_header.split(',')
        timestamp = next((p.split('=')[1] for p in parts if p.startswith('t=')), None)
        signature = next((p.split('=')[1] for p in parts if p.startswith('v1=')), None)
        
        if not timestamp or not signature:
            logger.error("Invalid Stripe signature header format")
            return False
        
        # Check timestamp (prevent replay attacks)
        current_time = int(time.time())
        if abs(current_time - int(timestamp)) > 300:  # 5 minutes tolerance
            logger.error("Stripe webhook timestamp too old")
            return False
        
        # Create the expected signature
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected_sig = hmac.new(
            STRIPE_WEBHOOK_SECRET.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(expected_sig, signature)
    except Exception as e:
        logger.error(f"Error verifying Stripe signature: {str(e)}")
        return False

@router.post("/webhook")  # Changed from "/webhook/stripe" to "/webhook"
async def stripe_webhook(
    request: Request, 
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature")
):
    """Handle Stripe webhook events."""
    logger.info("Received Stripe webhook request")
    
    try:
        if not ENABLE_STRIPE:
            logger.warning("Stripe integration is disabled")
            return JSONResponse({"status": "disabled"})
        
        # Read the request body
        payload = await request.body()
        logger.info(f"Webhook payload size: {len(payload)} bytes")
        
        # Log headers for debugging
        logger.debug(f"Request headers: {dict(request.headers)}")
        
        if not stripe_signature:
            logger.error("Stripe signature header missing")
            raise HTTPException(status_code=400, detail="Stripe signature header missing")
        
        logger.info("Verifying Stripe signature...")
        
        # Verify the signature
        if not verify_stripe_signature(payload, stripe_signature):
            logger.error("Invalid Stripe signature")
            raise HTTPException(status_code=400, detail="Invalid Stripe signature")
        
        logger.info("Stripe signature verified successfully")
        
        # Parse the event
        try:
            event = json.loads(payload)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON payload: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        # Use the user service to handle events
        if ENABLE_DATABASE:
            event_type = event.get("type")
            event_data = event.get("data", {}).get("object", {})
            
            result = await user_service.handle_stripe_webhook(event_type, event_data)
            if result:
                logger.info(f"Successfully processed {event_type} event")
                return JSONResponse({"status": "success", "processed": True})
            else:
                logger.warning(f"Event {event_type} was not processed")
                return JSONResponse({"status": "success", "processed": False})
        else:
            # Fallback to simple event handling
            event_type = event.get("type")
            logger.info(f"Processing Stripe event: {event_type} (database disabled)")
            return JSONResponse({"status": "success", "processed": False, "message": "Database disabled"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/test")
async def test_stripe_webhook():
    """Test endpoint to verify the Stripe webhook setup."""
    return JSONResponse({
        "status": "ok", 
        "message": "Stripe webhook endpoint is working",
        "stripe_enabled": ENABLE_STRIPE,
        "webhook_secret_configured": bool(STRIPE_WEBHOOK_SECRET)
    })