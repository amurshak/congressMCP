#!/usr/bin/env python3
"""
Simple script to test user creation functionality
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
import random

# Add the parent directory to Python path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from congress_api.core.services.user_service import UserService
from congress_api.core.auth.auth import SubscriptionTier

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_create_new_user():
    """Create a new test user with unique email"""
    
    # Generate unique email with timestamp
    import time
    timestamp = int(time.time())
    test_email = f"test_{timestamp}@example.com"
    test_stripe_id = f"cus_test_{timestamp}"
    
    logger.info(f"Creating new user: {test_email}")
    
    user_service = UserService()
    
    try:
        # Test different subscription tiers
        tiers = [SubscriptionTier.FREE, SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE]
        tier = random.choice(tiers)
        
        user, api_key = await user_service.create_user_with_api_key(
            email=test_email,
            stripe_customer_id=test_stripe_id,
            tier=tier
        )
        
        if user and api_key:
            logger.info("✅ SUCCESS! New user created:")
            logger.info(f"   📧 Email: {user.email}")
            logger.info(f"   🆔 User ID: {user.id}")
            logger.info(f"   💎 Subscription Tier: {user.subscription_tier}")
            logger.info(f"   🔑 API Key: {api_key}")
            logger.info(f"   📅 Created: {user.created_at}")
            
            # Test API key validation
            from congress_api.core.database import db_client
            validation_result = await db_client.validate_api_key(api_key)
            
            if validation_result:
                logger.info("✅ API key validation successful!")
                logger.info(f"   Valid: {validation_result.get('valid', False)}")
                logger.info(f"   User ID: {validation_result.get('user_id')}")
                logger.info(f"   Tier: {validation_result.get('tier')}")
            else:
                logger.error("❌ API key validation failed")
            
            return user, api_key
        else:
            logger.error("❌ Failed to create user")
            return None, None
            
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        return None, None

async def main():
    """Main test function"""
    
    # Load environment
    from dotenv import load_dotenv
    
    # Determine environment
    env_file = ".env.development"
    if os.getenv("PORT"):  # Heroku or production
        env_file = ".env.production"
    
    env_path = Path(__file__).parent / env_file
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded environment from: {env_path}")
    else:
        load_dotenv()
    
    logger.info("🧪 Testing User Creation")
    logger.info("=" * 50)
    
    # Test creating a new user
    await test_create_new_user()
    
    logger.info("=" * 50)
    logger.info("✅ User creation test complete!")

if __name__ == "__main__":
    asyncio.run(main())
