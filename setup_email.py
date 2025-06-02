#!/usr/bin/env python3
"""
Email service setup helper for CongressMCP.
This script helps configure email service environment variables.
"""

import os
import sys
from pathlib import Path

def setup_email_config():
    """Interactive setup for email configuration"""
    print("🏛️ CongressMCP Email Service Setup")
    print("=" * 50)
    
    # Check current configuration
    env_file = Path(".env")
    current_config = {}
    
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        current_config[key] = value
        except Exception as e:
            print(f"Warning: Could not read .env file: {e}")
    
    print("\n📧 Email Service Configuration")
    print("Current status:")
    
    resend_key = current_config.get('RESEND_API_KEY', '')
    from_email = current_config.get('RESEND_FROM_EMAIL', '')
    
    if resend_key:
        masked_key = resend_key[:8] + "..." + resend_key[-4:] if len(resend_key) > 12 else "***"
        print(f"  ✅ RESEND_API_KEY: {masked_key}")
    else:
        print("  ❌ RESEND_API_KEY: Not configured")
    
    if from_email:
        print(f"  ✅ RESEND_FROM_EMAIL: {from_email}")
    else:
        print("  ❌ RESEND_FROM_EMAIL: Not configured")
    
    print("\n" + "=" * 50)
    
    # Get user input
    print("\n🔑 Step 1: Resend API Key")
    print("Get your API key from: https://resend.com/api-keys")
    
    new_key = input(f"Enter your Resend API key (starts with 're_'): ").strip()
    
    if not new_key:
        print("❌ API key is required. Exiting.")
        return False
    
    if not new_key.startswith('re_'):
        print("⚠️  Warning: Resend API keys usually start with 're_'")
        confirm = input("Continue anyway? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            return False
    
    print("\n📮 Step 2: From Email Address")
    print("This is the email address that will send your emails.")
    print("For development, you can use: CongressMCP <noreply@resend.dev>")
    print("For production, use your verified domain: CongressMCP <noreply@yourdomain.com>")
    
    default_from = "CongressMCP <noreply@resend.dev>"
    new_from = input(f"Enter from email [{default_from}]: ").strip()
    
    if not new_from:
        new_from = default_from
    
    # Update .env file
    print("\n💾 Updating .env file...")
    
    try:
        # Read existing .env content
        env_lines = []
        if env_file.exists():
            with open(env_file, 'r') as f:
                env_lines = f.readlines()
        
        # Update or add email configuration
        updated_resend_key = False
        updated_from_email = False
        
        for i, line in enumerate(env_lines):
            if line.startswith('RESEND_API_KEY='):
                env_lines[i] = f"RESEND_API_KEY={new_key}\n"
                updated_resend_key = True
            elif line.startswith('RESEND_FROM_EMAIL='):
                env_lines[i] = f"RESEND_FROM_EMAIL={new_from}\n"
                updated_from_email = True
        
        # Add new lines if not found
        if not updated_resend_key:
            env_lines.append(f"\n# Email Service Configuration\nRESEND_API_KEY={new_key}\n")
        
        if not updated_from_email:
            env_lines.append(f"RESEND_FROM_EMAIL={new_from}\n")
        
        # Write back to .env
        with open(env_file, 'w') as f:
            f.writelines(env_lines)
        
        print("✅ .env file updated successfully!")
        
        print(f"\n🎉 Email service configured!")
        print(f"  📧 From: {new_from}")
        print(f"  🔑 API Key: {new_key[:8]}...{new_key[-4:]}")
        
        print(f"\n🧪 Next steps:")
        print(f"1. Test the email service: python test_email_service.py")
        print(f"2. Start your server and test user registration")
        print(f"3. Check that emails are being sent to new users")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating .env file: {e}")
        return False

def main():
    """Main setup function"""
    if not Path(".env").exists():
        print("⚠️  No .env file found. Creating one...")
        Path(".env").touch()
    
    success = setup_email_config()
    
    if success:
        print("\n✅ Email service setup complete!")
    else:
        print("\n❌ Email service setup failed.")
        print("Please check your configuration and try again.")
    
    return success

if __name__ == "__main__":
    try:
        result = main()
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        sys.exit(1)
