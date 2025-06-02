# database.py - Supabase database integration for user management and authentication
import os
import logging
import hashlib
import secrets
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
from supabase import create_client, Client
from .api_config import load_environment_config

# Configure logger
logger = logging.getLogger(__name__)

# Load environment configuration
ENV = load_environment_config()

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
            
            result = await asyncio.get_event_loop().run_in_executor(None, _create_user_sync)
            
            if result.data:
                user_record = result.data[0]
                logger.info(f"Created user: {email} with tier: {tier.value}")
                return User(
                    id=user_record["id"],
                    email=user_record["email"],
                    stripe_customer_id=user_record["stripe_customer_id"],
                    subscription_tier=SubscriptionTier(user_record["subscription_tier"]),
                    created_at=datetime.fromisoformat(user_record["created_at"]),
                    updated_at=datetime.fromisoformat(user_record["updated_at"]),
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
            
            result = await asyncio.get_event_loop().run_in_executor(None, _get_user_by_email_sync)
            
            if result.data:
                user_record = result.data[0]
                return User(
                    id=user_record["id"],
                    email=user_record["email"],
                    stripe_customer_id=user_record["stripe_customer_id"],
                    subscription_tier=SubscriptionTier(user_record["subscription_tier"]),
                    created_at=datetime.fromisoformat(user_record["created_at"]),
                    updated_at=datetime.fromisoformat(user_record["updated_at"]),
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
            
            result = await asyncio.get_event_loop().run_in_executor(None, _get_user_by_stripe_customer_id_sync)
            
            if result.data:
                user_record = result.data[0]
                return User(
                    id=user_record["id"],
                    email=user_record["email"],
                    stripe_customer_id=user_record["stripe_customer_id"],
                    subscription_tier=SubscriptionTier(user_record["subscription_tier"]),
                    created_at=datetime.fromisoformat(user_record["created_at"]),
                    updated_at=datetime.fromisoformat(user_record["updated_at"]),
                    is_active=user_record["is_active"]
                )
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user by Stripe ID {stripe_customer_id}: {e}")
            return None

    async def update_user_tier(self, user_id: str, tier: SubscriptionTier) -> bool:
        """Update user subscription tier"""
        if not self.is_available():
            return False
            
        try:
            def _update_user_tier_sync():
                return self.client.table("users").update({"subscription_tier": tier.value, "updated_at": datetime.utcnow().isoformat()}).eq("id", user_id).execute()
            
            result = await asyncio.get_event_loop().run_in_executor(None, _update_user_tier_sync)
            
            success = len(result.data) > 0
            if success:
                logger.info(f"Updated user {user_id} tier to {tier.value}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to update user {user_id} tier: {e}")
            return False

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
            
            result = await asyncio.get_event_loop().run_in_executor(None, _create_api_key_sync)
            
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
            
            result = await asyncio.get_event_loop().run_in_executor(None, _validate_api_key_sync)
            
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
            
            await asyncio.get_event_loop().run_in_executor(None, _update_key_last_used_sync)
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
            
            result = await asyncio.get_event_loop().run_in_executor(None, _revoke_api_key_sync)
            
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
            
            result = await asyncio.get_event_loop().run_in_executor(None, _track_usage_sync)
            
            if result.data:
                # Update existing record
                existing_record = result.data[0]
                new_count = existing_record["request_count"] + 1
                
                def _update_usage_sync():
                    return self.client.table("usage_tracking").update({"request_count": new_count, "endpoint": endpoint}).eq("id", existing_record["id"]).execute()
                
                await asyncio.get_event_loop().run_in_executor(None, _update_usage_sync)
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
                
                await asyncio.get_event_loop().run_in_executor(None, _create_usage_sync)
            
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
            
            result = await asyncio.get_event_loop().run_in_executor(None, _get_daily_usage_sync)
            
            total_requests = sum(record["request_count"] for record in result.data)
            return total_requests
            
        except Exception as e:
            logger.error(f"Failed to get daily usage for user {user_id}: {e}")
            return 0

# Global database client instance
db_client = SupabaseClient()

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
