#!/usr/bin/env python3
"""
Entry point script for running the Congress.gov API MCP server.
This script avoids the relative import issues when running with the MCP CLI.
"""
import sys
import os
import logging

# Configure logger
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the server from the congress_api package
from congress_api.main import server

# The MCP CLI will automatically detect and use the 'server' object
if __name__ == "__main__":
    logger.info("Congress.gov API MCP server is ready!")
    logger.info("The server object has been exported and can be used by the MCP CLI.")
