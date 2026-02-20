# mcp_app.py
from fastmcp import FastMCP
from .core.cors import cors_headers
from .core.client_handler import app_lifespan

# Create the MCP server with metadata and stateless HTTP transport
mcp = FastMCP(
    "Congress MCP",
    description="Access legislative data from the Congress.gov API",
    version="1.1.0",
    dependencies=["httpx", "python-dotenv"],
    lifespan=app_lifespan,
    transport="streamable-http",  # Use streamable HTTP transport (correct per FastMCP docs)
    stateless_http=True  # Enable stateless mode to handle concurrent requests properly
)

def initialize_features():
    # DEPRECATED: ORIGINAL FEATURES REPLACED BY BUCKETS """Initialize all features - called after server setup to avoid circular imports"""
    # from .features import (
    #     bills, members, committees, congress_info, amendments, 
    #     committee_reports, committee_prints, committee_meetings,
    #     hearings, congressional_record, daily_congressional_record,
    #     bound_congressional_record, house_communications, house_requirements,
    #     senate_communications, nominations, treaties, summaries,
    #     house_votes, crs_reports
    # )
    
    # Initialize bucket tools
    from .features.buckets import (
        legislation_hub, 
        members_and_committees, 
        voting_and_nominations, 
        records_and_hearings,
        committee_intelligence,
        research_and_professional
    )

# Add webhook routes using FastMCP's custom route decorator
from starlette.requests import Request
from starlette.responses import JSONResponse

@mcp.custom_route("/stripe/webhook", methods=["POST"])
async def stripe_webhook_handler(request: Request) -> JSONResponse:
    """Handle Stripe webhook requests"""
    try:
        from .core.services.stripe_webhook import stripe_webhook
        stripe_signature = request.headers.get("stripe-signature")
        return await stripe_webhook(request, stripe_signature)
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Stripe webhook error: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return JSONResponse({"error": "Webhook processing failed", "details": str(e)}, status_code=500)

# REMOVED: Test webhook endpoint (security risk - bypassed signature verification)
# REMOVED: Stripe test GET endpoint (unnecessary in production)

@mcp.custom_route("/api/register/free", methods=["OPTIONS"])
async def handle_preflight(request: Request) -> JSONResponse:
    """Handle CORS preflight requests"""
    return JSONResponse(
        {},
        headers=cors_headers(request)
    )

@mcp.custom_route("/api/register/free", methods=["POST"])
async def register_free_user(request: Request) -> JSONResponse:
    """Handle free tier user registration with Stripe customer creation"""
    import json
    import logging
    import os
    from .core.services.user_service import register_or_send_magic_link
    
    logger = logging.getLogger(__name__)
    
    try:
        # Parse request body
        body = await request.body()
        data = json.loads(body.decode('utf-8'))
        email = data.get('email', '').strip().lower()
        
        # Basic email validation
        if not email:
            return JSONResponse(
                {"error": "Email is required"}, 
                status_code=400,
                headers=cors_headers(request)
            )
        
        # Simple email format validation
        import re
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_regex, email):
            return JSONResponse(
                {"error": "Please enter a valid email address"}, 
                status_code=400,
                headers=cors_headers(request)
            )
        
        # Use UserService helper function to handle registration logic
        # Note: Stripe customer creation now happens in user service to avoid duplicates
        result = await register_or_send_magic_link(email)
        
        if result.get("success"):
            return JSONResponse(
                result,
                headers=cors_headers(request)
            )
        else:
            return JSONResponse(
                {"error": result.get("message", "Registration failed. Please try again.")}, 
                status_code=500,
                headers=cors_headers(request)
            )
            
    except json.JSONDecodeError:
        return JSONResponse(
            {"error": "Invalid JSON data"}, 
            status_code=400,
            headers=cors_headers(request)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return JSONResponse(
            {"error": "An unexpected error occurred. Please try again."}, 
            status_code=500,
            headers=cors_headers(request)
        )

# REMOVED: Debug endpoint that leaked Stripe configuration details

@mcp.custom_route("/api/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "Congressional MCP Server",
        "version": "1.0.0"
    })

# Magic Link Authentication Endpoints

@mcp.custom_route("/api/auth/request-magic-link", methods=["OPTIONS"])
async def handle_magic_link_preflight(request: Request) -> JSONResponse:
    """Handle CORS preflight requests for magic link"""
    return JSONResponse(
        {},
        headers=cors_headers(request)
    )

@mcp.custom_route("/api/auth/request-magic-link", methods=["POST"])
async def request_magic_link(request: Request) -> JSONResponse:
    """Request a magic link for key management"""
    import json
    import logging
    from .core.auth.magic_link_service import get_magic_link_service
    
    logger = logging.getLogger(__name__)
    
    try:
        # Parse request body
        body = await request.body()
        data = json.loads(body.decode('utf-8'))
        email = data.get('email', '').strip().lower()
        
        # Basic email validation
        if not email:
            return JSONResponse(
                {"success": False, "message": "Email is required"}, 
                status_code=400,
                headers=cors_headers(request)
            )
        
        # Simple email format validation
        import re
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_regex, email):
            return JSONResponse(
                {"success": False, "message": "Please enter a valid email address"}, 
                status_code=400,
                headers=cors_headers(request)
            )
        
        # Request magic link
        magic_link_service = get_magic_link_service()
        result = await magic_link_service.request_magic_link(email, purpose="key_management")
        
        logger.info(f"Magic link request for {email}: {result.get('success', False)}")
        
        return JSONResponse(
            result,
            status_code=200 if result.get("success") else 400,
            headers=cors_headers(request)
        )
        
    except json.JSONDecodeError:
        return JSONResponse(
            {"success": False, "message": "Invalid JSON data"}, 
            status_code=400,
            headers=cors_headers(request)
        )
    except Exception as e:
        logger.error(f"Magic link request error: {e}")
        return JSONResponse(
            {"success": False, "message": "An unexpected error occurred. Please try again."}, 
            status_code=500,
            headers=cors_headers(request)
        )

@mcp.custom_route("/api/auth/verify-magic-link", methods=["OPTIONS"])
async def handle_verify_magic_link_preflight(request: Request) -> JSONResponse:
    """Handle CORS preflight requests for magic link verification"""
    return JSONResponse(
        {},
        headers=cors_headers(request)
    )

@mcp.custom_route("/api/auth/verify-magic-link", methods=["POST"])
async def verify_magic_link(request: Request) -> JSONResponse:
    """Verify a magic link token"""
    import json
    import logging
    from .core.auth.magic_link_service import get_magic_link_service
    
    logger = logging.getLogger(__name__)
    
    try:
        # Parse request body
        body = await request.body()
        data = json.loads(body.decode('utf-8'))
        token = data.get('token', '').strip()
        email = data.get('email', '').strip().lower()
        
        # Validation
        if not token or not email:
            return JSONResponse(
                {"valid": False, "message": "Token and email are required"}, 
                status_code=400,
                headers=cors_headers(request)
            )
        
        # Verify magic link
        magic_link_service = get_magic_link_service()
        result = await magic_link_service.verify_magic_link(token, email)
        
        logger.info(f"Magic link verification for {email}: {result.get('valid', False)}")
        
        return JSONResponse(
            result,
            status_code=200 if result.get("valid") else 400,
            headers=cors_headers(request)
        )
        
    except json.JSONDecodeError:
        return JSONResponse(
            {"valid": False, "message": "Invalid JSON data"}, 
            status_code=400,
            headers=cors_headers(request)
        )
    except Exception as e:
        logger.error(f"Magic link verification error: {e}")
        return JSONResponse(
            {"valid": False, "message": "An unexpected error occurred. Please try again."}, 
            status_code=500,
            headers=cors_headers(request)
        )

@mcp.custom_route("/api/user/dashboard", methods=["OPTIONS"])
async def handle_dashboard_preflight(request: Request) -> JSONResponse:
    """Handle CORS preflight requests for user dashboard"""
    return JSONResponse(
        {},
        headers=cors_headers(request)
    )

@mcp.custom_route("/api/user/dashboard", methods=["POST"])
async def get_user_dashboard(request: Request) -> JSONResponse:
    """Get user dashboard data"""
    import json
    import logging
    from .core.auth.magic_link_service import get_magic_link_service
    
    logger = logging.getLogger(__name__)
    
    try:
        # Parse request body
        body = await request.body()
        data = json.loads(body.decode('utf-8'))
        token = data.get('token', '').strip()
        email = data.get('email', '').strip().lower()
        
        # Validation
        if not token or not email:
            return JSONResponse(
                {"success": False, "message": "Token and email are required"}, 
                status_code=400,
                headers=cors_headers(request)
            )
        
        # Get dashboard data
        magic_link_service = get_magic_link_service()
        result = await magic_link_service.get_user_dashboard_data(token, email)
        
        logger.info(f"Dashboard data request for {email}: {result.get('success', False)}")
        
        return JSONResponse(
            result,
            status_code=200 if result.get("success") else 400,
            headers=cors_headers(request)
        )
        
    except json.JSONDecodeError:
        return JSONResponse(
            {"success": False, "message": "Invalid JSON data"}, 
            status_code=400,
            headers=cors_headers(request)
        )
    except Exception as e:
        logger.error(f"Dashboard data error: {e}")
        return JSONResponse(
            {"success": False, "message": "An unexpected error occurred. Please try again."}, 
            status_code=500,
            headers=cors_headers(request)
        )

@mcp.custom_route("/api/user/regenerate-key", methods=["OPTIONS"])
async def handle_regenerate_key_preflight(request: Request) -> JSONResponse:
    """Handle CORS preflight requests for API key regeneration"""
    return JSONResponse(
        {},
        headers=cors_headers(request)
    )

@mcp.custom_route("/api/user/regenerate-key", methods=["POST"])
async def regenerate_api_key(request: Request) -> JSONResponse:
    """Regenerate user's API key"""
    import json
    import logging
    from .core.auth.magic_link_service import get_magic_link_service
    
    logger = logging.getLogger(__name__)
    
    try:
        # Parse request body
        body = await request.body()
        data = json.loads(body.decode('utf-8'))
        token = (data.get('token') or '').strip()
        email = (data.get('email') or '').strip().lower()
        request_new_link = data.get('requestNewLink', False)
        
        # Validation
        logger.info(f"Regenerate key request - email: '{email}', token: '{token}', requestNewLink: {request_new_link}")
        
        if not email:
            logger.warning("Email validation failed - email is empty")
            return JSONResponse(
                {"success": False, "message": "Email is required"}, 
                status_code=400,
                headers=cors_headers(request)
            )
        
        magic_link_service = get_magic_link_service()
        
        # Handle request for new magic link
        if request_new_link:
            result = await magic_link_service.request_magic_link(email, purpose="key_management")
        else:
            # Validate token for API key regeneration
            if not token:
                logger.warning("Token validation failed - token is empty")
                return JSONResponse(
                    {"success": False, "message": "Session token is required"}, 
                    status_code=400,
                    headers=cors_headers(request)
                )
            
            result = await magic_link_service.regenerate_api_key(token, email)
        
        logger.info(f"API key regeneration for {email}: {result.get('success', False)}")
        
        return JSONResponse(
            result,
            status_code=200 if result.get("success") else 400,
            headers=cors_headers(request)
        )
        
    except json.JSONDecodeError:
        return JSONResponse(
            {"success": False, "message": "Invalid JSON data"}, 
            status_code=400,
            headers=cors_headers(request)
        )
    except Exception as e:
        logger.error(f"API key regeneration error: {e}")
        return JSONResponse(
            {"success": False, "message": "An unexpected error occurred. Please try again."}, 
            status_code=500,
            headers=cors_headers(request)
        )