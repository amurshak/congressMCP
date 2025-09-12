# database.py - Supabase database integration for user management and authentication
import os
import logging
import hashlib
import secrets
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
from dateutil import parser as dateutil_parser
from supabase import create_client, Client
from .api_config import load_environment_config

# Configure logger
logger = logging.getLogger(__name__)

# Load environment configuration
ENV = load_environment_config()

# Create a dedicated thread pool for database operations
# This prevents exhaustion of the default thread pool
_db_thread_pool = ThreadPoolExecutor(max_workers=10, thread_name_prefix="db_pool")

# Setup cleanup for thread pool
import atexit

def _cleanup_thread_pool():
    """Clean up the database thread pool on shutdown"""
    global _db_thread_pool
    if _db_thread_pool:
        logger.info("Shutting down database thread pool...")
        _db_thread_pool.shutdown(wait=True)
        logger.info("Database thread pool shutdown complete")

atexit.register(_cleanup_thread_pool)

# Subscription tiers (matching auth.py)
class SubscriptionTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

@dataclass
class User:
    """User data model"""
    id: str
    email: str
    stripe_customer_id: Optional[str]
    subscription_tier: SubscriptionTier
    created_at: datetime
    updated_at: datetime
    is_active: bool = True

@dataclass
class ApiKey:
    """API Key data model"""
    id: str
    user_id: str
    key_hash: str
    tier: SubscriptionTier
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool = True
    last_used_at: Optional[datetime] = None

@dataclass
class UsageRecord:
    """Usage tracking data model"""
    id: str
    user_id: str
    date: datetime
    request_count: int
    feature_used: str
    endpoint: str

class SupabaseClient:
    """Supabase database client for user and authentication management"""
    
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")  
        self.supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")
        self.enable_database = os.getenv("ENABLE_DATABASE", "true").lower() == "true"
        
        if not self.enable_database:
            logger.warning("Database is disabled - authentication features will be limited")
            self.client = None
            return
            
        if not all([self.supabase_url, self.supabase_service_key]):
            logger.error("Missing Supabase configuration - database features disabled")
            self.client = None
            return
            
        try:
            # Use service role key for admin operations
            self.client: Client = create_client(self.supabase_url, self.supabase_service_key)
            logger.info("Connected to Supabase database")
        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")
            self.client = None

    def is_available(self) -> bool:
        """Check if database is available"""
        return self.client is not None and self.enable_database

    # User Management Methods
    async def create_user(self, email: str, stripe_customer_id: Optional[str] = None, 
                         tier: SubscriptionTier = SubscriptionTier.FREE) -> Optional[User]:
        """Create a new user"""
        if not self.is_available():
            logger.warning("Database not available - cannot create user")
            return None
            
        try:
            user_data = {
                "email": email,
                "stripe_customer_id": stripe_customer_id,
                "subscription_tier": tier.value,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "is_active": True
            }
            
            def _create_user_sync():
                return self.client.table("users").insert(user_data).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _create_user_sync)
            
            if result.data:
                user_record = result.data[0]
                logger.info(f"Created user: {email} with tier: {tier.value}")
                return User(
                    id=user_record["id"],
                    email=user_record["email"],
                    stripe_customer_id=user_record["stripe_customer_id"],
                    subscription_tier=SubscriptionTier(user_record["subscription_tier"]),
                    created_at=self._parse_datetime(user_record["created_at"]),
                    updated_at=self._parse_datetime(user_record["updated_at"]),
                    is_active=user_record["is_active"]
                )
            return None
            
        except Exception as e:
            logger.error(f"Failed to create user {email}: {e}")
            return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        if not self.is_available():
            return None
            
        try:
            def _get_user_by_email_sync():
                return self.client.table("users").select("*").eq("email", email).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _get_user_by_email_sync)
            
            if result.data:
                user_record = result.data[0]
                return User(
                    id=user_record["id"],
                    email=user_record["email"],
                    stripe_customer_id=user_record["stripe_customer_id"],
                    subscription_tier=SubscriptionTier(user_record["subscription_tier"]),
                    created_at=self._parse_datetime(user_record["created_at"]),
                    updated_at=self._parse_datetime(user_record["updated_at"]),
                    is_active=user_record["is_active"]
                )
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user {email}: {e}")
            return None

    async def get_user_by_stripe_customer_id(self, stripe_customer_id: str) -> Optional[User]:
        """Get user by Stripe customer ID"""
        if not self.is_available():
            return None
            
        try:
            def _get_user_by_stripe_customer_id_sync():
                return self.client.table("users").select("*").eq("stripe_customer_id", stripe_customer_id).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _get_user_by_stripe_customer_id_sync)
            
            if result.data:
                user_record = result.data[0]
                return User(
                    id=user_record["id"],
                    email=user_record["email"],
                    stripe_customer_id=user_record["stripe_customer_id"],
                    subscription_tier=SubscriptionTier(user_record["subscription_tier"]),
                    created_at=self._parse_datetime(user_record["created_at"]),
                    updated_at=self._parse_datetime(user_record["updated_at"]),
                    is_active=user_record["is_active"]
                )
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user by Stripe ID {stripe_customer_id}: {e}")
            return None

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        if not self.is_available():
            return None
            
        try:
            def _get_user_by_id_sync():
                return self.client.table("users").select("*").eq("id", user_id).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _get_user_by_id_sync)
            
            if result.data:
                user_record = result.data[0]
                return User(
                    id=user_record["id"],
                    email=user_record["email"],
                    stripe_customer_id=user_record["stripe_customer_id"],
                    subscription_tier=SubscriptionTier(user_record["subscription_tier"]),
                    created_at=self._parse_datetime(user_record["created_at"]),
                    updated_at=self._parse_datetime(user_record["updated_at"]),
                    is_active=user_record["is_active"]
                )
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user by ID {user_id}: {e}")
            return None

    async def update_user_tier(self, user_id: str, tier: SubscriptionTier) -> bool:
        """Update user subscription tier"""
        if not self.is_available():
            return False
            
        try:
            def _update_user_tier_sync():
                return self.client.table("users").update({"subscription_tier": tier.value, "updated_at": datetime.utcnow().isoformat()}).eq("id", user_id).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _update_user_tier_sync)
            
            success = len(result.data) > 0
            if success:
                logger.info(f"Updated user {user_id} tier to {tier.value}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to update user {user_id} tier: {e}")
            return False

    # Helper Methods
    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse datetime string from Supabase, handling various ISO formats."""
        if not dt_str:
            raise ValueError("Empty datetime string")
            
        # Clean the string of any potential invisible characters
        dt_str = dt_str.strip()
        
        try:
            # Try standard fromisoformat first (works for most cases)
            # Handle Z timezone indicator
            cleaned_str = dt_str.replace('Z', '+00:00')
            return datetime.fromisoformat(cleaned_str)
        except (ValueError, AttributeError) as e:
            logger.debug(f"fromisoformat failed for '{dt_str}': {e}")
            try:
                # Fallback to dateutil parser for more complex formats
                return dateutil_parser.isoparse(dt_str)
            except Exception as e2:
                logger.debug(f"dateutil.isoparse failed for '{dt_str}': {e2}")
                try:
                    # Last resort: try to parse with dateutil's general parser
                    return dateutil_parser.parse(dt_str)
                except Exception as e3:
                    logger.error(f"All datetime parsing methods failed for '{dt_str}': fromisoformat={e}, isoparse={e2}, parse={e3}")
                    raise ValueError(f"Unable to parse datetime string: '{dt_str}'")
    
    # API Key Management Methods
    def _hash_key(self, api_key: str) -> str:
        """Hash an API key for secure storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def _generate_api_key(self, user_id: str, tier: SubscriptionTier) -> str:
        """Generate a new API key"""
        # Format: lawgiver_<tier>_<user_id_prefix>_<random>
        user_prefix = user_id[:8] if len(user_id) >= 8 else user_id
        random_suffix = secrets.token_urlsafe(16)
        return f"lawgiver_{tier.value}_{user_prefix}_{random_suffix}"

    async def create_api_key(self, user_id: str, tier: SubscriptionTier, 
                           expires_days: int = 365) -> Optional[str]:
        """Create a new API key for a user"""
        if not self.is_available():
            return None
            
        try:
            # Generate the API key
            api_key = self._generate_api_key(user_id, tier)
            key_hash = self._hash_key(api_key)
            
            # Calculate expiry date
            expires_at = datetime.utcnow() + timedelta(days=expires_days)
            
            key_data = {
                "user_id": user_id,
                "key_hash": key_hash,
                "tier": tier.value,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": expires_at.isoformat(),
                "is_active": True
            }
            
            def _create_api_key_sync():
                return self.client.table("api_keys").insert(key_data).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _create_api_key_sync)
            
            if result.data:
                logger.info(f"Created API key for user {user_id} with tier {tier.value}")
                return api_key  # Return the unhashed key to give to user
            return None
            
        except Exception as e:
            logger.error(f"Failed to create API key for user {user_id}: {e}")
            return None

    async def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key and return user info"""
        if not self.is_available():
            return None
            
        try:
            key_hash = self._hash_key(api_key)
            
            # Join with users table to get user info
            def _validate_api_key_sync():
                return self.client.table("api_keys").select("*, users(*)").eq("key_hash", key_hash).eq("is_active", True).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _validate_api_key_sync)
            
            if not result.data:
                return None
                
            key_record = result.data[0]
            user_record = key_record["users"]
            
            # Check if key is expired
            if key_record["expires_at"]:
                expires_at = datetime.fromisoformat(key_record["expires_at"])
                now = datetime.now(expires_at.tzinfo) if expires_at.tzinfo else datetime.utcnow()
                if now > expires_at:
                    logger.warning(f"API key expired for user {user_record['id']}")
                    return None
            
            # Update last used timestamp
            await self._update_key_last_used(key_record["id"])
            
            return {
                "user_id": user_record["id"],
                "email": user_record["email"],
                "tier": SubscriptionTier(key_record["tier"]),
                "is_active": user_record["is_active"],
                "valid": True
            }
            
        except Exception as e:
            logger.error(f"Failed to validate API key: {e}")
            return None

    async def _update_key_last_used(self, key_id: str):
        """Update the last used timestamp for an API key"""
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            def _update_key_last_used_sync():
                return self.client.table("api_keys").update({"last_used_at": now}).eq("id", key_id).execute()
            
            await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _update_key_last_used_sync)
        except Exception as e:
            logger.error(f"Failed to update key last used: {e}")

    async def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key"""
        if not self.is_available():
            return False
            
        try:
            key_hash = self._hash_key(api_key)
            
            def _revoke_api_key_sync():
                return self.client.table("api_keys").update({"is_active": False, "updated_at": datetime.utcnow().isoformat()}).eq("key_hash", key_hash).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _revoke_api_key_sync)
            
            success = len(result.data) > 0
            if success:
                logger.info("Revoked API key")
            return success
            
        except Exception as e:
            logger.error(f"Failed to revoke API key: {e}")
            return False

    # Usage Tracking Methods
    async def track_usage(self, user_id: str, feature: str, endpoint: str) -> bool:
        """Track API usage for a user"""
        if not self.is_available():
            return False
            
        try:
            today = datetime.utcnow().date()
            
            # Try to increment existing record for today
            def _track_usage_sync():
                return self.client.table("usage_tracking").select("*").eq("user_id", user_id).eq("date", today.isoformat()).eq("feature", feature).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _track_usage_sync)
            
            if result.data:
                # Update existing record
                existing_record = result.data[0]
                new_count = existing_record["request_count"] + 1
                
                def _update_usage_sync():
                    return self.client.table("usage_tracking").update({"request_count": new_count, "endpoint": endpoint}).eq("id", existing_record["id"]).execute()
                
                await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _update_usage_sync)
            else:
                # Create new record
                usage_data = {
                    "user_id": user_id,
                    "date": today.isoformat(),
                    "request_count": 1,
                    "feature": feature,
                    "endpoint": endpoint
                }
                
                def _create_usage_sync():
                    return self.client.table("usage_tracking").insert(usage_data).execute()
                
                await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _create_usage_sync)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to track usage for user {user_id}: {e}")
            return False

    async def get_daily_usage(self, user_id: str, date: datetime = None) -> int:
        """Get daily usage count for a user"""
        if not self.is_available():
            return 0
            
        try:
            if date is None:
                date = datetime.utcnow().date()
            else:
                date = date.date() if hasattr(date, 'date') else date
                
            def _get_daily_usage_sync():
                return self.client.table("usage_tracking").select("request_count").eq("user_id", user_id).eq("date", date.isoformat()).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _get_daily_usage_sync)
            
            total_requests = sum(record["request_count"] for record in result.data)
            return total_requests
            
        except Exception as e:
            logger.error(f"Failed to get daily usage for user {user_id}: {e}")
            return 0

    async def update_stripe_customer_id(self, user_id: str, stripe_customer_id: str) -> bool:
        """Update user's Stripe customer ID"""
        if not self.is_available():
            return False
            
        try:
            def _update_stripe_customer_id_sync():
                return self.client.table("users").update({
                    "stripe_customer_id": stripe_customer_id,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", user_id).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _update_stripe_customer_id_sync)
            
            success = len(result.data) > 0
            if success:
                logger.info(f"Updated Stripe customer ID for user {user_id}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to update Stripe customer ID for user {user_id}: {e}")
            return False

    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate user account"""
        if not self.is_available():
            return False
            
        try:
            def _deactivate_user_sync():
                return self.client.table("users").update({
                    "is_active": False,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", user_id).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _deactivate_user_sync)
            
            success = len(result.data) > 0
            if success:
                logger.info(f"Deactivated user {user_id}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to deactivate user {user_id}: {e}")
            return False

    # Magic Link Methods
    async def create_magic_link(self, user_id: Optional[str], email: str, token: str, 
                              expires_at: datetime, purpose: str = "key_management") -> Optional[str]:
        """Create a new magic link"""
        if not self.is_available():
            return None
            
        try:
            def _create_magic_link_sync():
                return self.client.table("magic_links").insert({
                    "user_id": user_id,
                    "email": email.lower(),
                    "token": token,
                    "expires_at": expires_at.isoformat(),
                    "purpose": purpose,
                    "is_used": False
                }).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _create_magic_link_sync)
            
            if result.data:
                magic_link_id = result.data[0]["id"]
                logger.info(f"Created magic link {magic_link_id} for {email}")
                return magic_link_id
            return None
            
        except Exception as e:
            logger.error(f"Failed to create magic link for {email}: {e}")
            return None

    async def get_magic_link(self, token: str) -> Optional[Dict[str, Any]]:
        """Get magic link by token"""
        if not self.is_available():
            return None
            
        try:
            def _get_magic_link_sync():
                return self.client.table("magic_links").select("*").eq("token", token).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _get_magic_link_sync)
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.error(f"Failed to get magic link {token}: {e}")
            return None

    async def mark_magic_link_used(self, token: str) -> bool:
        """Mark magic link as used"""
        if not self.is_available():
            return False
            
        try:
            def _mark_magic_link_used_sync():
                return self.client.table("magic_links").update({
                    "is_used": True,
                    "used_at": datetime.utcnow().isoformat()
                }).eq("token", token).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _mark_magic_link_used_sync)
            
            success = len(result.data) > 0
            if success:
                logger.info(f"Marked magic link as used: {token}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to mark magic link as used {token}: {e}")
            return False

    async def delete_magic_link(self, token: str) -> bool:
        """Delete magic link"""
        if not self.is_available():
            return False
            
        try:
            def _delete_magic_link_sync():
                return self.client.table("magic_links").delete().eq("token", token).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _delete_magic_link_sync)
            
            success = len(result.data) > 0
            if success:
                logger.info(f"Deleted magic link: {token}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete magic link {token}: {e}")
            return False

    async def delete_expired_magic_links(self) -> int:
        """Delete all expired magic links"""
        if not self.is_available():
            return 0
            
        try:
            def _delete_expired_magic_links_sync():
                return self.client.table("magic_links").delete().lt("expires_at", datetime.utcnow().isoformat()).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _delete_expired_magic_links_sync)
            
            deleted_count = len(result.data) if result.data else 0
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} expired magic links")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete expired magic links: {e}")
            return 0

    async def delete_expired_magic_links_for_email(self, email: str) -> int:
        """Delete expired magic links for specific email"""
        if not self.is_available():
            return 0
            
        try:
            def _delete_expired_magic_links_for_email_sync():
                return self.client.table("magic_links").delete().eq("email", email.lower()).lt("expires_at", datetime.utcnow().isoformat()).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _delete_expired_magic_links_for_email_sync)
            
            deleted_count = len(result.data) if result.data else 0
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete expired magic links for {email}: {e}")
            return 0

    async def get_active_api_key_for_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get active API key for user"""
        if not self.is_available():
            return None
            
        try:
            def _get_active_api_key_sync():
                return self.client.table("api_keys").select("*").eq("user_id", user_id).eq("is_active", True).order("created_at", desc=True).limit(1).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _get_active_api_key_sync)
            
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.error(f"Failed to get active API key for user {user_id}: {e}")
            return None

    async def deactivate_user_api_keys(self, user_id: str) -> bool:
        """Deactivate all API keys for user"""
        if not self.is_available():
            return False
            
        try:
            def _deactivate_user_api_keys_sync():
                return self.client.table("api_keys").update({
                    "is_active": False
                }).eq("user_id", user_id).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _deactivate_user_api_keys_sync)
            
            success = len(result.data) > 0
            if success:
                logger.info(f"Deactivated API keys for user {user_id}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to deactivate API keys for user {user_id}: {e}")
            return False

    async def get_monthly_usage(self, user_id: str) -> int:
        """Get monthly usage count for a user"""
        if not self.is_available():
            return 0
            
        try:
            # Get current month usage - use UTC consistently
            current_month = datetime.utcnow().replace(day=1).date()
            
            def _get_monthly_usage_sync():
                return self.client.table("usage_tracking").select("request_count").eq("user_id", user_id).gte("date", current_month.isoformat()).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(_db_thread_pool, _get_monthly_usage_sync)
            
            total_requests = sum(record["request_count"] for record in result.data) if result.data else 0
            
            # Add debug logging for monthly usage queries
            logger.debug(f"Monthly usage query for user {user_id}: month_start={current_month}, records_found={len(result.data) if result.data else 0}, total_usage={total_requests}")
            
            return total_requests
            
        except Exception as e:
            logger.error(f"Failed to get monthly usage for user {user_id}: {e}")
            return 0

# Global database client instance
db_client = SupabaseClient()

# Update db_manager alias for compatibility
db_manager = db_client

# Helper functions for easy access
async def get_user_by_email(email: str) -> Optional[User]:
    """Get user by email"""
    return await db_client.get_user_by_email(email)

async def validate_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """Validate API key and return user info"""
    return await db_client.validate_api_key(api_key)

async def track_usage(user_id: str, feature: str, endpoint: str) -> bool:
    """Track API usage"""
    return await db_client.track_usage(user_id, feature, endpoint)

async def get_daily_usage(user_id: str) -> int:
    """Get daily usage count"""
    return await db_client.get_daily_usage(user_id)

async def get_monthly_usage(user_id: str) -> int:
    """Get monthly usage count"""
    return await db_client.get_monthly_usage(user_id)
