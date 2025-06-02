#!/usr/bin/env python3
"""
Test script for upgrade email functionality.
Simulates a user upgrading to Pro and sends the upgrade email.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from congress_api.core.email_service import email_service
from congress_api.core.auth import SubscriptionTier

async def send_test_upgrade_email(test_email: str):
    """Send a test upgrade email"""
    print(f"🧪 Testing upgrade email service...")
    print(f"📧 Sending test upgrade email to: {test_email}")
    print(f"📤 From: KeyMaker <keymaker@congressmcp.lawgiver.ai>")
    print(f"🚀 Simulating upgrade to PRO tier")
    
    try:
        # Test upgrade email
        success = await email_service.send_upgrade_email(
            email=test_email,
            new_api_key="lawgiver_pro_test12345_UpgradeDemo789",
            new_tier=SubscriptionTier.PRO,
            user_name="Test User"
        )
        
        if success:
            print("✅ Test upgrade email sent successfully!")
            print(f"📬 Check your inbox at {test_email}")
            print("💡 If you don't see it, check your spam folder")
            print("🎉 This simulates what users get when they upgrade to Pro!")
            return True
        else:
            print("❌ Failed to send test upgrade email")
            return False
            
    except Exception as e:
        print(f"❌ Error sending test upgrade email: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_upgrade_email.py <email_address>")
        print("Example: python test_upgrade_email.py alex@example.com")
        sys.exit(1)
    
    test_email = sys.argv[1]
    
    # Basic email validation
    import re
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', test_email):
        print(f"❌ Invalid email format: {test_email}")
        sys.exit(1)
    
    try:
        result = asyncio.run(send_test_upgrade_email(test_email))
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Test cancelled")
        sys.exit(1)
