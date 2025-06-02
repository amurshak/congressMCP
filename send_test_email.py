#!/usr/bin/env python3
"""
Direct test email sending script for CongressMCP.
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

async def send_test_email(test_email: str):
    """Send a test welcome email"""
    print(f"🧪 Testing email service...")
    print(f"📧 Sending test email to: {test_email}")
    print(f"📤 From: KeyMaker <keymaker@congressmcp.lawgiver.ai>")
    
    try:
        # Test welcome email
        success = await email_service.send_welcome_email(
            email=test_email,
            api_key="test_api_key_12345_demo",
            tier=SubscriptionTier.FREE,
            user_name="Test User"
        )
        
        if success:
            print("✅ Test email sent successfully!")
            print(f"📬 Check your inbox at {test_email}")
            print("💡 If you don't see it, check your spam folder")
            return True
        else:
            print("❌ Failed to send test email")
            return False
            
    except Exception as e:
        print(f"❌ Error sending test email: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python send_test_email.py <email_address>")
        print("Example: python send_test_email.py alex@example.com")
        sys.exit(1)
    
    test_email = sys.argv[1]
    
    # Basic email validation
    import re
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', test_email):
        print(f"❌ Invalid email format: {test_email}")
        sys.exit(1)
    
    try:
        result = asyncio.run(send_test_email(test_email))
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Test cancelled")
        sys.exit(1)
