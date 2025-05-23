# api_config.py
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
API_KEY = os.getenv("CONGRESS_API_KEY")
if not API_KEY:
    print("WARNING: CONGRESS_API_KEY environment variable is not set!", file=sys.stderr)
    print("The server will start, but API requests will fail.", file=sys.stderr)
    print("Please set the CONGRESS_API_KEY environment variable and restart the server.", file=sys.stderr)

BASE_URL = "https://api.congress.gov/v3"
