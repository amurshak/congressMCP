#!/usr/bin/env python3
"""
Entry point script for running the Congress.gov API MCP server.
This script avoids the relative import issues when running with the MCP CLI.
"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the server from the congress_api package
from congress_api.main import server

# The MCP CLI will automatically detect and use the 'server' object
if __name__ == "__main__":
    print("Congress.gov API MCP server is ready!")
    print("The server object has been exported and can be used by the MCP CLI.")
