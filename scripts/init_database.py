#!/usr/bin/env python3
"""
Database initialization script for Congressional MCP server.

This script helps verify the Supabase database connection and 
optionally creates test data for development.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add the parent directory to Python path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from congress_api.core.database import db_client
from congress_api.core.services.user_service import UserService
from congress_api.core.auth.auth import SubscriptionTier

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_database_connection():
    """Test the connection to Supabase."""
    logger.info("Testing database connection...")
    
    if not db_client.is_available():
        logger.error("❌ Database is not available. Check your Supabase configuration.")
        return False
    
    try:
        # Try a simple query to test the connection
        result = db_client.client.table('users').select('count').execute()
        logger.info(f"✅ Database connection successful. Users table accessible.")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {str(e)}")
        return False

async def create_test_user():
    """Create a test user for development."""
    logger.info("Creating test user...")
    
    user_service = UserService()
    
    try:
        # Create a test user
        test_email = "test@example.com"
        test_stripe_id = "cus_test_123456"
        
        user, api_key = await user_service.create_user_with_api_key(
            email=test_email,
            stripe_customer_id=test_stripe_id,
            tier=SubscriptionTier.PRO
        )
        
        if user and api_key:
            logger.info(f"✅ Test user created successfully:")
            logger.info(f"   Email: {user.email}")
            logger.info(f"   User ID: {user.id}")
            logger.info(f"   Tier: {user.subscription_tier}")
            logger.info(f"   API Key: {api_key}")
            return user, api_key
        else:
            logger.error("❌ Failed to create test user")
            return None, None
            
    except Exception as e:
        logger.error(f"❌ Error creating test user: {str(e)}")
        return None, None

async def test_api_key_validation():
    """Test API key validation."""
    logger.info("Testing API key validation...")
    
    try:
        # First, create a test user to get an API key
        user_service = UserService()
        
        # Try to find an existing test user or create one
        test_user, api_key = await create_test_user()
        if not test_user or not api_key:
            logger.error("❌ No API key available for testing")
            return False
        
        # Test API key validation
        validation_result = await db_client.validate_api_key(api_key)
        
        if validation_result:
            logger.info(f"✅ API key validation successful:")
            logger.info(f"   User ID: {validation_result.get('user_id')}")
            logger.info(f"   Tier: {validation_result.get('tier')}")
            logger.info(f"   Active: {validation_result.get('is_active')}")
            return True
        else:
            logger.error("❌ API key validation failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing API key validation: {str(e)}")
        return False

def show_database_stats():
    """Show basic database statistics."""
    logger.info("Fetching database statistics...")
    
    try:
        # Count users
        users_result = db_client.client.table('users').select('id', count='exact').execute()
        user_count = users_result.count if hasattr(users_result, 'count') else len(users_result.data)
        
        # Count API keys
        keys_result = db_client.client.table('api_keys').select('id', count='exact').execute()
        key_count = keys_result.count if hasattr(keys_result, 'count') else len(keys_result.data)
        
        # Count usage records
        usage_result = db_client.client.table('usage_tracking').select('id', count='exact').execute()
        usage_count = usage_result.count if hasattr(usage_result, 'count') else len(usage_result.data)
        
        logger.info(f"📊 Database Statistics:")
        logger.info(f"   Users: {user_count}")
        logger.info(f"   API Keys: {key_count}")
        logger.info(f"   Usage Records: {usage_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error fetching database stats: {str(e)}")
        return False

async def main():
    """Main initialization function."""
    logger.info("🚀 Starting Congressional MCP Database Initialization")
    logger.info("=" * 60)
    
    # Check environment configuration
    logger.info("Checking environment configuration...")
    
    required_env_vars = ['SUPABASE_URL', 'SUPABASE_SERVICE_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file and ensure Supabase is configured.")
        return False
    
    logger.info("✅ Environment configuration looks good")
    
    # Test database connection
    if not await test_database_connection():
        return False
    
    # Show current database stats
    show_database_stats()
    
    # Ask user if they want to create test data
    print("\n" + "=" * 60)
    try:
        create_test = input("Do you want to create a test user? (y/N): ").lower().strip()
        
        if create_test in ['y', 'yes']:
            test_user, api_key = await create_test_user()
            if test_user and api_key:
                # Test API key validation
                await test_api_key_validation()
    except EOFError:
        # Handle non-interactive environments
        logger.info("Running in non-interactive mode, skipping test user creation.")
    
    print("\n" + "=" * 60)
    logger.info("✅ Database initialization complete!")
    logger.info("Your Congressional MCP server is ready to use with Supabase.")
    
    return True

if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    
    # Try to load development environment first
    env_file = Path(__file__).parent.parent / ".env.development"
    if env_file.exists():
        load_dotenv(env_file)
        logger.info(f"Loaded environment from: {env_file}")
    else:
        # Fallback to .env
        load_dotenv()
        logger.info("Loaded environment from .env file")
    
    # Run the main function
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⏹️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        sys.exit(1)
