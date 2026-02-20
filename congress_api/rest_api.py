# rest_api.py - REST API endpoints for Stripe, auth, and dashboard
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from .core.cors import cors_headers

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

async def handle_preflight(request: Request) -> JSONResponse:
    """Handle CORS preflight requests"""
    return JSONResponse(
        {},
        headers=cors_headers(request)
    )

async def register_free_user(request: Request) -> JSONResponse:
    """Handle free tier user registration with Stripe customer creation"""
    import json
    import logging
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

async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "Congressional MCP Server",
        "version": "1.0.0"
    })

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

# Create REST API app with all endpoints
rest_app = Starlette(routes=[
    # Stripe webhook
    Route("/stripe/webhook", stripe_webhook_handler, methods=["POST"]),
    
    # Registration endpoints
    Route("/api/register/free", handle_preflight, methods=["OPTIONS"]),
    Route("/api/register/free", register_free_user, methods=["POST"]),
    
    # Health check
    Route("/api/health", health_check, methods=["GET"]),
    
    # Magic link authentication endpoints
    Route("/api/auth/request-magic-link", handle_preflight, methods=["OPTIONS"]),
    Route("/api/auth/request-magic-link", request_magic_link, methods=["POST"]),
    Route("/api/auth/verify-magic-link", handle_preflight, methods=["OPTIONS"]),
    Route("/api/auth/verify-magic-link", verify_magic_link, methods=["POST"]),
    
    # User dashboard endpoints
    Route("/api/user/dashboard", handle_preflight, methods=["OPTIONS"]),
    Route("/api/user/dashboard", get_user_dashboard, methods=["POST"]),
    Route("/api/user/regenerate-key", handle_preflight, methods=["OPTIONS"]),
    Route("/api/user/regenerate-key", regenerate_api_key, methods=["POST"]),
])