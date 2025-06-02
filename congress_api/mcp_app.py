# mcp_app.py
from fastmcp import FastMCP
from .core.client_handler import app_lifespan

# Create the MCP server with metadata and streamable HTTP transport
mcp = FastMCP(
    "Congress MCP",
    description="Access legislative data from the Congress.gov API",
    version="1.0.0",
    dependencies=["httpx", "python-dotenv"],
    lifespan=app_lifespan,
    transport="streamable-http"  # Use streamable HTTP transport (note the hyphen)
)

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
        logging.getLogger(__name__).error(f"Stripe webhook error: {e}")
        return JSONResponse({"error": "Webhook processing failed"}, status_code=500)

@mcp.custom_route("/stripe/test", methods=["GET"])
async def stripe_test_handler(request: Request) -> JSONResponse:
    """Test endpoint for Stripe webhooks"""
    return JSONResponse({"status": "test_success", "message": "Stripe test endpoint working"})
