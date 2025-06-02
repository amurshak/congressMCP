# user_service.py - High-level user management service
import logging
from typing import Optional, Tuple, Dict, Any
from .database import db_client, User
from .auth import SubscriptionTier
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
            
            # Send welcome email with API key
            email_sent = await email_service.send_welcome_email(
                email=user.email,
                api_key=api_key,
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
                # TODO: Add method to update stripe_customer_id
                pass
            return existing_user, None
        
        # Create new user with FREE tier
        return await self.create_user_with_api_key(email, stripe_customer_id, SubscriptionTier.FREE)

    async def handle_stripe_subscription_created(self, stripe_customer_id: str, 
                                                stripe_price_id: str) -> bool:
        """Handle Stripe subscription creation - upgrade user tier"""
        logger.info(f"Processing subscription creation for customer: {stripe_customer_id}")
        
        # Get user by Stripe customer ID
        user = await self.db.get_user_by_stripe_customer_id(stripe_customer_id)
        if not user:
            logger.error(f"User not found for Stripe customer: {stripe_customer_id}")
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

    def _get_tier_from_price_id(self, price_id: str) -> Optional[SubscriptionTier]:
        """Map Stripe price ID to subscription tier"""
        # Actual Stripe price IDs from CLI setup
        price_tier_mapping = {
            "price_1RVWCJCrAoNgWc5EZbpHinj9": SubscriptionTier.PRO,  # Pro Monthly $29/month
            "price_1RVWCQCrAoNgWc5EodIUwBDv": SubscriptionTier.PRO,  # Pro Annual $299/year
        }
        
        tier = price_tier_mapping.get(price_id)
        if not tier:
            logger.warning(f"Unknown price ID: {price_id}, defaulting to FREE")
            return SubscriptionTier.FREE
            
        return tier

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
        from .auth import TIER_CONFIG
        
        tier_features = TIER_CONFIG.get(tier, {}).get("features", [])
        return feature in tier_features

    def _get_rate_limit(self, tier: SubscriptionTier) -> int:
        """Get rate limit for a subscription tier"""
        from .auth import TIER_CONFIG
        
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

async def validate_api_key_with_features(api_key: str, feature: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Validate API key and check feature access"""
    return await user_service.validate_api_key_with_features(api_key, feature)

async def handle_stripe_webhook(event_type: str, data: Dict[str, Any]) -> bool:
    """Handle Stripe webhook events"""
    try:
        if event_type == "customer.created":
            customer_id = data["id"]
            email = data["email"]
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
            
        else:
            logger.info(f"Unhandled webhook event: {event_type}")
            return True
            
    except Exception as e:
        logger.error(f"Error handling Stripe webhook {event_type}: {e}")
        return False
