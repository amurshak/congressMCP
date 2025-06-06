# Congress.gov API MCP Server

**🎉 Production Ready - Complete Legislative Data Access for Claude Desktop**

This project provides a Model Context Protocol (MCP) server for accessing the Congress.gov API through 6 organized bucket tools, allowing AI systems to retrieve and interact with legislative data from the United States Congress with a clean, unified interface.

[![smithery badge](https://smithery.ai/badge/@amurshak/podbeanmcp)](https://smithery.ai/server/@amurshak/podbeanmcp)

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
You'll now have access to 6 organized bucket tools covering 116+ congressional operations!

---

## 🗂️ Bucket Tool Architecture (v1.5.0)

### 6 Organized Bucket Tools

#### 1. **Legislation Hub** (`legislation_hub`)
- **Bills**: Search, details, text, actions, amendments, cosponsors, subjects
- **Amendments**: Search, details, actions, sponsors  
- **Summaries**: Bill summaries with keyword search
- **Treaties**: Search, actions, committees, text
- **Operations**: 30 total (7 free, 23 paid)

#### 2. **Members and Committees** (`members_and_committees`)
- **Members**: Search by name/state/party, sponsored/cosponsored legislation
- **Committees**: Search, bills, reports, communications, nominations
- **Operations**: 20 total (3 free, 17 paid)

#### 3. **Voting and Nominations** (`voting_and_nominations`)
- **House Votes**: By congress/session, vote details, member votes
- **Nominations**: Search, details, actions, committees, hearings, nominees
- **Operations**: 20 total (2 free, 18 paid)

#### 4. **Records and Hearings** (`records_and_hearings`)
- **Congressional Records**: Daily and bound record search
- **Communications**: House and Senate communications, requirements
- **Hearings**: Search, details, content by congress/chamber
- **Operations**: 20 total (3 free, 17 paid)

#### 5. **Committee Intelligence** (`committee_intelligence`)
- **Committee Reports**: Latest, by congress/type, details, content
- **Committee Prints**: Latest, by congress/chamber, details
- **Committee Meetings**: Latest, by congress/chamber/committee, details
- **Operations**: 20 total (0 free, 20 paid - professional tier)

#### 6. **Research and Professional** (`research_and_professional`)
- **Congress Information**: Basic and enhanced congress details
- **CRS Reports**: Congressional Research Service report search
- **Operations**: 6 total (1 free, 5 paid)

## Features

### Unified Interface
- **Operation-Based Routing**: Each bucket accepts an `operation` parameter
- **Consistent Parameters**: Unified parameter handling across all buckets
- **Clear Documentation**: Detailed operation descriptions and tier access info
- **Error Handling**: User-friendly error messages with operation guidance

### Access Control
- **Free Tier**: Access to 13 basic operations across buckets
- **Paid Tier**: Full access to all 116+ operations
- **Bucket-Level Management**: Centralized FREE_OPERATIONS and PAID_OPERATIONS
- **Clear Messaging**: Users receive detailed tier information for each bucket

## Project Structure

```
congress_api/                  # Main Python package for the server
├── __init__.py                # Makes 'congress_api' a package
├── main.py                    # Main script to run the server, imports modules for registration
├── mcp_app.py                 # Defines and configures the FastMCP instance (`mcp`)
│
├── core/                      # Core functionalities like API client and config
│   ├── __init__.py
│   ├── api_config.py          # API key, base URL, and .env loading
│   └── client_handler.py      # AppContext, app_lifespan, make_api_request
│
├── features/                  # Contains modules for different API resource types
│   ├── __init__.py
│   ├── amendments.py          # Amendment-related resources, tools, and formatting
│   ├── bills.py               # Bill-related resources, tools, and formatting
│   ├── bound_congressional_record.py # Bound congressional record resources and tools
│   ├── committee_meetings.py  # Committee meetings resources and tools
│   ├── committee_prints.py    # Committee prints resources and tools
│   ├── committee_reports.py   # Committee reports resources and tools
│   ├── committees.py          # Committee-related resources, tools, and formatting
│   ├── congress_info.py       # Resources for general Congress information
│   ├── congressional_record.py # Congressional record resources and tools
│   ├── crs_reports.py         # Congressional Research Service reports resources
│   ├── daily_congressional_record.py # Daily congressional record resources
│   ├── hearings.py            # Hearings resources and tools
│   ├── house_communications.py # House communications resources
│   ├── house_requirements.py  # House requirements resources
│   ├── members.py             # Member-related resources, tools, and formatting
│   ├── nominations.py         # Nominations resources and tools
│   ├── senate_communications.py # Senate communications resources
│   ├── summaries.py           # Bill summaries resources and tools
│   └── treaties.py            # Treaties resources and tools
│
└── prompts_module.py          # All @mcp.prompt definitions
```

## Setup

1. Clone the repository
2. Create a `.env` file in the project root with your Congress.gov API key:
   ```
   CONGRESS_API_KEY=your_api_key_here
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Running the Server

### Development Mode

For testing and debugging with the MCP Inspector:

```
mcp dev congress_api/main.py
```

Or use the provided development script:

```
./server.sh
```

### Claude Desktop Integration

To install the server in Claude Desktop:

```
mcp install congress_api/main.py
```

### Direct Execution

For advanced scenarios:

```
python -m congress_api.main
```

## Production Deployment

This project includes production-ready deployment configurations.

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

### Environment Configuration

The server supports environment-specific configuration using separate `.env` files:

#### For Local Development:
1. Copy the template for development:
   ```bash
   cp .env.template .env.development
   ```

2. Edit `.env.development` with your development settings:
   - Use your Congress.gov API key
   - For Stripe webhooks: Use the CLI secret from `stripe listen`

#### For Production Deployment:
1. Copy the template for production:
   ```bash
   cp .env.template .env.production
   ```

2. Edit `.env.production` with your production settings:
   - For Stripe webhooks: Use the webhook endpoint secret from Stripe Dashboard

#### Environment Detection:
- **Development**: Automatically detected when no `PORT` environment variable is set
- **Production**: Automatically detected when `PORT` is set (Heroku)
- **Manual**: Set `CONGRESS_API_ENV=development|production|staging`

#### Stripe Webhook Testing:
For local webhook testing with Stripe CLI:
```bash
# Terminal 1: Start the server (loads .env.development automatically)
uvicorn asgi:app --host=127.0.0.1 --port=8000

# Terminal 2: Forward webhooks from Stripe CLI
stripe listen --forward-to localhost:8000/stripe/webhook

# Terminal 3: Trigger test events
stripe trigger customer.created
stripe trigger customer.subscription.created
```

### Running with Production Server (Alternative Deployment)

**Note**: Heroku production deployment uses `uvicorn asgi:app` via the Procfile. This alternative server script is for other deployment scenarios:

```
python production_server.py --env production --workers 2
```

Options:
- `--host`: Host to bind to (default: 0.0.0.0)
- `--port`: Port to bind to (default: 8000)
- `--workers`: Number of worker processes (default: 1)
- `--env`: Environment (production, staging, development)
- `--log-level`: Log level (debug, info, warning, error, critical)

### Heroku Deployment

This MCP server can be deployed directly to Heroku using the simplified direct execution approach:

1. **One-Click Deployment**:
   
   Click the "Deploy to Heroku" button above and follow the prompts to set up your app with the required environment variables.

2. **Manual Deployment**:

   ```bash
   # Install the Heroku CLI if you haven't already
   # https://devcenter.heroku.com/articles/heroku-cli
   
   # Create a new Heroku app
   export APP_NAME=your-congressional-mcp
   heroku create $APP_NAME
   
   # Set the Python buildpack
   heroku buildpacks:set heroku/python -a $APP_NAME
   
   # Configure environment variables
   heroku config:set CONGRESS_API_KEY=your_api_key_here -a $APP_NAME
   heroku config:set CONGRESS_API_ENV=production -a $APP_NAME
   heroku config:set LOG_LEVEL=INFO -a $APP_NAME
   heroku config:set ENABLE_CACHING=true -a $APP_NAME
   heroku config:set CACHE_TIMEOUT=300 -a $APP_NAME
   
   # Deploy the application
   git push heroku main
   
   # Scale the web process
   heroku ps:scale web=1 -a $APP_NAME
   ```

3. **Verifying Your Deployment**:

   After deploying, you can verify that your MCP server is running correctly by checking:
   
   ```bash
   # Check the logs
   heroku logs --tail -a $APP_NAME
   
   # Check the health endpoint
   curl https://your-congressional-mcp.herokuapp.com/health
   
   # Check the MCP info endpoint
   curl https://your-congressional-mcp.herokuapp.com/mcp-info
   ```
   
   The MCP info endpoint should show non-zero counts for resources and tools, confirming that everything is registered correctly.

4. **Connecting to Your MCP Server**:

   Your MCP server will be available at:
   - SSE endpoint: `https://your-congressional-mcp.herokuapp.com/sse`
   - You can also use the MCP Inspector to connect to this endpoint

### Docker Deployment

For containerized deployment:

1. Build and run with Docker:
   ```
   docker build -t congress-mcp-server .
   docker run -p 8000:8000 -e CONGRESS_API_KEY=your_key_here congress-mcp-server
   ```

2. Or use Docker Compose:
   ```
   CONGRESS_API_KEY=your_key_here docker-compose up -d
   ```

### Production Features

The server includes several production-ready features:

- **Environment-specific configuration**: Different settings for development, staging, and production
- **Structured logging**: JSON-formatted logs in production for better parsing
- **Caching**: Optional in-memory caching to reduce API calls
- **Health checks**: `/health` endpoint for monitoring
- **Connection pooling**: Optimized HTTP client settings
- **Error handling**: Comprehensive error handling and reporting

## API Documentation

For detailed information about the Congress.gov API endpoints, see the documentation in `documentation/CongressAPI_documentation.md`.

## 🧪 Testing & Development

### Postman Testing
Test the production server directly:

**URL:** `https://congressmcp.lawgiver.ai/mcp/`  
**Method:** `POST`  
**Headers:**
```
Content-Type: application/json
Accept: application/json, text/event-stream
Authorization: Bearer your-api-key-here
X-Session-ID: test-session-123
```

**Sample Request (Initialize):**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "postman-test",
      "version": "1.0.0"
    }
  }
}
```

**Expected Response:**
```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05",...}}
```

### Local Development
For server development, see the deployment documentation in the `/deployment` folder.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
