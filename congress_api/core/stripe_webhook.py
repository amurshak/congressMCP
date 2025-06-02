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

from .auth import generate_api_key, generate_jwt_token, SubscriptionTier

# Configure logger
logger = logging.getLogger(__name__)

# Load environment variables
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
ENABLE_STRIPE = os.getenv("ENABLE_STRIPE", "true").lower() == "true"  # Default to true for testing

# Create router
router = APIRouter()

# Map Stripe price IDs to subscription tiers
STRIPE_PRICE_TO_TIER = {
    # These would be your actual Stripe price IDs
    "price_free": SubscriptionTier.FREE,
    "price_pro": SubscriptionTier.PRO,
    "price_enterprise": SubscriptionTier.ENTERPRISE
}

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

def get_subscription_tier(price_id: str) -> SubscriptionTier:
    """Get the subscription tier for a Stripe price ID."""
    return STRIPE_PRICE_TO_TIER.get(price_id, SubscriptionTier.FREE)

def update_user_tier(user_id: str, tier: SubscriptionTier) -> Dict[str, Any]:
    """Update a user's subscription tier and generate new API keys."""
    # In a production environment, this would update a database record
    # For now, we'll just generate new keys
    
    # Generate API key
    api_key = generate_api_key(user_id, tier)
    
    # Generate JWT token
    jwt_token = generate_jwt_token(user_id, tier)
    
    # In a production environment, you would store these in a database
    # and associate them with the user's account
    
    return {
        "user_id": user_id,
        "tier": tier.value,
        "api_key": api_key,
        "jwt_token": jwt_token
    }

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
        
        # Handle the event
        event_type = event.get("type")
        logger.info(f"Processing Stripe event: {event_type}")
        
        if event_type == "checkout.session.completed":
            # Handle successful checkout
            session = event.get("data", {}).get("object", {})
            customer_id = session.get("customer")
            subscription_id = session.get("subscription")
            
            if not customer_id or not subscription_id:
                logger.error("Missing customer or subscription ID in checkout session")
                return JSONResponse({"status": "error", "message": "Missing customer or subscription ID"})
            
            # In a production environment, you would look up the subscription details
            # to determine the price ID and subscription tier
            # For now, we'll use a placeholder
            price_id = "price_pro"  # Placeholder
            tier = get_subscription_tier(price_id)
            
            # Update the user's tier and generate new API keys
            user_data = update_user_tier(customer_id, tier)
            
            logger.info(f"User {customer_id} subscribed to {tier.value} tier")
            
            return JSONResponse({"status": "success", "user": user_data})
        
        elif event_type == "customer.subscription.updated":
            # Handle subscription update
            subscription = event.get("data", {}).get("object", {})
            customer_id = subscription.get("customer")
            
            if not customer_id:
                logger.error("Missing customer ID in subscription update")
                return JSONResponse({"status": "error", "message": "Missing customer ID"})
            
            # Get the current price ID
            items = subscription.get("items", {}).get("data", [])
            if not items:
                logger.error("No items in subscription update")
                return JSONResponse({"status": "error", "message": "No items in subscription"})
            
            price_id = items[0].get("price", {}).get("id")
            if not price_id:
                logger.error("Missing price ID in subscription update")
                return JSONResponse({"status": "error", "message": "Missing price ID"})
            
            # Get the subscription tier
            tier = get_subscription_tier(price_id)
            
            # Update the user's tier and generate new API keys
            user_data = update_user_tier(customer_id, tier)
            
            logger.info(f"User {customer_id} updated subscription to {tier.value} tier")
            
            return JSONResponse({"status": "success", "user": user_data})
        
        elif event_type == "customer.subscription.deleted":
            # Handle subscription cancellation
            subscription = event.get("data", {}).get("object", {})
            customer_id = subscription.get("customer")
            
            if not customer_id:
                logger.error("Missing customer ID in subscription deletion")
                return JSONResponse({"status": "error", "message": "Missing customer ID"})
            
            # Downgrade the user to the free tier
            tier = SubscriptionTier.FREE
            
            # Update the user's tier and generate new API keys
            user_data = update_user_tier(customer_id, tier)
            
            logger.info(f"User {customer_id} subscription canceled, downgraded to {tier.value} tier")
            
            return JSONResponse({"status": "success", "user": user_data})
        
        elif event_type == "customer.subscription.created":
            # Handle new subscription creation
            subscription = event.get("data", {}).get("object", {})
            customer_id = subscription.get("customer")
            
            if not customer_id:
                logger.error("Missing customer ID in subscription creation")
                return JSONResponse({"status": "error", "message": "Missing customer ID"})
            
            # Get the price ID from subscription items
            items = subscription.get("items", {}).get("data", [])
            if not items:
                logger.error("No items in subscription creation")
                return JSONResponse({"status": "error", "message": "No items in subscription"})
            
            price_id = items[0].get("price", {}).get("id")
            if not price_id:
                logger.error("Missing price ID in subscription creation")
                return JSONResponse({"status": "error", "message": "Missing price ID"})
            
            # Get the subscription tier
            tier = get_subscription_tier(price_id)
            
            # Update the user's tier and generate new API keys
            user_data = update_user_tier(customer_id, tier)
            
            logger.info(f"User {customer_id} created new subscription for {tier.value} tier")
            
            return JSONResponse({"status": "success", "user": user_data})
        
        elif event_type == "customer.subscription.trial_will_end":
            # Handle trial expiration warning (3 days before)
            subscription = event.get("data", {}).get("object", {})
            customer_id = subscription.get("customer")
            trial_end = subscription.get("trial_end")
            
            if not customer_id:
                logger.error("Missing customer ID in trial will end event")
                return JSONResponse({"status": "error", "message": "Missing customer ID"})
            
            logger.info(f"User {customer_id} trial will end at {trial_end}")
            
            # You can add email notification logic here
            # For now, just log the event
            
            return JSONResponse({"status": "success", "message": "Trial expiration notification processed"})
        
        elif event_type == "invoice.payment_succeeded":
            # Handle successful invoice payment
            invoice = event.get("data", {}).get("object", {})
            customer_id = invoice.get("customer")
            subscription_id = invoice.get("subscription")
            
            if not customer_id:
                logger.error("Missing customer ID in payment succeeded event")
                return JSONResponse({"status": "error", "message": "Missing customer ID"})
            
            logger.info(f"Payment succeeded for user {customer_id}, subscription {subscription_id}")
            
            # Ensure user maintains their current tier access
            # The subscription.updated event will handle tier changes if needed
            
            return JSONResponse({"status": "success", "message": "Payment success processed"})
        
        elif event_type == "invoice.payment_failed":
            # Handle failed invoice payment
            invoice = event.get("data", {}).get("object", {})
            customer_id = invoice.get("customer")
            subscription_id = invoice.get("subscription")
            
            if not customer_id:
                logger.error("Missing customer ID in payment failed event")
                return JSONResponse({"status": "error", "message": "Missing customer ID"})
            
            logger.warning(f"Payment failed for user {customer_id}, subscription {subscription_id}")
            
            # You may want to implement dunning management here
            # For now, log the failure and let Stripe handle retries
            # Consider downgrading access after multiple failures
            
            return JSONResponse({"status": "success", "message": "Payment failure processed"})
        
        elif event_type == "customer.created":
            # Handle new customer creation
            customer = event.get("data", {}).get("object", {})
            customer_id = customer.get("id")
            email = customer.get("email")
            
            if not customer_id:
                logger.error("Missing customer ID in customer creation")
                return JSONResponse({"status": "error", "message": "Missing customer ID"})
            
            # Set up new customer with free tier by default
            tier = SubscriptionTier.FREE
            user_data = update_user_tier(customer_id, tier)
            
            logger.info(f"New customer {customer_id} ({email}) created with {tier.value} tier")
            
            return JSONResponse({"status": "success", "user": user_data})
        
        # Return a 200 response for other event types
        logger.info(f"Received unhandled event type: {event_type}")
        return JSONResponse({"status": "received", "type": event_type})
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in webhook handler: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/test")
async def test_stripe_webhook():
    """Test endpoint to verify the Stripe webhook setup."""
    return JSONResponse({
        "status": "ok", 
        "message": "Stripe webhook endpoint is working",
        "stripe_enabled": ENABLE_STRIPE,
        "webhook_secret_configured": bool(STRIPE_WEBHOOK_SECRET)
    })