# magic_link_service.py
import os
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from ..services.email_service import EmailService, email_service
from .auth import SubscriptionTier

# Configure logger
logger = logging.getLogger(__name__)

class MagicLinkService:
    """Service for handling magic link generation and verification"""
    
    def __init__(self, db_manager, email_service: EmailService):
        self.db = db_manager
        self.email_service = email_service
        self.default_expiry_minutes = int(os.getenv("MAGIC_LINK_EXPIRY_MINUTES", "15"))
        self.frontend_base_url = os.getenv("FRONTEND_BASE_URL", "https://congressmcp.com")
        
    async def request_magic_link(self, email: str, purpose: str = "key_management") -> Dict[str, Any]:
        """
        Request a magic link for email-based authentication
        
        Args:
            email: User email address
            purpose: Purpose of the magic link ('key_management' or 'registration')
            
        Returns:
            Dict containing success status and message
        """
        try:
            # Check if user exists
            from ..database import get_user_by_email
            user = await get_user_by_email(email)
            
            if not user and purpose == "key_management":
                return {
                    "success": False,
                    "message": "No account found with this email address. Please sign up first."
                }
            
            # Clean up any existing expired links for this email
            await self._cleanup_expired_links(email)
            
            # Generate secure token
            token = self._generate_secure_token()
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.default_expiry_minutes)
            
            # Store magic link in database
            magic_link_id = await self.db.create_magic_link(
                user_id=user.id if user else None,
                email=email,
                token=token,
                expires_at=expires_at,
                purpose=purpose
            )
            
            if not magic_link_id:
                raise Exception("Failed to create magic link in database")
            
            # Generate magic link URL
            magic_url = self._generate_magic_link_url(token, email, purpose)
            
            # Send email with magic link
            email_sent = await self._send_magic_link_email(
                email=email,
                magic_url=magic_url,
                expires_minutes=self.default_expiry_minutes,
                purpose=purpose,
                user_name=user.email.split('@')[0] if user else email.split('@')[0]
            )
            
            if not email_sent:
                # Clean up the magic link if email failed
                await self.db.delete_magic_link(token)
                return {
                    "success": False,
                    "message": "Failed to send magic link email. Please try again."
                }
            
            logger.info(f"Magic link sent successfully to {email} for {purpose}")
            
            return {
                "success": True,
                "message": f"Magic link sent to {email}. Please check your inbox and spam folder.",
                "expires_in_minutes": self.default_expiry_minutes
            }
            
        except Exception as e:
            logger.error(f"Error requesting magic link for {email}: {str(e)}")
            return {
                "success": False,
                "message": "An error occurred while sending the magic link. Please try again."
            }
    
    async def verify_magic_link(self, token: str, email: str) -> Dict[str, Any]:
        """
        Verify a magic link token and return user information
        
        Args:
            token: Magic link token
            email: User email address
            
        Returns:
            Dict containing verification result and user data
        """
        try:
            # Get magic link from database
            magic_link = await self.db.get_magic_link(token)
            
            if not magic_link:
                return {
                    "valid": False,
                    "message": "Invalid or expired magic link. Please request a new one."
                }
            
            # Check if already used
            if magic_link.get("is_used"):
                return {
                    "valid": False,
                    "message": "This magic link has already been used. Please request a new one."
                }
            
            # Check if expired
            expires_at = magic_link.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            
            if datetime.now(timezone.utc) > expires_at:
                return {
                    "valid": False,
                    "message": "This magic link has expired. Please request a new one."
                }
            
            # Check if email matches
            if magic_link.get("email").lower() != email.lower():
                return {
                    "valid": False,
                    "message": "Invalid magic link. Please request a new one."
                }
            
            # Mark magic link as used
            await self.db.mark_magic_link_used(token)
            
            # Get or create user
            from ..database import get_user_by_email
            user = await get_user_by_email(email)
            if not user:
                # This shouldn't happen for key_management links, but handle gracefully
                return {
                    "valid": False,
                    "message": "User account not found. Please sign up first."
                }
            
            # Get user's API key info (we can't retrieve the actual key, only metadata)
            api_key_data = await self.db.get_active_api_key_for_user(user.id)
            if not api_key_data:
                return {
                    "valid": False,
                    "message": "No active API key found. Please regenerate your API key."
                }
            
            # Get usage statistics using helper functions
            from ..database import get_monthly_usage
            monthly_usage = await get_monthly_usage(user.id)
            
            # Determine limits based on tier
            if user.subscription_tier == "pro":
                limit = 5000
            elif user.subscription_tier == "enterprise":
                limit = -1  # Unlimited
            else:
                limit = 200
                
            usage_stats = {
                "current": monthly_usage,
                "limit": limit,
                "period": "monthly"
            }
            
            logger.info(f"Magic link verified successfully for {email}")
            
            return {
                "valid": True,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "tier": user.subscription_tier,
                    "created_at": user.created_at.isoformat() if user.created_at else None
                },
                "api_key_created_at": api_key_data.get("created_at"),
                "api_key_last_used": api_key_data.get("last_used_at"),
                "usage": usage_stats,
                "session_token": self._generate_session_token(user.id, token)
            }
            
        except Exception as e:
            logger.error(f"Error verifying magic link {token}: {str(e)}")
            return {
                "valid": False,
                "message": "An error occurred while verifying the magic link. Please try again."
            }
    
    async def regenerate_api_key(self, session_token: str, email: str) -> Dict[str, Any]:
        """
        Regenerate API key for authenticated user
        
        Args:
            session_token: Valid session token from magic link verification
            email: User email address
            
        Returns:
            Dict containing new API key data
        """
        try:
            # Verify session token (basic implementation - could be enhanced)
            if not self._verify_session_token(session_token, email):
                return {
                    "success": False,
                    "message": "Invalid session. Please request a new magic link."
                }
            
            # Get user
            from ..database import get_user_by_email
            user = await get_user_by_email(email)
            if not user:
                return {
                    "success": False,
                    "message": "User not found."
                }
            
            # Deactivate existing API keys
            await self.db.deactivate_user_api_keys(user.id)
            
            # Generate new API key
            from ..services.user_service import UserService
            user_service = UserService()
            new_api_key = await user_service.generate_api_key(user.id, user.subscription_tier)
            
            if not new_api_key:
                return {
                    "success": False,
                    "message": "Failed to generate new API key."
                }
            
            # Note: New API key is shown directly in dashboard, no email needed
            logger.info(f"New API key for {email} available in dashboard")
            
            logger.info(f"API key regenerated successfully for {email}")
            
            return {
                "success": True,
                "api_key": new_api_key,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "message": "API key regenerated successfully. Please update your configuration."
            }
            
        except Exception as e:
            logger.error(f"Error regenerating API key for {email}: {str(e)}")
            return {
                "success": False,
                "message": "An error occurred while regenerating the API key. Please try again."
            }
    
    async def get_user_dashboard_data(self, session_token: str, email: str) -> Dict[str, Any]:
        """
        Get user dashboard data for authenticated user
        
        Args:
            session_token: Valid session token
            email: User email address
            
        Returns:
            Dict containing user dashboard data
        """
        try:
            # Verify session token
            if not self._verify_session_token(session_token, email):
                return {
                    "success": False,
                    "message": "Invalid session. Please request a new magic link."
                }
            
            # Get user
            from ..database import get_user_by_email
            user = await get_user_by_email(email)
            if not user:
                return {
                    "success": False,
                    "message": "User not found."
                }
            
            # Get API key info
            api_key_data = await self.db.get_active_api_key_for_user(user.id)
            
            # Get usage statistics using helper functions
            from ..database import get_monthly_usage
            monthly_usage = await get_monthly_usage(user.id)
            
            # Determine limits based on tier
            if user.subscription_tier == "pro":
                limit = 5000
            elif user.subscription_tier == "enterprise":
                limit = -1  # Unlimited
            else:
                limit = 200
                
            usage_stats = {
                "current": monthly_usage,
                "limit": limit,
                "period": "monthly"
            }
            
            # Calculate billing period (simplified)
            billing_start = user.created_at.replace(day=1) if user.created_at else datetime.now(timezone.utc).replace(day=1)
            billing_end = (billing_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            return {
                "success": True,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "tier": user.subscription_tier,
                    "created_at": user.created_at.isoformat() if user.created_at else None
                },
                "api_key_exists": bool(api_key_data),
                "api_key_created_at": api_key_data.get("created_at") if api_key_data else None,
                "api_key_last_used": api_key_data.get("last_used_at") if api_key_data else None,
                "usage": usage_stats,
                "billing_period": {
                    "start": billing_start.isoformat(),
                    "end": billing_end.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard data for {email}: {str(e)}")
            return {
                "success": False,
                "message": "An error occurred while loading dashboard data."
            }
    
    async def cleanup_expired_links(self) -> int:
        """Clean up expired magic links - called by background task"""
        try:
            deleted_count = await self.db.delete_expired_magic_links()
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired magic links")
            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up expired magic links: {str(e)}")
            return 0
    
    def _generate_secure_token(self) -> str:
        """Generate a cryptographically secure random token"""
        return secrets.token_urlsafe(32)
    
    def _generate_magic_link_url(self, token: str, email: str, purpose: str) -> str:
        """Generate the magic link URL"""
        params = {
            "token": token,
            "email": email
        }
        
        if purpose == "key_management":
            base_path = "/manage"
        else:
            base_path = "/verify"
        
        return f"{self.frontend_base_url}{base_path}?{urlencode(params)}"
    
    def _generate_session_token(self, user_id: str, magic_token: str) -> str:
        """Generate a session token (simplified - could use JWT)"""
        session_data = f"{user_id}:{magic_token}:{datetime.now(timezone.utc).isoformat()}"
        return secrets.token_urlsafe(32)  # Simplified - real implementation would encode session_data
    
    def _verify_session_token(self, session_token: str, email: str) -> bool:
        """Verify session token (simplified implementation)"""
        # This is a simplified implementation
        # In production, you'd want to use JWT or store sessions in database
        return bool(session_token and len(session_token) > 20)
    
    async def _cleanup_expired_links(self, email: str) -> None:
        """Clean up expired links for specific email"""
        try:
            await self.db.delete_expired_magic_links_for_email(email)
        except Exception as e:
            logger.warning(f"Error cleaning up expired links for {email}: {str(e)}")
    
    async def _send_magic_link_email(self, email: str, magic_url: str, expires_minutes: int, 
                                   purpose: str, user_name: str) -> bool:
        """Send magic link email"""
        try:
            if purpose == "key_management":
                subject = "🔑 CongressMCP Key Management Link"
                template_type = "key_management"
            else:
                subject = "🔗 CongressMCP Account Verification"
                template_type = "verification"
            
            # Generate HTML email content
            html_content = self._generate_magic_link_email_html(
                email=email,
                magic_url=magic_url,
                expires_minutes=expires_minutes,
                template_type=template_type,
                user_name=user_name
            )
            
            # Send email using the existing email service
            from resend import Emails
            import resend
            
            if not self.email_service.enabled:
                logger.warning("Email service disabled - cannot send magic link")
                return False
            
            params = {
                "from": self.email_service.from_email,
                "to": [email],
                "subject": subject,
                "html": html_content,
                "tags": [
                    {"name": "category", "value": "magic_link"},
                    {"name": "purpose", "value": purpose}
                ]
            }
            
            email_response = Emails.send(params)
            logger.info(f"Magic link email sent to {email} (ID: {email_response.get('id')})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send magic link email to {email}: {str(e)}")
            return False
    
    def _generate_magic_link_email_html(self, email: str, magic_url: str, expires_minutes: int,
                                      template_type: str, user_name: str) -> str:
        """Generate HTML content for magic link email"""
        
        if template_type == "key_management":
            title = "🔑 Manage Your API Key"
            heading = "Manage Your CongressMCP API Key"
            description = "You requested access to your API key management dashboard. Click the secure link below to view your key details, usage statistics, and regenerate your API key if needed."
        else:
            title = "🔗 Verify Your Account"
            heading = "Verify Your CongressMCP Account"
            description = "Click the secure link below to verify your account and complete your registration."
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
                    line-height: 1.6; 
                    margin: 0; 
                    padding: 0; 
                    background-color: #151c2c;
                    color: rgba(255, 255, 255, 0.8);
                }}
                .email-wrapper {{
                    background: #151c2c;
                    padding: 20px;
                    min-height: 100vh;
                }}
                .container {{ 
                    max-width: 600px; 
                    margin: 0 auto; 
                    background: linear-gradient(108.74deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.02) 50%);
                    border-radius: 12px; 
                    overflow: hidden;
                    box-shadow: 0px 0px 50px -25px rgba(0, 0, 0, 0.5);
                    backdrop-filter: blur(50px);
                    border: 0.5px solid rgba(196, 213, 232, 0.22);
                    position: relative;
                }}
                .header {{ 
                    background: linear-gradient(135deg, #1e293b, #334155); 
                    color: white; 
                    padding: 48px 32px; 
                    text-align: center; 
                    position: relative;
                }}
                .content {{ 
                    padding: 32px; 
                    position: relative;
                    z-index: 10;
                }}
                .footer {{ 
                    background: linear-gradient(108.74deg, rgba(255, 255, 255, 0.04) 0%, rgba(255, 255, 255, 0.01) 100%); 
                    padding: 24px 32px; 
                    border-top: 1px solid rgba(196, 213, 232, 0.22); 
                    color: rgba(255, 255, 255, 0.5); 
                    font-size: 14px; 
                    text-align: center;
                }}
                .glass-card {{ 
                    background: linear-gradient(108.74deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.02) 50%); 
                    border-radius: 12px; 
                    padding: 24px; 
                    margin: 20px 0; 
                    border: 1px solid rgba(196, 213, 232, 0.22);
                    backdrop-filter: blur(30px);
                }}
                .btn-primary {{
                    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
                    color: white !important;
                    padding: 16px 32px;
                    border-radius: 8px;
                    font-weight: 600;
                    text-decoration: none;
                    display: inline-block;
                    transition: all 0.2s ease;
                    border: none;
                    box-shadow: 0 4px 14px rgba(59, 130, 246, 0.25);
                    font-size: 16px;
                }}
                .warning-card {{
                    background: linear-gradient(108.74deg, rgba(245, 158, 11, 0.12) 0%, rgba(245, 158, 11, 0.04) 100%);
                    border: 1px solid rgba(245, 158, 11, 0.3);
                    border-radius: 12px;
                    padding: 20px;
                    margin: 20px 0;
                }}
                .heading-xl {{
                    font-size: 2.25rem;
                    font-weight: 700;
                    line-height: 1.2;
                    color: white;
                    margin: 0;
                }}
                .heading-lg {{
                    font-size: 1.5rem;
                    font-weight: 600;
                    line-height: 1.3;
                    color: white;
                    margin: 0 0 16px 0;
                }}
                .body-lg {{
                    font-size: 1rem;
                    line-height: 1.6;
                    color: rgba(255, 255, 255, 0.8);
                }}
                .body-sm {{
                    font-size: 0.875rem;
                    line-height: 1.5;
                    color: rgba(255, 255, 255, 0.6);
                }}
            </style>
        </head>
        <body>
            <div class="email-wrapper">
                <div class="container">
                    <div class="header">
                        <div style="font-size: 56px; margin-bottom: 16px;">🏛️</div>
                        <h1 class="heading-xl">{heading}</h1>
                        <p style="color: rgba(255,255,255,0.9); font-size: 18px; margin: 8px 0 0 0;">Hi {user_name}!</p>
                    </div>
                    
                    <div class="content">
                        <div style="margin: 24px 0;">
                            <p class="body-lg" style="margin-bottom: 24px;">
                                {description}
                            </p>
                            
                            <div style="text-align: center; margin: 32px 0;">
                                <a href="{magic_url}" class="btn-primary">Manage Your API Key</a>
                            </div>
                            
                            <div class="warning-card">
                                <p style="margin: 0; color: #fbbf24; font-size: 14px;">
                                    <strong>⏰ This link expires in {expires_minutes} minutes</strong><br>
                                    For security reasons, this link can only be used once and will expire automatically.
                                </p>
                            </div>
                        </div>
                        
                        <div class="glass-card">
                            <h3 style="color: #60a5fa; margin: 0 0 16px 0; font-size: 18px;">🔒 Security Notice</h3>
                            <ul style="line-height: 1.6; color: rgba(255, 255, 255, 0.7); margin: 0; padding-left: 20px;">
                                <li>This link is only valid for {expires_minutes} minutes</li>
                                <li>The link can only be used once</li>
                                <li>Never share this link with anyone</li>
                                <li>If you didn't request this, please ignore this email</li>
                            </ul>
                        </div>
                        
                        <div class="glass-card">
                            <p style="margin: 0; font-size: 14px; color: rgba(255, 255, 255, 0.7);">
                                <strong>Can't click the button?</strong> Copy and paste this link into your browser:<br>
                                <span style="word-break: break-all; color: #60a5fa; font-family: monospace; background: rgba(255,255,255,0.05); padding: 8px; border-radius: 4px; display: inline-block; margin-top: 8px;">{magic_url}</span>
                            </p>
                        </div>
                    </div>
                    
                    <div class="footer">
                        <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.5);">Questions? Reply to this email or contact <a href="mailto:support@congressmcp.lawgiver.ai" style="color: #60a5fa; text-decoration: none;">support@congressmcp.lawgiver.ai</a></p>
                        <p style="margin: 0; font-size: 13px;">CongressMCP - AI-powered legislative intelligence</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

# Global magic link service instance
magic_link_service = None

def get_magic_link_service() -> MagicLinkService:
    """Get or create the global magic link service instance"""
    global magic_link_service
    if magic_link_service is None:
        from ..database import db_client  # Use the existing global client
        magic_link_service = MagicLinkService(db_client, email_service)
    return magic_link_service