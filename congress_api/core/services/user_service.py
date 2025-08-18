# user_service.py - High-level user management service
import logging
import os
from typing import Optional, Tuple, Dict, Any
from ..database import db_client, User
from ..auth.auth import SubscriptionTier
from .email_service import email_service

logger = logging.getLogger(__name__)

class UserService:
    """High-level service for user management operations"""
    
    def __init__(self):
        self.db = db_client

    async def create_user_with_api_key(self, email: str, 
                                     stripe_customer_id: Optional[str] = None,
                                     tier: SubscriptionTier = SubscriptionTier.FREE) -> Tuple[Optional[User], Optional[str]]:
        """Create a new user and generate their first API key"""
        try:
            # Create the user
            user = await self.db.create_user(email, stripe_customer_id, tier)
            if not user:
                logger.error(f"Failed to create user: {email}")
                return None, None
            
            # Generate API key
            api_key = await self.db.create_api_key(user.id, tier)
            if not api_key:
                logger.error(f"Failed to create API key for user: {user.id}")
                return user, None
                
            logger.info(f"Created user {email} with API key and tier {tier.value}")
            
            # Send welcome email (without API key - shown in frontend)
            email_sent = await email_service.send_welcome_email(
                email=user.email,
                api_key=None,  # Don't include API key in email
                tier=tier
            )
            if email_sent:
                logger.info(f"Welcome email sent successfully to {user.email}")
            else:
                logger.warning(f"Failed to send welcome email to {user.email}")
            
            return user, api_key
            
        except Exception as e:
            logger.error(f"Error creating user with API key: {e}")
            return None, None

    async def register_or_send_magic_link(self, email: str) -> Dict[str, Any]:
        """
        Smart registration: handle both new users and existing users
        - New users: create account + send registration magic link
        - Existing users: send key management magic link
        """
        try:
            # Check if user already exists
            existing_user = await self.db.get_user_by_email(email)
            
            if existing_user:
                # Existing user - send key management magic link
                logger.info(f"Existing user {email} requesting access - sending key management magic link")
                from ..auth.magic_link_service import get_magic_link_service
                magic_link_service = get_magic_link_service()
                magic_result = await magic_link_service.request_magic_link(email, purpose="key_management")
                
                if magic_result.get("success"):
                    return {
                        "success": True,
                        "message": "Check your email for a magic link to access your API key.",
                        "user_exists": True
                    }
                else:
                    return {
                        "success": False,
                        "message": "Failed to send magic link. Please try again.",
                        "user_exists": True
                    }
            else:
                # New user - create account without API key + send registration magic link
                # First get or create Stripe customer to avoid duplicates
                stripe_customer_id = await self._get_or_create_stripe_customer(email)
                user = await self.create_user_for_registration(email, stripe_customer_id, SubscriptionTier.FREE)
                if not user:
                    return {
                        "success": False,
                        "message": "Failed to create account. Please try again."
                    }
                
                # Send registration magic link
                from ..auth.magic_link_service import get_magic_link_service
                magic_link_service = get_magic_link_service()
                magic_result = await magic_link_service.request_magic_link(email, purpose="registration")
                
                if magic_result.get("success"):
                    return {
                        "success": True,
                        "message": "Registration successful! Check your email for a verification link to get your API key.",
                        "user_id": user.id,
                        "tier": user.subscription_tier,
                        "verification_required": True
                    }
                else:
                    return {
                        "success": False,
                        "message": "Registration created but verification email failed. Please try requesting a new magic link.",
                        "user_created": True
                    }
                    
        except Exception as e:
            logger.error(f"Error in register_or_send_magic_link: {e}")
            return {
                "success": False,
                "message": "An unexpected error occurred. Please try again."
            }

    async def _get_or_create_stripe_customer(self, email: str) -> Optional[str]:
        """
        Get existing Stripe customer or create new one to avoid duplicates
        """
        try:
            # Check if Stripe is enabled
            enable_stripe = os.getenv("ENABLE_STRIPE", "true").lower() == "true"
            if not enable_stripe:
                logger.info("Stripe is disabled, skipping customer creation")
                return None
                
            import stripe
            stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
            
            if not stripe.api_key:
                logger.warning("❌ Stripe API key not configured, creating user without Stripe customer")
                return None
                
            # First, check for existing Stripe customer with this email
            logger.info(f"Checking for existing Stripe customer with email {email}...")
            customers = stripe.Customer.list(email=email, limit=1)
            
            if customers.data:
                existing_customer = customers.data[0]
                logger.info(f"✅ Found existing Stripe customer {existing_customer.id} for {email}")
                return existing_customer.id
            
            # No existing customer found, create new one
            logger.info(f"Creating new Stripe customer for {email}...")
            customer = stripe.Customer.create(
                email=email,
                metadata={
                    'tier': 'FREE',
                    'source': 'free_signup',
                    'created_via': 'congressional_mcp_frontend'
                }
            )
            logger.info(f"✅ Created new Stripe customer {customer.id} for {email}")
            return customer.id
            
        except Exception as e:
            logger.error(f"❌ Failed to get or create Stripe customer for {email}: {str(e)}")
            # Continue without Stripe customer - this is graceful degradation
            return None

    async def create_user_for_registration(self, email: str, 
                                         stripe_customer_id: Optional[str] = None,
                                         tier: SubscriptionTier = SubscriptionTier.FREE) -> Optional[User]:
        """Create a new user without API key (for magic link registration flow)"""
        try:
            # Create the user (no API key yet)
            user = await self.db.create_user(email, stripe_customer_id, tier)
            if not user:
                logger.error(f"Failed to create user: {email}")
                return None
                
            logger.info(f"Created user {email} with tier {tier.value} (API key pending verification)")
            return user
            
        except Exception as e:
            logger.error(f"Error creating user for registration: {e}")
            return None

    async def handle_stripe_customer_created(self, stripe_customer_id: str, 
                                           email: str) -> Tuple[Optional[User], Optional[str]]:
        """Handle Stripe customer creation - create user with FREE tier"""
        logger.info(f"Processing Stripe customer creation: {email}")
        
        # Check if user already exists
        existing_user = await self.db.get_user_by_email(email)
        if existing_user:
            logger.info(f"User {email} already exists, updating Stripe customer ID")
            # Update the existing user with Stripe customer ID if not set
            if not existing_user.stripe_customer_id:
                success = await self.db.update_stripe_customer_id(existing_user.id, stripe_customer_id)
                if success:
                    logger.info(f"Updated Stripe customer ID for existing user {email}")
                else:
                    logger.error(f"Failed to update Stripe customer ID for user {email}")
            return existing_user, None
        
        # Create new user with FREE tier
        return await self.create_user_with_api_key(email, stripe_customer_id, SubscriptionTier.FREE)

    async def handle_stripe_subscription_created(self, stripe_customer_id: str, 
                                                stripe_price_id: str) -> bool:
        """Handle Stripe subscription creation - create user if needed, then upgrade tier"""
        logger.info(f"Processing subscription creation for customer: {stripe_customer_id}")
        
        # Check if this is a CongressMCP price ID
        tier = self._get_tier_from_price_id(stripe_price_id)
        if not tier:
            logger.info(f"Skipping subscription for unknown price ID: {stripe_price_id}")
            return True  # Not our price ID, ignore
        
        # Get user by Stripe customer ID
        user = await self.db.get_user_by_stripe_customer_id(stripe_customer_id)
        if not user:
            # User doesn't exist - this is likely a Pro customer created via payment link
            # Get customer email from Stripe and create CongressMCP user
            logger.info(f"User not found for Stripe customer {stripe_customer_id}, creating CongressMCP user...")
            
            try:
                import stripe
                stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
                customer = stripe.Customer.retrieve(stripe_customer_id)
                email = customer.email
                
                if not email:
                    logger.error(f"No email found for Stripe customer: {stripe_customer_id}")
                    return False
                
                logger.info(f"Creating CongressMCP user for Pro customer: {email}")
                # Create user with Pro tier directly
                user, api_key = await self.create_user_with_api_key(email, stripe_customer_id, tier)
                if not user:
                    logger.error(f"Failed to create CongressMCP user for Pro customer: {email}")
                    return False
                    
                logger.info(f"Successfully created CongressMCP user {email} with Pro tier")
                return True  # User created with correct tier, no need to upgrade
                
            except Exception as e:
                logger.error(f"Error creating user for Pro subscription: {e}")
                return False
        
        # Map Stripe price ID to subscription tier
        tier = self._get_tier_from_price_id(stripe_price_id)
        if not tier:
            logger.error(f"Unknown price ID: {stripe_price_id}")
            return False
        
        # Update user tier
        success = await self.db.update_user_tier(user.id, tier)
        if success:
            logger.info(f"Upgraded user {user.email} to {tier.value}")
            
            # Deactivate existing API keys before creating new one
            await self.db.deactivate_user_api_keys(user.id)
            
            # Generate new API key with updated tier
            new_api_key = await self.db.create_api_key(user.id, tier)
            if new_api_key:
                logger.info(f"Generated new API key for upgraded user {user.email}")
                
                # Send upgrade email with new API key
                email_sent = await email_service.send_upgrade_email(
                    email=user.email,
                    new_api_key=new_api_key,
                    new_tier=tier
                )
                if email_sent:
                    logger.info(f"Upgrade email sent successfully to {user.email}")
                else:
                    logger.warning(f"Failed to send upgrade email to {user.email}")
                
        return success

    async def handle_stripe_subscription_updated(self, stripe_customer_id: str, 
                                                stripe_price_id: str,
                                                subscription_status: str) -> bool:
        """Handle Stripe subscription updates"""
        logger.info(f"Processing subscription update for customer: {stripe_customer_id}")
        
        user = await self.db.get_user_by_stripe_customer_id(stripe_customer_id)
        if not user:
            logger.error(f"User not found for Stripe customer: {stripe_customer_id}")
            return False
        
        if subscription_status in ['active', 'trialing']:
            # Active subscription - ensure user has correct tier
            tier = self._get_tier_from_price_id(stripe_price_id)
            if tier and tier != user.subscription_tier:
                return await self.db.update_user_tier(user.id, tier)
        elif subscription_status in ['canceled', 'unpaid', 'past_due']:
            # Downgrade to FREE tier
            return await self.db.update_user_tier(user.id, SubscriptionTier.FREE)
        
        return True

    async def handle_stripe_subscription_deleted(self, stripe_customer_id: str) -> bool:
        """Handle Stripe subscription cancellation - downgrade to FREE"""
        logger.info(f"Processing subscription deletion for customer: {stripe_customer_id}")
        
        user = await self.db.get_user_by_stripe_customer_id(stripe_customer_id)
        if not user:
            logger.error(f"User not found for Stripe customer: {stripe_customer_id}")
            return False
        
        # Downgrade to FREE tier
        success = await self.db.update_user_tier(user.id, SubscriptionTier.FREE)
        if success:
            logger.info(f"Downgraded user {user.email} to FREE tier")
        
        return success

    async def handle_invoice_payment_failed(self, stripe_customer_id: str) -> bool:
        """Handle failed payment - notify user and start grace period"""
        logger.info(f"Processing payment failure for customer: {stripe_customer_id}")
        
        user = await self.db.get_user_by_stripe_customer_id(stripe_customer_id)
        if not user:
            logger.error(f"User not found for Stripe customer: {stripe_customer_id}")
            return False
        
        # Send payment failed notification email
        email_sent = await email_service.send_payment_failed_email(
            email=user.email,
            tier=user.subscription_tier
        )
        if email_sent:
            logger.info(f"Payment failed email sent to {user.email}")
        else:
            logger.warning(f"Failed to send payment failed email to {user.email}")
        
        # Note: Don't downgrade immediately - Stripe will retry
        # Downgrade will happen on subscription.updated with status 'past_due' or 'canceled'
        return True

    async def handle_invoice_payment_succeeded(self, invoice_data: dict) -> bool:
        """Handle successful payment - confirm subscription active"""
        logger.info(f"Processing successful payment for invoice: {invoice_data.get('id')}")
        
        stripe_customer_id = invoice_data.get("customer")
        user = await self.db.get_user_by_stripe_customer_id(stripe_customer_id)
        if not user:
            logger.error(f"User not found for Stripe customer: {stripe_customer_id}")
            return False
        
        # Send payment success notification if needed
        logger.info(f"Payment succeeded for user {user.email}")
        return True

    async def handle_customer_deleted(self, stripe_customer_id: str) -> bool:
        """Handle customer deletion - deactivate user account"""
        logger.info(f"Processing customer deletion for customer: {stripe_customer_id}")
        
        user = await self.db.get_user_by_stripe_customer_id(stripe_customer_id)
        if not user:
            logger.error(f"User not found for Stripe customer: {stripe_customer_id}")
            return False
        
        # Deactivate user account
        success = await self.db.deactivate_user(user.id)
        if success:
            logger.info(f"Deactivated user account for {user.email}")
        else:
            logger.error(f"Failed to deactivate user account for {user.email}")
        
        return success

    def _get_tier_from_price_id(self, price_id: str) -> Optional[SubscriptionTier]:
        """Map Stripe price ID to subscription tier"""
        # Get price IDs from environment variables
        stripe_pro_monthly_price = os.getenv("STRIPE_PRICE_PRO_MONTHLY")
        stripe_pro_annual_price = os.getenv("STRIPE_PRICE_PRO_ANNUAL")
        
        # Map price IDs to tiers
        if price_id == stripe_pro_monthly_price:
            return SubscriptionTier.PRO
        elif price_id == stripe_pro_annual_price:
            return SubscriptionTier.PRO
        else:
            logger.warning(f"Unknown price ID: {price_id}, defaulting to FREE")
            return SubscriptionTier.FREE

    async def validate_api_key_with_features(self, api_key: str, 
                                           feature: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Validate API key and check feature access"""
        # Validate the API key
        key_info = await self.db.validate_api_key(api_key)
        if not key_info:
            return False, None, "Invalid API key"
        
        # Check if user is active
        if not key_info["is_active"]:
            return False, None, "User account is inactive"
        
        # Check feature access based on tier
        tier = key_info["tier"]
        if not self._check_feature_access(feature, tier):
            return False, key_info, f"Feature '{feature}' not available for {tier.value} tier"
        
        # Check rate limits
        user_id = key_info["user_id"]
        daily_usage = await self.db.get_daily_usage(user_id)
        rate_limit = self._get_rate_limit(tier)
        
        if daily_usage >= rate_limit:
            return False, key_info, f"Daily rate limit ({rate_limit}) exceeded"
        
        return True, key_info, "Valid"

    def _check_feature_access(self, feature: str, tier: SubscriptionTier) -> bool:
        """Check if a tier has access to a specific feature"""
        from ..auth.auth import TIER_CONFIG
        
        tier_features = TIER_CONFIG.get(tier, {}).get("features", [])
        return feature in tier_features

    def _get_rate_limit(self, tier: SubscriptionTier) -> int:
        """Get rate limit for a subscription tier"""
        from ..auth.auth import TIER_CONFIG
        
        return TIER_CONFIG.get(tier, {}).get("rate_limit", 100)

    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics and usage info"""
        if not self.db.is_available():
            return {"error": "Database not available"}
        
        try:
            daily_usage = await self.db.get_daily_usage(user_id)
            
            # Get user info
            # TODO: Add method to get user by ID
            
            return {
                "daily_usage": daily_usage,
                "daily_limit": "Unknown",  # Would need user tier info
                "usage_percentage": 0
            }
            
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {"error": str(e)}


# Global user service instance
user_service = UserService()

# Helper functions for easy access
async def create_user_with_api_key(email: str, stripe_customer_id: Optional[str] = None) -> Tuple[Optional[User], Optional[str]]:
    """Create user with API key"""
    return await user_service.create_user_with_api_key(email, stripe_customer_id)

async def register_or_send_magic_link(email: str, stripe_customer_id: Optional[str] = None) -> Dict[str, Any]:
    """Smart registration: handle both new users and existing users"""
    return await user_service.register_or_send_magic_link(email)

async def create_user_for_registration(email: str, stripe_customer_id: Optional[str] = None) -> Optional[User]:
    """Create user without API key for magic link registration flow"""
    return await user_service.create_user_for_registration(email, stripe_customer_id)

async def validate_api_key_with_features(api_key: str, feature: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Validate API key and check feature access"""
    return await user_service.validate_api_key_with_features(api_key, feature)

async def handle_stripe_webhook(event_type: str, data: Dict[str, Any]) -> bool:
    """Handle Stripe webhook events"""
    try:
        if event_type == "customer.created":
            customer_id = data["id"]
            email = data["email"]
            metadata = data.get("metadata", {})
            
            # Only process customers created by CongressMCP
            congress_indicators = [
                metadata.get("created_via") == "congressional_mcp_frontend",
                metadata.get("source") == "free_signup",
                "congressional" in metadata.get("created_via", "").lower(),
                "congressmcp" in metadata.get("source", "").lower()
            ]
            
            if not any(congress_indicators):
                logger.info(f"Skipping customer {customer_id} ({email}) - not created by CongressMCP (metadata: {metadata})")
                return True  # Return success but don't process
            
            logger.info(f"Processing CongressMCP customer {customer_id} ({email}) with metadata: {metadata}")
            user, api_key = await user_service.handle_stripe_customer_created(customer_id, email)
            return user is not None
            
        elif event_type == "customer.subscription.created":
            subscription = data
            customer_id = subscription["customer"]
            price_id = subscription["items"]["data"][0]["price"]["id"]
            return await user_service.handle_stripe_subscription_created(customer_id, price_id)
            
        elif event_type == "customer.subscription.updated":
            subscription = data
            customer_id = subscription["customer"]
            price_id = subscription["items"]["data"][0]["price"]["id"]
            status = subscription["status"]
            return await user_service.handle_stripe_subscription_updated(customer_id, price_id, status)
            
        elif event_type == "customer.subscription.deleted":
            subscription = data
            customer_id = subscription["customer"]
            return await user_service.handle_stripe_subscription_deleted(customer_id)
            
        elif event_type == "invoice.payment_failed":
            invoice = data
            customer_id = invoice["customer"]
            return await user_service.handle_invoice_payment_failed(customer_id)
            
        elif event_type == "invoice.payment_succeeded":
            invoice = data
            return await user_service.handle_invoice_payment_succeeded(invoice)
            
        elif event_type == "customer.deleted":
            customer_id = data["id"]
            return await user_service.handle_customer_deleted(customer_id)
            
        else:
            logger.info(f"Unhandled webhook event: {event_type}")
            return True
            
    except Exception as e:
        logger.error(f"Error handling Stripe webhook {event_type}: {e}")
        return False
