# Congressional MCP Feature Management

This document describes the feature management system for temporarily reducing tool complexity and overwhelm in the Congressional MCP server.

## Overview

The Congressional MCP server includes 125 tools and resources across 21 feature modules. To reduce complexity and improve user experience, we've implemented a configuration-based system to selectively enable features.

## Feature Modes

### Essential Mode (Default)
- **Features**: 2 (Bills, Members)
- **Tools**: ~15
- **Coverage**: Handles 60% of typical queries
- **Use Case**: New users, basic legislative research

**Enabled Tools:**
- Bills: `search_bills`, `get_bill_details`, `get_bill_text`, `get_bill_content`
- Members: `search_members`, `get_member_details`, `get_member_sponsored_legislation`

### High Value Mode
- **Features**: 6 (Essential + Amendments, Committees, House Votes, Summaries)
- **Tools**: ~35
- **Coverage**: Handles 85% of typical queries
- **Use Case**: Regular users, comprehensive research

**Additional Tools:**
- Amendments: `search_amendments`, `get_amendment_details`, `get_amendment_actions`
- Committees: `search_committees`, `get_committee_details`, `get_committee_bills`
- House Votes: `get_house_vote_details`, `get_house_vote_member_votes`
- Summaries: `search_summaries`, `get_bill_summaries`

### Specialized Mode
- **Features**: 9 (High Value + Nominations, Treaties, Congress Info)
- **Tools**: ~50
- **Coverage**: Handles 95% of typical queries
- **Use Case**: Power users, specialized research

**Additional Tools:**
- Nominations: `search_nominations`, `get_nomination_details`
- Treaties: `search_treaties`, `get_treaty_details`, `get_treaty_text`
- Congress Info: `get_congress_info`

### Full Mode
- **Features**: 21 (All available)
- **Tools**: 125
- **Coverage**: 100% functionality
- **Use Case**: Advanced users, comprehensive access

## Configuration

### Environment Variable
Set the feature mode using the `CONGRESS_MCP_FEATURE_MODE` environment variable:

```bash
# Essential mode (default)
CONGRESS_MCP_FEATURE_MODE=essential

# High value mode
CONGRESS_MCP_FEATURE_MODE=high_value

# Specialized mode
CONGRESS_MCP_FEATURE_MODE=specialized

# Full mode
CONGRESS_MCP_FEATURE_MODE=full
```

### Using the Management Script

The `scripts/manage_features.py` script provides an easy interface:

```bash
# Show current configuration
python scripts/manage_features.py status

# Switch to essential mode
python scripts/manage_features.py set essential

# Switch to high value mode
python scripts/manage_features.py set high_value

# List all available modes
python scripts/manage_features.py list
```

### Pre-configured Environment Files

Use the pre-configured `.env` files:

```bash
# Copy essential mode configuration
cp .env.essential .env

# Copy high value mode configuration
cp .env.high_value .env
```

## Implementation Details

### Dynamic Feature Loading
The system uses dynamic imports in `mcp_app.py` to load only enabled features:

```python
from .core.feature_config import get_enabled_features

enabled_features = get_enabled_features()
for feature_name in enabled_features:
    # Dynamically import only enabled features
```

### Reversibility
All changes are easily reversible:

1. **No code deletion**: All feature modules remain intact
2. **Configuration-based**: Changes are controlled by environment variables
3. **Instant switching**: Change modes and restart the server
4. **Backup system**: Management script automatically backs up `.env` files

### Logging
The system provides detailed logging about which features are loaded:

```
Congressional MCP Server - Feature Mode: essential
Loading 2/21 features (9.5% coverage)
✅ Loaded feature: bills
✅ Loaded feature: members
Congressional MCP Server initialized with 2 features
```

## Benefits

### For Users
- **Reduced Overwhelm**: Fewer tools to learn and navigate
- **Faster Discovery**: Easier to find relevant tools
- **Better Performance**: Faster server startup and response times
- **Progressive Complexity**: Start simple, add features as needed

### For Developers
- **Easy Testing**: Test with minimal feature set
- **Debugging**: Isolate issues to specific feature sets
- **Performance Tuning**: Identify resource usage by feature
- **Gradual Rollout**: Deploy new features incrementally

## Recommendations

### For New Users
Start with **Essential Mode** to learn the core functionality:
- Search and retrieve bills
- Find and research members of Congress
- Access bill text and basic information

### For Regular Users
Upgrade to **High Value Mode** when you need:
- Amendment tracking and analysis
- Committee research and bill assignments
- Voting records and member positions
- Bill summaries and legislative analysis

### For Power Users
Use **Specialized Mode** for:
- Presidential nominations and confirmations
- Treaty research and ratification tracking
- Congressional session information
- Advanced legislative research

### For Developers/Integrators
Use **Full Mode** for:
- Complete API testing
- Comprehensive data access
- Advanced integrations
- Production deployments requiring all features

## Monitoring

The feature configuration is logged at server startup and can be monitored through:

1. **Server Logs**: Check startup logs for feature loading status
2. **Management Script**: Use `status` command for current configuration
3. **Environment Variables**: Check `CONGRESS_MCP_FEATURE_MODE` value

## Future Enhancements

Potential improvements to the feature management system:

1. **Runtime Configuration**: Change modes without server restart
2. **Custom Feature Sets**: Define custom combinations of features
3. **Usage Analytics**: Track which tools are actually used
4. **Automatic Recommendations**: Suggest optimal feature sets based on usage
5. **API Endpoint**: Programmatic feature management via REST API
