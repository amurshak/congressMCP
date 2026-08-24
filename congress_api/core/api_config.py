# api_config.py
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional

# Configure logger
logger = logging.getLogger(__name__)

def load_environment_config():
    """
    Load environment variables from a .env file, without overriding the shell.

    Rules:
    - CONGRESS_API_ENV selects an explicit environment ("production",
      "staging", "development"): its .env.{env} file is loaded if present.
    - Unset (the normal end-user install): environment is "local" and only a
      plain .env at the project root is loaded, if one exists.
    - Files never override variables already exported in the environment
      (override=False), so `CONGRESS_API_KEY=... congressmcp` always wins.
    - No platform auto-detection: the old Heroku PORT heuristic is gone.
    """
    project_root = Path(__file__).parent.parent.parent

    env = (os.getenv('CONGRESS_API_ENV') or '').lower().strip()

    if env:
        env_file = project_root / f".env.{env}"
        if env_file.exists():
            logger.info(f"Loading {env} environment from: {env_file}")
            load_dotenv(env_file, override=False)
    else:
        env = 'local'
        env_file = project_root / ".env"
        if env_file.exists():
            logger.info(f"Loading environment from: {env_file}")
            load_dotenv(env_file, override=False)

    logger.info(f"Environment: {env}")
    return env

# Load environment configuration
ENV = load_environment_config()

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
