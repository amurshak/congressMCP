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
    """Initialize features based on configuration - called after server setup to avoid circular imports"""
    from .core.feature_config import get_enabled_features, get_feature_stats
    
    # Get enabled features from configuration
    enabled_features = get_enabled_features()
    stats = get_feature_stats()
    
    # Log configuration info
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Congressional MCP Server - Feature Mode: {stats['mode']}")
    logger.info(f"Loading {stats['enabled_count']}/{stats['total_available']} features ({stats['coverage_percentage']}% coverage)")
    
    # Dynamic import of enabled features only
    feature_modules = {}
    
    for feature_name in enabled_features:
        try:
            if feature_name == "bills":
                from .features import bills
                feature_modules["bills"] = bills
            elif feature_name == "members":
                from .features import members
                feature_modules["members"] = members
            elif feature_name == "committees":
                from .features import committees
                feature_modules["committees"] = committees
            elif feature_name == "congress_info":
                from .features import congress_info
                feature_modules["congress_info"] = congress_info
            elif feature_name == "amendments":
                from .features import amendments
                feature_modules["amendments"] = amendments
            elif feature_name == "summaries":
                from .features import summaries
                feature_modules["summaries"] = summaries
            elif feature_name == "house_votes":
                from .features import house_votes
                feature_modules["house_votes"] = house_votes
            elif feature_name == "committee_reports":
                from .features import committee_reports
                feature_modules["committee_reports"] = committee_reports
            elif feature_name == "committee_prints":
                from .features import committee_prints
                feature_modules["committee_prints"] = committee_prints
            elif feature_name == "committee_meetings":
                from .features import committee_meetings
                feature_modules["committee_meetings"] = committee_meetings
            elif feature_name == "hearings":
                from .features import hearings
                feature_modules["hearings"] = hearings
            elif feature_name == "congressional_record":
                from .features import congressional_record
                feature_modules["congressional_record"] = congressional_record
            elif feature_name == "daily_congressional_record":
                from .features import daily_congressional_record
                feature_modules["daily_congressional_record"] = daily_congressional_record
            elif feature_name == "bound_congressional_record":
                from .features import bound_congressional_record
                feature_modules["bound_congressional_record"] = bound_congressional_record
            elif feature_name == "house_communications":
                from .features import house_communications
                feature_modules["house_communications"] = house_communications
            elif feature_name == "house_requirements":
                from .features import house_requirements
                feature_modules["house_requirements"] = house_requirements
            elif feature_name == "senate_communications":
                from .features import senate_communications
                feature_modules["senate_communications"] = senate_communications
            elif feature_name == "nominations":
                from .features import nominations
                feature_modules["nominations"] = nominations
            elif feature_name == "crs_reports":
                from .features import crs_reports
                feature_modules["crs_reports"] = crs_reports
            elif feature_name == "treaties":
                from .features import treaties
                feature_modules["treaties"] = treaties
            
            logger.info(f"✅ Loaded feature: {feature_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load feature {feature_name}: {e}")
    
    # Import prompts
    from . import prompts_module
    
    logger.info(f"Congressional MCP Server initialized with {len(feature_modules)} features")
    return True

# Add webhook routes using FastMCP's custom route decorator
from starlette.requests import Request
from starlette.responses import JSONResponse

@mcp.custom_route("/stripe/webhook", methods=["POST"])
async def stripe_webhook_handler(request: Request) -> JSONResponse:
    """Handle Stripe webhook requests"""
    try:
        from .core.stripe_webhook import stripe_webhook
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
    from .core.user_service import UserService
    from .core.auth import SubscriptionTier
    
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
                "message": "Registration successful! Check your email for your API key.",
                "user_id": user.id,
                "tier": user.subscription_tier,
                "stripe_customer_id": stripe_customer_id,
                # Note: In production, remove api_key from response and only send via email
                "api_key": api_key if api_key else None
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