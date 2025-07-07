#!/usr/bin/env python3
"""
Quick script to upgrade a user to Pro tier
Usage: python scripts/upgrade_user.py
"""
import asyncio
import sys
import os

# Add the congress_api directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from congress_api.core.database import db_client
from congress_api.core.auth.auth import SubscriptionTier

async def upgrade_user_to_pro(email: str):
    """Upgrade user to Pro tier"""
    try:
        print(f"🔍 Looking for user: {email}")
        
        # Get user by email
        user = await db_client.get_user_by_email(email)
        if not user:
            print(f"❌ User not found: {email}")
            return False
            
        print(f"✅ Found user: {user.email} (ID: {user.id})")
        print(f"   Current tier: {user.subscription_tier}")
        
        if user.subscription_tier == SubscriptionTier.PRO.value:
            print("✅ User is already Pro tier!")
            return True
            
        # Update to Pro tier
        success = await db_client.update_user_subscription_tier(user.id, SubscriptionTier.PRO)
        
        if success:
            print(f"🎉 Successfully upgraded {email} to Pro tier!")
            print(f"   New rate limit: 5,000 calls/month")
            return True
        else:
            print(f"❌ Failed to upgrade {email}")
            return False
            
    except Exception as e:
        print(f"❌ Error upgrading user: {e}")
        return False

async def list_users():
    """List all users in the database"""
    try:
        def _list_users_sync():
            return db_client.client.table("users").select("id, email, subscription_tier, created_at").execute()
        
        import asyncio
        result = await asyncio.get_event_loop().run_in_executor(None, _list_users_sync)
        
        print("📋 Users in database:")
        if result.data:
            for user in result.data:
                print(f"   {user['email']} - {user['subscription_tier']} - {user['created_at']}")
        else:
            print("   No users found")
            
    except Exception as e:
        print(f"❌ Error listing users: {e}")

async def main():
    email = "amurshak@gmail.com"
    
    print("🚀 Congressional MCP User Upgrade Tool")
    print("=" * 50)
    
    if not db_client.is_available():
        print("❌ Database is not available. Check your configuration.")
        return
        
    # First list existing users
    await list_users()
    print()
        
    success = await upgrade_user_to_pro(email)
    
    if success:
        print(f"\n✅ {email} has been upgraded to Pro tier!")
        print("   Rate limit: 5,000 calls/month")
        print("   All 91+ congressional functions available")
    else:
        print(f"\n❌ Failed to upgrade {email}")

if __name__ == "__main__":
    asyncio.run(main())