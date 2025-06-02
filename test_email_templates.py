#!/usr/bin/env python3
"""
Comprehensive email template testing script.
Tests both welcome (free tier) and upgrade (pro tier) email templates.
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

async def test_email_templates(test_email: str, test_type: str = "both"):
    """Test email templates"""
    print(f"🧪 Testing email templates for: {test_email}")
    print(f"📤 From: KeyMaker <keymaker@congressmcp.lawgiver.ai>")
    print("-" * 60)
    
    results = []
    
    if test_type in ["both", "welcome", "free"]:
        print("\n📧 Testing FREE tier welcome email...")
        try:
            success = await email_service.send_welcome_email(
                email=test_email,
                api_key="lawgiver_free_test12345_WelcomeDemo789",
                tier=SubscriptionTier.FREE,
                user_name="Test User"
            )
            
            if success:
                print("✅ FREE tier welcome email sent successfully!")
                results.append("✅ FREE welcome email")
            else:
                print("❌ Failed to send FREE tier welcome email")
                results.append("❌ FREE welcome email")
                
        except Exception as e:
            print(f"❌ Error sending FREE tier welcome email: {str(e)}")
            results.append("❌ FREE welcome email (error)")
    
    if test_type in ["both", "upgrade", "pro"]:
        print("\n🚀 Testing PRO tier upgrade email...")
        try:
            success = await email_service.send_upgrade_email(
                email=test_email,
                new_api_key="lawgiver_pro_test12345_UpgradeDemo789",
                new_tier=SubscriptionTier.PRO,
                user_name="Test User"
            )
            
            if success:
                print("✅ PRO tier upgrade email sent successfully!")
                results.append("✅ PRO upgrade email")
            else:
                print("❌ Failed to send PRO tier upgrade email")
                results.append("❌ PRO upgrade email")
                
        except Exception as e:
            print(f"❌ Error sending PRO tier upgrade email: {str(e)}")
            results.append("❌ PRO upgrade email (error)")
    
    print("\n" + "=" * 60)
    print("📬 EMAIL TEMPLATE TEST RESULTS:")
    print("=" * 60)
    for result in results:
        print(f"  {result}")
    
    print(f"\n📧 Check your inbox at: {test_email}")
    print("💡 If you don't see the emails, check your spam folder")
    
    # Check what templates contain
    print("\n📋 EMAIL TEMPLATE FEATURES TESTED:")
    print("-" * 60)
    if test_type in ["both", "welcome", "free"]:
        print("🆓 FREE TIER WELCOME EMAIL:")
        print("  • 200 API calls per month")
        print("  • Basic tools: Bills, Members, Committees")
        print("  • Congress information and search")
        print("  • Email support (no community support)")
        print("  • Setup Guide link (not documentation)")
        print("  • support@congressmcp.lawgiver.ai contact")
    
    if test_type in ["both", "upgrade", "pro"]:
        print("⭐ PRO TIER UPGRADE EMAIL:")
        print("  • 5,000 API calls per month")
        print("  • Access to all 23+ tool categories")
        print("  • All congressional data types")
        print("  • Standard email support")
        print("  • support@congressmcp.lawgiver.ai contact")
    
    return len([r for r in results if "✅" in r]) == len(results)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_email_templates.py <email_address> [type]")
        print("Types: welcome, upgrade, both (default)")
        print("Example: python test_email_templates.py alex@example.com both")
        sys.exit(1)
    
    test_email = sys.argv[1]
    test_type = sys.argv[2] if len(sys.argv) > 2 else "both"
    
    if test_type not in ["welcome", "free", "upgrade", "pro", "both"]:
        print(f"❌ Invalid test type: {test_type}")
        print("Valid types: welcome, upgrade, both")
        sys.exit(1)
    
    # Basic email validation
    import re
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', test_email):
        print(f"❌ Invalid email format: {test_email}")
        sys.exit(1)
    
    try:
        result = asyncio.run(test_email_templates(test_email, test_type))
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Test cancelled")
        sys.exit(1)
