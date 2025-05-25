# main.py
import logging
import sys
import os

# Add the parent directory to sys.path to enable absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) 

# Import the MCP app - using absolute imports instead of relative
from congress_api.mcp_app import mcp

# Import all features to register them with the MCP server
from congress_api.features import bills, members, committees, congress_info, amendments, summaries, committee_reports, committee_prints

# Import prompts
from congress_api import prompts_module

def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )
    # Set specific loggers to DEBUG level
    logging.getLogger('congress_api.features.amendments').setLevel(logging.DEBUG)

def main():
    """Main entry point for the Congress.gov API MCP server."""
    setup_logging()
    print("Starting Congress.gov API MCP server...", file=sys.stderr)
    
    # Skip debugging info for now to avoid attribute errors
    print("Server is ready!", file=sys.stderr)
    return mcp

# This is the object that MCP will look for
server = main()

if __name__ == "__main__":
    # When run directly, we don't need to do anything else as main() already returns the server
    pass
