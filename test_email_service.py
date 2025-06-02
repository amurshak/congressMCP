#!/usr/bin/env python3
"""
Test script for the email service functionality.
This script helps verify email sending without requiring a full registration flow.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import our modules
from congress_api.core.email_service import email_service
from congress_api.core.auth import SubscriptionTier

async def test_email_service():
    """Test email service functionality"""
    logger.info("🧪 Testing CongressMCP Email Service")
    logger.info("=" * 50)
    
    # Check if email service is configured
    if not email_service.enabled:
        logger.warning("❌ Email service is not configured")
        logger.info("To enable email service:")
        logger.info("1. Get a Resend API key from: https://resend.com/api-keys")
        logger.info("2. Add RESEND_API_KEY=re_your_key_here to your .env file")
        logger.info("3. Add RESEND_FROM_EMAIL=CongressMCP <noreply@yourdomain.com> to your .env file")
        logger.info("4. Verify your domain in Resend dashboard")
        return False
    
    logger.info("✅ Email service is configured and ready")
    
    # Test email address (you can change this)
    test_email = input("\nEnter test email address (or press Enter to skip actual sending): ").strip()
    
    if not test_email:
        logger.info("📧 Email service configuration verified, but no test email sent")
        return True
    
    # Validate email format
    import re
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, test_email):
        logger.error("❌ Invalid email format")
        return False
    
    try:
        # Test welcome email
        logger.info(f"📤 Sending test welcome email to: {test_email}")
        test_api_key = "test_key_12345_free_tier_demo"
        
        success = await email_service.send_welcome_email(
            email=test_email,
            api_key=test_api_key,
            tier=SubscriptionTier.FREE,
            user_name="Test User"
        )
        
        if success:
            logger.info("✅ Welcome email sent successfully!")
            logger.info(f"📧 Check {test_email} for the welcome email")
        else:
            logger.error("❌ Failed to send welcome email")
            return False
        
        # Ask if user wants to test upgrade email
        test_upgrade = input("\nWould you like to test upgrade email too? (y/N): ").strip().lower()
        
        if test_upgrade in ['y', 'yes']:
            logger.info(f"📤 Sending test upgrade email to: {test_email}")
            test_pro_api_key = "test_key_67890_pro_tier_demo"
            
            upgrade_success = await email_service.send_upgrade_email(
                email=test_email,
                new_api_key=test_pro_api_key,
                new_tier=SubscriptionTier.PRO,
                user_name="Test User"
            )
            
            if upgrade_success:
                logger.info("✅ Upgrade email sent successfully!")
                logger.info(f"📧 Check {test_email} for the upgrade email")
            else:
                logger.error("❌ Failed to send upgrade email")
                return False
        
        logger.info("\n🎉 Email service test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Email service test failed: {str(e)}")
        return False

async def main():
    """Main test function"""
    logger.info("Starting email service test...")
    
    success = await test_email_service()
    
    if success:
        logger.info("\n✅ Email service is working correctly!")
        logger.info("🚀 You can now register users and they will receive API keys via email")
    else:
        logger.error("\n❌ Email service needs configuration")
        logger.info("📝 Check the .env.email.example file for setup instructions")
    
    return success

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        logger.info("\n⏹️  Test cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        sys.exit(1)
