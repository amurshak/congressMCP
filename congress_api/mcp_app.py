# mcp_app.py
from fastmcp import FastMCP
from .core.client_handler import app_lifespan

# Create the MCP server with metadata and regular HTTP transport
mcp = FastMCP(
    "Congress MCP",
    description="Access legislative data from the Congress.gov API",
    version="1.1.0",
    dependencies=["httpx", "python-dotenv"],
    lifespan=app_lifespan,
    transport="streamable-http"  # Use streamable HTTP transport (correct per FastMCP docs)
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

@mcp.custom_route("/stripe/test", methods=["GET"])
async def stripe_test_handler(request: Request) -> JSONResponse:
    """Test endpoint for Stripe webhooks"""
    return JSONResponse({"status": "test_success", "message": "Stripe test endpoint working"})

@mcp.custom_route("/stripe/test/webhook", methods=["POST"])
async def stripe_test_webhook_handler(request: Request) -> JSONResponse:
    """Test webhook handler that bypasses signature verification"""
    try:
        import json
        from .core import user_service
        
        # Parse the request body
        payload = await request.body()
        event = json.loads(payload)
        
        event_type = event.get("type")
        event_data = event.get("data", {}).get("object", {})
        
        # Handle the webhook event
        result = await user_service.handle_stripe_webhook(event_type, event_data)
        
        return JSONResponse({
            "status": "success", 
            "processed": result,
            "event_type": event_type,
            "message": "Test webhook processed (no signature verification)"
        })
        
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Test webhook error: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return JSONResponse({"error": "Test webhook failed", "details": str(e)}, status_code=500)

@mcp.custom_route("/api/register/free", methods=["OPTIONS"])
async def handle_preflight(request: Request) -> JSONResponse:
    """Handle CORS preflight requests"""
    return JSONResponse(
        {},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@mcp.custom_route("/api/register/free", methods=["POST"])
async def register_free_user(request: Request) -> JSONResponse:
    """Handle free tier user registration with Stripe customer creation"""
    import json
    import logging
    import os
    from .core.services.user_service import UserService
    from .core.auth.auth import SubscriptionTier
    
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
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                }
            )
        
        # Simple email format validation
        import re
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_regex, email):
            return JSONResponse(
                {"error": "Please enter a valid email address"}, 
                status_code=400,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                }
            )
        
        # Check if Stripe is enabled
        enable_stripe = os.getenv("ENABLE_STRIPE", "true").lower() == "true"
        
        # Initialize user service
        user_service = UserService()
        
        # Check if user already exists
        try:
            from .core.database import db_client
            existing_user = await db_client.get_user_by_email(email)
            if existing_user:
                logger.info(f"User {email} already exists")
                return JSONResponse({
                    "success": True,
                    "message": "Registration successful! Check your email for your API key.",
                    "user_exists": True
                },
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                })
        except Exception as e:
            logger.warning(f"Could not check existing user: {e}")
            # Continue with registration if database check fails
        
        stripe_customer_id = None
        
        # Create Stripe customer for free user (enables seamless upgrades)
        if enable_stripe:
            try:
                import stripe
                stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
                
                if stripe.api_key:
                    logger.info(f"Creating Stripe customer for {email}...")
                    customer = stripe.Customer.create(
                        email=email,
                        metadata={
                            'tier': 'FREE',
                            'source': 'free_signup',
                            'created_via': 'congressional_mcp_frontend'
                        }
                    )
                    stripe_customer_id = customer.id
                    logger.info(f"✅ Created Stripe customer {stripe_customer_id} for free user {email}")
                else:
                    logger.warning("❌ Stripe API key not configured, creating user without Stripe customer")
            except Exception as e:
                logger.error(f"❌ Failed to create Stripe customer for {email}: {str(e)}")
                logger.error(f"Exception type: {type(e).__name__}")
                # Continue without Stripe customer - this is graceful degradation
        else:
            logger.info("Stripe is disabled, skipping customer creation")
        
        # Create new user with free tier
        user, api_key = await user_service.create_user_with_api_key(
            email=email,
            stripe_customer_id=stripe_customer_id,
            tier=SubscriptionTier.FREE
        )
        
        if user and api_key:
            logger.info(f"Successfully created free tier user: {email} (Stripe: {stripe_customer_id})")
            
            # Email sending is handled automatically by user_service.create_user_with_api_key
            return JSONResponse({
                "success": True,
                "message": "Registration successful! Your API key is shown below.",
                "user_id": user.id,
                "tier": user.subscription_tier,
                "stripe_customer_id": stripe_customer_id,
                "api_key": api_key if api_key else None,
                "email": email
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            })
        else:
            logger.error(f"Failed to create user: {email}")
            return JSONResponse(
                {"error": "Registration failed. Please try again."}, 
                status_code=500,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                }
            )
            
    except json.JSONDecodeError:
        return JSONResponse(
            {"error": "Invalid JSON data"}, 
            status_code=400,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return JSONResponse(
            {"error": "An unexpected error occurred. Please try again."}, 
            status_code=500,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )

@mcp.custom_route("/api/debug/stripe", methods=["GET"])
async def debug_stripe_config(request: Request) -> JSONResponse:
    """Debug endpoint to check Stripe configuration"""
    import os
    try:
        import stripe
        stripe_available = True
    except ImportError:
        stripe_available = False
    
    return JSONResponse({
        "stripe_package_available": stripe_available,
        "enable_stripe": os.getenv("ENABLE_STRIPE", "not_set"),
        "stripe_secret_key_present": bool(os.getenv("STRIPE_SECRET_KEY")),
        "stripe_secret_key_prefix": os.getenv("STRIPE_SECRET_KEY", "")[:7] + "..." if os.getenv("STRIPE_SECRET_KEY") else "not_set",
        "environment": os.getenv("CONGRESS_API_ENV", "not_set")
    })

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
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
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
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                }
            )
        
        # Simple email format validation
        import re
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_regex, email):
            return JSONResponse(
                {"success": False, "message": "Please enter a valid email address"}, 
                status_code=400,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                }
            )
        
        # Request magic link
        magic_link_service = get_magic_link_service()
        result = await magic_link_service.request_magic_link(email, purpose="key_management")
        
        logger.info(f"Magic link request for {email}: {result.get('success', False)}")
        
        return JSONResponse(
            result,
            status_code=200 if result.get("success") else 400,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
        
    except json.JSONDecodeError:
        return JSONResponse(
            {"success": False, "message": "Invalid JSON data"}, 
            status_code=400,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
    except Exception as e:
        logger.error(f"Magic link request error: {e}")
        return JSONResponse(
            {"success": False, "message": "An unexpected error occurred. Please try again."}, 
            status_code=500,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )

@mcp.custom_route("/api/auth/verify-magic-link", methods=["OPTIONS"])
async def handle_verify_magic_link_preflight(request: Request) -> JSONResponse:
    """Handle CORS preflight requests for magic link verification"""
    return JSONResponse(
        {},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
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
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                }
            )
        
        # Verify magic link
        magic_link_service = get_magic_link_service()
        result = await magic_link_service.verify_magic_link(token, email)
        
        logger.info(f"Magic link verification for {email}: {result.get('valid', False)}")
        
        return JSONResponse(
            result,
            status_code=200 if result.get("valid") else 400,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
        
    except json.JSONDecodeError:
        return JSONResponse(
            {"valid": False, "message": "Invalid JSON data"}, 
            status_code=400,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
    except Exception as e:
        logger.error(f"Magic link verification error: {e}")
        return JSONResponse(
            {"valid": False, "message": "An unexpected error occurred. Please try again."}, 
            status_code=500,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )

@mcp.custom_route("/api/user/dashboard", methods=["OPTIONS"])
async def handle_dashboard_preflight(request: Request) -> JSONResponse:
    """Handle CORS preflight requests for user dashboard"""
    return JSONResponse(
        {},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
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
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                }
            )
        
        # Get dashboard data
        magic_link_service = get_magic_link_service()
        result = await magic_link_service.get_user_dashboard_data(token, email)
        
        logger.info(f"Dashboard data request for {email}: {result.get('success', False)}")
        
        return JSONResponse(
            result,
            status_code=200 if result.get("success") else 400,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
        
    except json.JSONDecodeError:
        return JSONResponse(
            {"success": False, "message": "Invalid JSON data"}, 
            status_code=400,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
    except Exception as e:
        logger.error(f"Dashboard data error: {e}")
        return JSONResponse(
            {"success": False, "message": "An unexpected error occurred. Please try again."}, 
            status_code=500,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )

@mcp.custom_route("/api/user/regenerate-key", methods=["OPTIONS"])
async def handle_regenerate_key_preflight(request: Request) -> JSONResponse:
    """Handle CORS preflight requests for API key regeneration"""
    return JSONResponse(
        {},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
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
        if not email:
            return JSONResponse(
                {"success": False, "message": "Email is required"}, 
                status_code=400,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                }
            )
        
        magic_link_service = get_magic_link_service()
        
        # Handle request for new magic link
        if request_new_link:
            result = await magic_link_service.request_magic_link(email, purpose="key_management")
        else:
            # Validate token for API key regeneration
            if not token:
                return JSONResponse(
                    {"success": False, "message": "Session token is required"}, 
                    status_code=400,
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                        "Access-Control-Allow-Headers": "*",
                    }
                )
            
            result = await magic_link_service.regenerate_api_key(token, email)
        
        logger.info(f"API key regeneration for {email}: {result.get('success', False)}")
        
        return JSONResponse(
            result,
            status_code=200 if result.get("success") else 400,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
        
    except json.JSONDecodeError:
        return JSONResponse(
            {"success": False, "message": "Invalid JSON data"}, 
            status_code=400,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
    except Exception as e:
        logger.error(f"API key regeneration error: {e}")
        return JSONResponse(
            {"success": False, "message": "An unexpected error occurred. Please try again."}, 
            status_code=500,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )