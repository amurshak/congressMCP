# Congress.gov API MCP Server

**🎉 Production Ready - Complete Legislative Data Access via 6 Bucket Tools**

This Model Context Protocol (MCP) server provides comprehensive access to the Congress.gov API through 6 organized bucket tools, enabling AI systems to retrieve and interact with legislative data from the United States Congress with a clean, unified interface.

**🎯 Complete Access: 6 Bucket Tools • 90 Operations • 36 Resources**

## 🚀 Quick Start

### 1. Get Your API Key
Visit [congressmcp.lawgiver.ai](https://congressmcp.lawgiver.ai) to register and get your API key.

### 2. Install via NPM (Recommended)
```bash
npm install -g congressmcp
```

### 3. Configure Claude Desktop
Add this to your Claude Desktop configuration:

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

### 4. Restart Claude Desktop
You'll now have access to 6 organized bucket tools covering 90 congressional operations plus 36 resources!

---

## 🗂️ Bucket Tool Architecture (v1.5.0)

### 🎯 **Major Achievement: 87+ Tools → 6 Organized Buckets**

We've successfully consolidated 87+ individual tools into 6 logical, organized bucket tools for a dramatically improved user experience:

#### 1. **📋 Legislation Hub** (`legislation_hub`)
**Consolidates:** Bills, Amendments, Summaries, Treaties  
**Operations:** 22 total (7 free, 15 paid)
- **Bills**: Search, details, text, actions, amendments, cosponsors, subjects
- **Amendments**: Search, details, actions, sponsors  
- **Summaries**: Bill summaries with keyword search
- **Treaties**: Search, actions, committees, text
- **Operations**: 22 total (7 free, 15 paid)

#### 2. **👥 Members and Committees** (`members_and_committees`)
**Consolidates:** Congressional Members, Committees, Committee Operations  
**Operations:** 13 total (3 free, 10 paid)
- **Members**: Search, details, sponsored/cosponsored legislation
- **Committees**: Search, bills, reports, communications, nominations
- **Operations**: 13 total (3 free, 10 paid)

#### 3. **🗳️ Voting and Nominations** (`voting_and_nominations`)
**Consolidates:** House Votes, Nominations  
**Operations:** 14 total (2 free, 12 paid)
- **House Votes**: By Congress/session, details, member votes, XML data
- **Nominations**: Search, details, actions, committees, hearings
- **Operations**: 14 total (2 free, 12 paid)

#### 4. **📰 Records and Hearings** (`records_and_hearings`)
**Consolidates:** Congressional Records, Communications, Hearings  
**Operations:** 16 total (3 free, 13 paid)
- **Congressional Records**: Daily/bound records, search functionality
- **Communications**: House/Senate communications, requirements
- **Hearings**: Search, details, content by Congress/chamber
- **Operations**: 16 total (3 free, 13 paid)

#### 5. **📊 Committee Intelligence** (`committee_intelligence`)
**Consolidates:** Committee Reports, Prints, Meetings  
**Operations:** 19 total (0 free, 19 paid)
- **Committee Reports**: Latest, by Congress/type, details, content
- **Committee Prints**: Latest, by Congress/chamber, details
- **Committee Meetings**: Latest, by Congress/chamber/committee, search
- **Operations**: 19 total (0 free, 19 paid)

#### 6. **🔬 Research and Professional** (`research_and_professional`)
**Consolidates:** Congress Information, CRS Reports  
**Operations:** 6 total (1 free, 5 paid)
- **Congress Info**: Basic and enhanced Congress information
- **CRS Reports**: Congressional Research Service report search
- **Professional Analytics**: Enhanced research capabilities
- **Operations**: 6 total (1 free, 5 paid)

---

## 🏗️ Architecture Overview

### Bucket Tool Design
Each bucket tool accepts an `operation` parameter to route to specific functionality:

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
- **Operation-Level Control**: Each bucket manages FREE_OPERATIONS and PAID_OPERATIONS sets
- **Tier-Based Access**: Free tier gets basic operations, paid tiers get full access
- **Clear Messaging**: Users receive detailed tier information and upgrade guidance

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
│   │   ├── buckets/            # 🆕 Bucket tool implementations
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

### Production Deployment (Heroku)
The server is deployed at `api-cmcp.lawgiver.ai` with:
- SSL/TLS encryption
- Automatic scaling
- Environment-based configuration
- Health monitoring

### Local Development
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
Key environment variables:
- `CONGRESS_API_KEY`: Your Congress.gov API key
- `LAWGIVER_JWT_SECRET`: JWT secret for authentication
- `LAWGIVER_API_KEYS`: API keys for user authentication (format: tier:user:key)
- `ENABLE_AUTH`: Enable authentication (true/false)
- `ADMIN_API_KEY`: Admin API key (optional, for key management)
- `ENABLE_KEY_MANAGEMENT`: Enable admin key management (true/false)
- `STRIPE_SECRET_KEY`: Stripe secret key for payments
- `STRIPE_WEBHOOK_SECRET`: Stripe webhook secret
- `STRIPE_PRICE_PRO_MONTHLY`: Stripe price ID for Pro monthly
- `STRIPE_PRICE_PRO_ANNUAL`: Stripe price ID for Pro annual
- `ENABLE_STRIPE`: Enable Stripe integration (true/false)
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_ANON_KEY`: Supabase anonymous key
- `SUPABASE_SERVICE_KEY`: Supabase service role key
- `ENABLE_DATABASE`: Enable database features (true/false)
- `RESEND_API_KEY`: Resend API key for email
- `RESEND_FROM_EMAIL`: From email address

---

## 🧪 Testing

### Run Tests
```bash
# Run all tests
pytest

# Run specific bucket tests
pytest tests/test_legislation_hub_bucket.py
pytest tests/test_members_committees_bucket.py

# Run with coverage
pytest --cov=congress_api
```

### Test Coverage
- **Bucket Tools**: Comprehensive operation routing and access control tests
- **Individual Features**: Unit tests for all internal functions
- **Integration**: End-to-end testing with real API responses
- **Authentication**: Tier-based access control verification

---

## 📚 Documentation

### Repository Documentation
- **API_RELIABILITY_GUIDE.md**: Comprehensive reliability framework documentation
- **TOOL_CONSOLIDATION_PLAN.md**: Bucket architecture implementation details

### Project Documentation (CongressMcpFiles/docs/)
- **PROJECT_STATUS.md**: Current project status and completion metrics
- **TECHNICAL_OVERVIEW.md**: High-level technical architecture
- **CHANGELOG.md**: Version history and feature releases
- **BUSINESS_OVERVIEW.md**: Market analysis and business strategy

---

## 🔧 Development

### Adding New Operations
1. **Implement internal function** in appropriate feature file
2. **Add operation to bucket** in relevant bucket tool
3. **Update operation sets** (FREE_OPERATIONS/PAID_OPERATIONS)
4. **Add comprehensive tests** for the new operation
5. **Update documentation** with operation details

### Bucket Tool Pattern
```python
@mcp.tool("bucket_name")
async def bucket_tool(ctx: Context, operation: str, **kwargs) -> str:
    # Access control check
    if operation in PAID_OPERATIONS and not has_paid_access(ctx):
        raise PaymentRequiredError(f"Operation '{operation}' requires paid subscription")
    
    # Route to internal function
    if operation == "example_operation":
        return await _example_operation(ctx, **kwargs)
    
    # Handle unknown operations
    raise ValueError(f"Unknown operation: {operation}")
```

---

## 🎯 Key Benefits

### For Users
- **Simplified Discovery**: 6 logical buckets instead of 87+ scattered tools
- **Consistent Interface**: Unified parameter handling across all operations
- **Clear Documentation**: Detailed operation descriptions and examples
- **Reliable Performance**: Comprehensive error handling and retry logic

### For Developers
- **Easier Maintenance**: Centralized logic and consistent patterns
- **Better Testing**: Focused test suites per bucket
- **Reduced Complexity**: Eliminated 87 individual tool registrations
- **Improved Organization**: Clear separation between interfaces and implementations

---

## 📊 Version History

### v1.5.0 - Bucket Architecture Complete
- **Major Achievement**: Consolidated 87+ tools into 6 organized buckets
- **Enhanced UX**: Simplified tool discovery and consistent interfaces
- **Access Control**: Operation-level tier management within buckets
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

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🆘 Support

- **Documentation**: [CongressMcpFiles/docs/](../docs/)
- **Issues**: GitHub Issues
- **Email**: support@lawgiver.ai
- **Website**: [congressmcp.lawgiver.ai](https://congressmcp.lawgiver.ai)
