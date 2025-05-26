# Congress.gov API MCP Server

This project provides a Model Context Protocol (MCP) server for accessing the Congress.gov API, allowing AI systems to retrieve and interact with legislative data from the United States Congress.

## Features

### Legislative Information
- **Bills**: Access bill information, including actions, amendments, cosponsors, subjects, and more
- **Amendments**: Search and retrieve amendment details, actions, and sponsors
- **Summaries**: Access bill summaries with keyword search capabilities
- **Treaties**: Search and access treaty information, actions, and committees

### Congressional Members & Committees
- **Members**: Search for members of Congress by name, state, party, and other criteria
- **Committees**: Browse congressional committees, their activities, bills, and reports
- **Committee Reports**: Access committee reports with search capabilities
- **Committee Prints**: Retrieve committee prints filtered by congress and chamber
- **Committee Meetings**: Get information about scheduled and past committee meetings

### Congressional Records & Communications
- **Congressional Record**: Access the Congressional Record with search capabilities
- **Daily Congressional Record**: Retrieve daily congressional record issues
- **Bound Congressional Record**: Access bound congressional record issues
- **House Communications**: Retrieve house communications by type and congress
- **Senate Communications**: Access senate communications by type and congress
- **CRS Reports**: Search and access Congressional Research Service reports

### Other Resources
- **Congress Information**: Get information about current and past Congresses
- **Nominations**: Search and retrieve nomination details, actions, and committees
- **House Requirements**: Access house requirements information

### General Features
- Pre-defined prompts for common legislative research tasks
- Comprehensive search tools for all data types
- Formatted outputs for better readability

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
