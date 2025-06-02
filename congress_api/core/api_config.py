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
    Load environment variables from the appropriate .env file.
    
    Priority:
    1. CONGRESS_API_ENV environment variable (development, production, staging)
    2. Heroku detection (if PORT is set, assume production)
    3. Default to development
    """
    # Get the project root directory
    project_root = Path(__file__).parent.parent.parent
    
    # Determine environment
    env = os.getenv('CONGRESS_API_ENV')
    
    if not env:
        # Auto-detect environment
        if os.getenv('PORT'):  # Heroku sets PORT
            env = 'production'
        else:
            env = 'development'
    
    env = env.lower()
    
    # Load the appropriate .env file
    if env == "production":
        # In production, we expect environment variables to be set by the deployment platform
        # But we can still try to load from .env.production as a fallback
        env_file = project_root / ".env.production"
        if env_file.exists():
            logger.info(f"Loading production environment from: {env_file}")
            load_dotenv(env_file, override=True)
    elif env == "staging":
        env_file = project_root / ".env.staging"
        if env_file.exists():
            logger.info(f"Loading staging environment from: {env_file}")
            load_dotenv(env_file, override=True)
    else:  # development is the default
        env_file = project_root / ".env.development"
        if env_file.exists():
            logger.info(f"Loading development environment from: {env_file}")
            load_dotenv(env_file, override=True)
        else:
            # Fallback to .env
            fallback_env = project_root / ".env"
            if fallback_env.exists():
                logger.info(f"Fallback: Loading environment from: {fallback_env}")
                load_dotenv(fallback_env, override=True)
    
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
