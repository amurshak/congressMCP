# Congress.gov API MCP Server

**🎉 Production Ready - Complete Legislative Data Access via 6 Toolsets**

This Model Context Protocol (MCP) server provides comprehensive access to the Congress.gov API through 6 organized toolsets, enabling AI systems to retrieve and interact with legislative data from the United States Congress with a clean, unified interface.

**🎯 Complete Access: 6 Toolsets • 92 Operations • All Functions Available**

## 🚀 Quick Start (Hosted Service - Recommended)

### 1. Get Your API Key
Visit [congressmcp.lawgiver.ai](https://congressmcp.lawgiver.ai) to register and get your API key.

### 2. Install via NPM
```bash
npm install -g congressmcp
```

### 3. Configure Your MCP Client
Add this to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "congressional-mcp": {
      "command": "npx",
      "args": ["-y", "congressmcp"],
      "env": {
        "CONGRESSMCP_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### 4. Restart Your MCP Client
You'll now have access to 6 organized toolsets covering 92 congressional operations!

**For most users, this hosted approach provides the best experience with reliable uptime, automatic updates, and professional support.**

---

## 🗂️ Toolset Architecture (v1.6.0)

### 🎯 **Major Achievement: 87+ Tools → 6 Organized Toolsets**

We've successfully consolidated 87+ individual tools into 6 logical, organized toolsets for a dramatically improved user experience. All operations are now available to all users, with rate limiting based on tier:

#### 1. **📋 Legislation Hub** (`legislation_hub`)
**Consolidates:** Bills, Amendments, Summaries, Treaties  
**Operations:** 24 total (all available)
- **Bills**: Search, details, text, actions, amendments, cosponsors, subjects
- **Amendments**: Search, details, actions, sponsors  
- **Summaries**: Bill summaries with keyword search
- **Treaties**: Search, actions, committees, text

#### 2. **👥 Members and Committees** (`members_and_committees`)
**Consolidates:** Congressional Members, Committees, Committee Operations  
**Operations:** 13 total (all available)
- **Members**: Search, details, sponsored/cosponsored legislation
- **Committees**: Search, bills, reports, communications, nominations

#### 3. **🗳️ Voting and Nominations** (`voting_and_nominations`)
**Consolidates:** House Votes, Nominations  
**Operations:** 14 total (all available)
- **House Votes**: By Congress/session, details, member votes, XML data
- **Nominations**: Search, details, actions, committees, hearings

#### 4. **📰 Records and Hearings** (`records_and_hearings`)
**Consolidates:** Congressional Records, Communications, Hearings  
**Operations:** 16 total (all available)
- **Congressional Records**: Daily/bound records, search functionality
- **Communications**: House/Senate communications, requirements
- **Hearings**: Search, details, content by Congress/chamber

#### 5. **📊 Committee Intelligence** (`committee_intelligence`)
**Consolidates:** Committee Reports, Prints, Meetings  
**Operations:** 19 total (all available)
- **Committee Reports**: Latest, by Congress/type, details, content
- **Committee Prints**: Latest, by Congress/chamber, details
- **Committee Meetings**: Latest, by Congress/chamber/committee, search

#### 6. **🔬 Research and Professional** (`research_and_professional`)
**Consolidates:** Congress Information, CRS Reports  
**Operations:** 6 total (all available)
- **Congress Info**: Basic and enhanced Congress information
- **CRS Reports**: Congressional Research Service report search
- **Professional Analytics**: Enhanced research capabilities

---

## 🏗️ Architecture Overview

### Toolset Design
Each toolset accepts an `operation` parameter to route to specific functionality:

```python
# Example usage
await legislation_hub(
    operation="search_bills",
    keywords="climate change",
    congress=118,
    limit=10
)

await members_and_committees(
    operation="search_members",
    name="Smith",
    state="CA"
)
```

### Access Control
- **Universal Access**: All operations available to all users
- **Rate Limiting**: Free tier gets 200 calls/month, Pro tier gets 5000 calls/month
- **Usage Tracking**: Clear monitoring of API call usage and limits

### API Reliability Framework
- **Parameter Validation**: Comprehensive input validation for all operations
- **Defensive API Calls**: Retry logic and timeout handling for external requests
- **Response Processing**: Standardized deduplication and error handling
- **Enhanced Error Messages**: User-friendly error responses with operation guidance

---

## 📁 Project Structure

```
CongressMCP/
├── congress_api/
│   ├── core/                    # Core infrastructure
│   │   ├── auth.py             # Authentication & authorization
│   │   ├── config.py           # Configuration management
│   │   ├── database.py         # Database connections
│   │   └── middleware.py       # ASGI middleware
│   ├── features/               # Feature implementations
│   │   ├── buckets/            # 🆕 Toolset implementations
│   │   │   ├── legislation_hub.py
│   │   │   ├── members_and_committees.py
│   │   │   ├── voting_and_nominations.py
│   │   │   ├── records_and_hearings.py
│   │   │   ├── committee_intelligence.py
│   │   │   └── research_and_professional.py
│   │   ├── bills.py            # Internal bill functions
│   │   ├── members.py          # Internal member functions
│   │   ├── committees.py       # Internal committee functions
│   │   └── [other features]    # Internal feature functions
│   ├── reliability/            # API reliability framework
│   │   ├── validators.py       # Parameter validation
│   │   ├── api_wrapper.py      # Defensive API calls
│   │   ├── exceptions.py       # Error handling
│   │   └── response_utils.py   # Response processing
│   └── utils/                  # Utility functions
├── tests/                      # Comprehensive test suite
├── documentation/              # Technical documentation
├── requirements.txt            # Python dependencies
├── Procfile                    # Heroku deployment
└── README.md                   # This file
```

---

## 🚀 Deployment

### Production Deployment
The server is deployed at `api-cmcp.lawgiver.ai` with:
- SSL/TLS encryption
- Automatic scaling
- Environment-based configuration
- Health monitoring

### Self-Hosting (Advanced Users)

**Note:** Self-hosting requires significant technical setup and maintenance. The hosted service provides better reliability and support for most users.

For developers and enterprises who need full control:

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd CongressMCP
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the server**:
   ```bash
   python run_server.py
   ```

### Environment Configuration

**Core Configuration:**
- `CONGRESS_API_KEY`: Your Congress.gov API key (required)
- `ENABLE_AUTH`: Enable authentication (default: true)
- `ENABLE_DATABASE`: Enable database features (default: true)
- `ENABLE_STRIPE`: Enable payment integration (default: true)

**Authentication:**
- `LAWGIVER_JWT_SECRET`: JWT secret for authentication
- `LAWGIVER_API_KEYS`: API keys for user authentication (format: tier:user:key)
- `ADMIN_API_KEY`: Admin API key for key management
- `ENABLE_KEY_MANAGEMENT`: Enable admin key management (default: false)

**Database (Supabase):**
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_ANON_KEY`: Supabase anonymous key
- `SUPABASE_SERVICE_KEY`: Supabase service role key

**Payment Processing (Stripe):**
- `STRIPE_SECRET_KEY`: Stripe secret key
- `STRIPE_WEBHOOK_SECRET`: Stripe webhook secret
- `STRIPE_PRICE_PRO_MONTHLY`: Stripe price ID for Pro monthly
- `STRIPE_PRICE_PRO_ANNUAL`: Stripe price ID for Pro annual

**Email Service (Resend):**
- `RESEND_API_KEY`: Resend API key
- `RESEND_FROM_EMAIL`: From email address
- `FRONTEND_BASE_URL`: Frontend URL for magic links
- `MAGIC_LINK_EXPIRY_MINUTES`: Magic link expiry time (default: 60)

See `.env.example` for complete configuration with examples.

---

## 🧪 Testing

### Run Tests
```bash
# Run all tests
pytest

# Run specific toolset tests
pytest tests/test_legislation_hub_toolset.py
pytest tests/test_members_committees_toolset.py

# Run with coverage
pytest --cov=congress_api
```

### Test Coverage
- **Toolset Operations**: Operation routing and validation tests for each of the 6 toolsets
- **Core Features**: Selected tests for key functionality (amendments, email system)
- **Authentication**: User registration, email templates, and API key validation tests
- **Integration**: Basic endpoint testing with real API responses

---

## 📚 Documentation

### Repository Documentation
- **API_RELIABILITY_GUIDE.md**: Comprehensive reliability framework documentation
- **TOOL_CONSOLIDATION_PLAN.md**: Bucket architecture implementation details

### External Documentation
- **GitHub Issues**: Bug reports and feature requests
- **Website**: [congressmcp.lawgiver.ai](https://congressmcp.lawgiver.ai) for setup guides and API documentation

---

## 🔧 Development

### Adding New Operations
1. **Implement internal function** in appropriate feature file
2. **Add operation to toolset** in relevant toolset tool
3. **Update operation sets** (add to FREE_OPERATIONS and ALL_OPERATIONS)
4. **Add comprehensive tests** for the new operation
5. **Update documentation** with operation details

### Toolset Pattern
```python
@mcp.tool("toolset_name")
async def toolset_tool(ctx: Context, operation: str, **kwargs) -> str:
    # Validate operation exists
    if operation not in ALL_OPERATIONS:
        raise ValueError(f"Unknown operation: {operation}")
    
    # Rate limiting check (all operations available)
    await check_rate_limit(ctx)
    
    # Route to internal function
    if operation == "example_operation":
        return await _example_operation(ctx, **kwargs)
    
    # Handle routing
    return await route_operation(operation, ctx, **kwargs)
```

---

## 🎯 Key Benefits

### For Users
- **Simplified Discovery**: 6 logical toolsets instead of 87+ scattered tools
- **Universal Access**: All 92 operations available regardless of tier
- **Consistent Interface**: Unified parameter handling across all operations
- **Clear Documentation**: Detailed operation descriptions and examples
- **Reliable Performance**: Comprehensive error handling and retry logic

### For Developers
- **Easier Maintenance**: Centralized logic and consistent patterns
- **Better Testing**: Focused test suites per toolset
- **Reduced Complexity**: Eliminated 87 individual tool registrations
- **Improved Organization**: Clear separation between interfaces and implementations
- **Open Source Ready**: Easy configuration for self-hosting without commercial features

---

## 📊 Version History

### v1.6.0 - Universal Free Access
- **Major Achievement**: All 92 operations now available to free users
- **Simplified Tiers**: Rate limiting (200/5000 calls) instead of function restrictions
- **Open Source Ready**: Architecture supports easy deployment without commercial features
- **Enhanced UX**: Simplified tool discovery and universal access

### v1.5.0 - Toolset Architecture Complete
- **Major Achievement**: Consolidated 87+ tools into 6 organized toolsets
- **Enhanced UX**: Simplified tool discovery and consistent interfaces
- **Access Control**: Operation-level tier management within toolsets
- **API Reliability**: Full reliability framework integration

### Previous Versions
See [CHANGELOG.md](../docs/CHANGELOG.md) for complete version history.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes with tests
4. Update documentation
5. Submit a pull request

---

## 📄 License

This project is licensed under the Sustainable Use License - see the [LICENSE](LICENSE) file for details.

**In short:**
- ✅ **Free to use** for self-hosting and internal use
- ✅ **Modify and distribute** freely
- ❌ **Cannot offer as a competing hosted service**
- ✅ **Commercial use allowed** (except competitive hosting)

Want a hosted version without the hassle? Check out [congressmcp.lawgiver.ai](https://congressmcp.lawgiver.ai)

---

## 🆘 Support

- **Issues**: GitHub Issues
- **Email**: support@congressmcp.lawgiver.ai
- **Website**: [congressmcp.lawgiver.ai](https://congressmcp.lawgiver.ai)
