# Congress.gov API MCP Server

This project provides a Model Context Protocol (MCP) server for accessing the Congress.gov API, allowing AI systems to retrieve and interact with legislative data from the United States Congress.

## Features

- Access to bill information, including actions, amendments, cosponsors, and more
- Search for members of Congress and view their details
- Browse congressional committees and their activities
- Get information about the current Congress
- Pre-defined prompts for common legislative research tasks

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
│   ├── bills.py               # Bill-related resources, tools, and formatting
│   ├── members.py             # Member-related resources, tools, and formatting
│   ├── committees.py          # Committee-related resources, tools, and formatting
│   ├── congress_info.py       # Resources for general Congress information
│   └── amendments.py          # Amendment-related formatting and tools
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

## API Documentation

For detailed information about the Congress.gov API endpoints, see the documentation in `documentation/CongressAPI_documentation.md`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
