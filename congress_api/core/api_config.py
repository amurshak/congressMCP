# api_config.py
import os
import sys
import logging
from dotenv import load_dotenv
from typing import Dict, Any, Optional

# Configure logger
logger = logging.getLogger(__name__)

# Determine environment
ENV = os.getenv("CONGRESS_API_ENV", "development").lower()

# Load environment variables from the appropriate .env file
if ENV == "production":
    # In production, we expect environment variables to be set by the deployment platform
    # But we can still try to load from .env.production as a fallback
    load_dotenv(".env.production", override=True)
elif ENV == "staging":
    load_dotenv(".env.staging", override=True)
else:  # development is the default
    load_dotenv(".env", override=True)
    
# API Configuration
API_KEY = os.getenv("CONGRESS_API_KEY")
if not API_KEY:
    logger.error("CONGRESS_API_KEY environment variable is not set!")
    print("WARNING: CONGRESS_API_KEY environment variable is not set!", file=sys.stderr)
    print("The server will start, but API requests will fail.", file=sys.stderr)
    print("Please set the CONGRESS_API_KEY environment variable and restart the server.", file=sys.stderr)

# API Configuration
BASE_URL = os.getenv("CONGRESS_API_BASE_URL", "https://api.congress.gov/v3")

# Default request parameters
DEFAULT_REQUEST_PARAMS: Dict[str, Any] = {
    "format": "json",
    "limit": 20
}

# Cache configuration
ENABLE_CACHING = os.getenv("ENABLE_CACHING", "false").lower() == "true"
CACHE_TIMEOUT = int(os.getenv("CACHE_TIMEOUT", "300"))  # Default: 5 minutes

def get_api_config() -> Dict[str, Any]:
    """Return the current API configuration as a dictionary."""
    return {
        "environment": ENV,
        "base_url": BASE_URL,
        "caching_enabled": ENABLE_CACHING,
        "cache_timeout": CACHE_TIMEOUT,
        "api_key_configured": bool(API_KEY)
    }
