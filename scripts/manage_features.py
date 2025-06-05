#!/usr/bin/env python3
"""
Congressional MCP Feature Management Script

Simple script to switch between different feature modes and get statistics.
"""

import os
import sys
import shutil
from pathlib import Path

# Add the parent directory to the path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

def show_feature_stats():
    """Show current feature configuration statistics."""
    try:
        from congress_api.core.feature_config import get_feature_stats, get_enabled_features
        
        stats = get_feature_stats()
        enabled = get_enabled_features()
        
        print(f"\n📊 Congressional MCP Feature Configuration")
        print(f"{'='*50}")
        print(f"Mode: {stats['mode']}")
        print(f"Features: {stats['enabled_count']}/{stats['total_available']} ({stats['coverage_percentage']}%)")
        print(f"\n🔧 Enabled Features:")
        for i, feature in enumerate(enabled, 1):
            print(f"  {i:2d}. {feature}")
        
        return stats
    except Exception as e:
        print(f"❌ Error getting feature stats: {e}")
        return None

def set_feature_mode(mode):
    """Set the feature mode by copying the appropriate .env file or updating environment variable."""
    FEATURE_MODES = {
        "essential": "2 features (~15 tools) - Bills + Members only",
        "high_value": "6 features (~35 tools) - Essential + Amendments, Committees, Votes, Summaries",
        "specialized": "9 features (~50 tools) - High Value + Nominations, Treaties, Congress Info",
        "full": "21 features (125 tools) - All features enabled"
    }
    
    if mode not in FEATURE_MODES:
        print(f"❌ Invalid mode '{mode}'. Available modes: {', '.join(FEATURE_MODES.keys())}")
        return False
    
    env_file = f".env.{mode}"
    
    if os.path.exists(env_file):
        # Backup current .env if it exists
        if os.path.exists(".env"):
            backup_file = ".env.backup"
            shutil.copy(".env", backup_file)
            print(f"📁 Backed up current .env to {backup_file}")
        
        # Copy the mode-specific template
        shutil.copy(env_file, ".env")
        print(f"✅ Copied {env_file} template to .env")
        print(f"⚠️  Note: You may need to add your API keys and other settings to .env")
        print(f"   (Copy them from .env.example or your backup)")
    else:
        # Fallback: update or create .env with just the mode setting
        env_content = f"CONGRESS_MCP_FEATURE_MODE={mode}\n"
        
        if os.path.exists(".env"):
            # Read existing .env and update the mode
            with open(".env", "r") as f:
                lines = f.readlines()
            
            # Update or add the feature mode line
            updated = False
            for i, line in enumerate(lines):
                if line.startswith("CONGRESS_MCP_FEATURE_MODE="):
                    lines[i] = f"CONGRESS_MCP_FEATURE_MODE={mode}\n"
                    updated = True
                    break
            
            if not updated:
                lines.append(f"CONGRESS_MCP_FEATURE_MODE={mode}\n")
            
            with open(".env", "w") as f:
                f.writelines(lines)
        else:
            # Create new .env with just the mode
            with open(".env", "w") as f:
                f.write(env_content)
        
        print(f"✅ Updated CONGRESS_MCP_FEATURE_MODE to '{mode}' in .env")
    
    print(f"\n🚀 Feature mode set to '{mode}'")
    print("   Restart your MCP server to apply changes.")
    return True

def main():
    """Main CLI interface."""
    if len(sys.argv) < 2:
        print("Congressional MCP Feature Manager")
        print("Usage:")
        print("  python manage_features.py <command> [options]")
        print("\nCommands:")
        print("  status                 - Show current feature configuration")
        print("  set <mode>            - Switch to feature mode")
        print("  list                  - List available modes")
        print("\nModes:")
        print("  essential    - 2 features (~15 tools) - Bills + Members only")
        print("  high_value   - 6 features (~35 tools) - Essential + Amendments, Committees, Votes, Summaries")
        print("  specialized  - 9 features (~50 tools) - High Value + Nominations, Treaties, Congress Info")
        print("  full         - 21 features (125 tools) - All features enabled")
        return
    
    command = sys.argv[1].lower()
    
    if command == "status":
        show_feature_stats()
    
    elif command == "set":
        if len(sys.argv) < 3:
            print("❌ Error: Please specify a mode (essential, high_value, specialized, full)")
            return
        
        mode = sys.argv[2].lower()
        set_feature_mode(mode)
    
    elif command == "list":
        print("Available Feature Modes:")
        print("  essential    - 2 features (~15 tools)")
        print("                 Bills: search_bills, get_bill_details, get_bill_text, get_bill_content")
        print("                 Members: search_members, get_member_details, get_member_sponsored_legislation")
        print("")
        print("  high_value   - 6 features (~35 tools)")
        print("                 Essential + Amendments, Committees, House Votes, Summaries")
        print("")
        print("  specialized  - 9 features (~50 tools)")
        print("                 High Value + Nominations, Treaties, Congress Info")
        print("")
        print("  full         - 21 features (125 tools)")
        print("                 All available Congressional MCP features")
    
    else:
        print(f"❌ Unknown command: {command}")
        print("Use 'python manage_features.py' for help")

if __name__ == "__main__":
    main()
