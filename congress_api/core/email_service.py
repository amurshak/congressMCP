# email_service.py
import os
import logging
import resend
from typing import Optional, Dict, Any
from enum import Enum

from .auth import SubscriptionTier

# Configure logger
logger = logging.getLogger(__name__)

class EmailTemplate(Enum):
    """Email template types"""
    WELCOME_FREE = "welcome_free"
    WELCOME_PRO = "welcome_pro"
    UPGRADE_PRO = "upgrade_pro"
    API_KEY_GENERATED = "api_key_generated"

class EmailService:
    """Email service for CongressMCP using Resend"""
    
    def __init__(self):
        self.api_key = os.getenv("RESEND_API_KEY")
        self.from_email = os.getenv("RESEND_FROM_EMAIL", "CongressMCP <noreply@congressmcp.com>")
        self.enabled = bool(self.api_key)
        
        if not self.enabled:
            logger.warning("Email service disabled - RESEND_API_KEY not configured")
        else:
            resend.api_key = self.api_key
            logger.info("Email service initialized with Resend")
    
    async def send_welcome_email(self, 
                               email: str, 
                               api_key: str, 
                               tier: SubscriptionTier,
                               user_name: Optional[str] = None) -> bool:
        """Send welcome email with API key to new user"""
        if not self.enabled:
            logger.warning(f"Email service disabled - cannot send welcome email to {email}")
            return False
        
        try:
            # Choose template based on tier
            if tier == SubscriptionTier.PRO:
                template = EmailTemplate.WELCOME_PRO
                subject = "🎉 Welcome to CongressMCP Pro!"
            else:
                template = EmailTemplate.WELCOME_FREE
                subject = "🎉 Welcome to CongressMCP!"
            
            # Generate email content
            html_content = self._generate_welcome_email_html(
                email=email,
                api_key=api_key,
                tier=tier,
                user_name=user_name or email.split('@')[0]
            )
            
            # Send email
            params = {
                "from": self.from_email,
                "to": [email],
                "subject": subject,
                "html": html_content,
                "tags": [
                    {"name": "category", "value": "welcome"},
                    {"name": "tier", "value": tier.value}
                ]
            }
            
            email_response = resend.Emails.send(params)
            logger.info(f"Welcome email sent successfully to {email} (ID: {email_response.get('id')})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send welcome email to {email}: {str(e)}")
            return False
    
    async def send_upgrade_email(self,
                               email: str,
                               new_api_key: str,
                               new_tier: SubscriptionTier,
                               user_name: Optional[str] = None) -> bool:
        """Send upgrade notification email with new API key"""
        if not self.enabled:
            logger.warning(f"Email service disabled - cannot send upgrade email to {email}")
            return False
        
        try:
            subject = f"🚀 CongressMCP Upgrade Complete - Welcome to {new_tier.value.title()}!"
            
            html_content = self._generate_upgrade_email_html(
                email=email,
                api_key=new_api_key,
                tier=new_tier,
                user_name=user_name or email.split('@')[0]
            )
            
            params = {
                "from": self.from_email,
                "to": [email],
                "subject": subject,
                "html": html_content,
                "tags": [
                    {"name": "category", "value": "upgrade"},
                    {"name": "new_tier", "value": new_tier.value}
                ]
            }
            
            email_response = resend.Emails.send(params)
            logger.info(f"Upgrade email sent successfully to {email} (ID: {email_response.get('id')})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send upgrade email to {email}: {str(e)}")
            return False
    
    def _generate_welcome_email_html(self, 
                                   email: str, 
                                   api_key: str, 
                                   tier: SubscriptionTier,
                                   user_name: str) -> str:
        """Generate HTML content for welcome email"""
        
        # Feature lists based on tier
        if tier == SubscriptionTier.PRO:
            features = [
                "✅ <strong>5,000 API calls per month</strong>",
                "✅ <strong>Access to all 23+ tool categories</strong>",
                "✅ <strong>Bills, Members, Committees, Votes, Amendments</strong>",
                "✅ <strong>Congressional Record, Hearings, Reports</strong>",
                "✅ <strong>CRS Reports, Treaties, Nominations</strong>",
                "✅ <strong>Standard email support</strong>"
            ]
            setup_note = """
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #28a745; margin-top: 0;">🎉 Pro Features Unlocked!</h3>
                <p style="margin-bottom: 0;">You now have access to our complete congressional data suite with 5,000 monthly API calls.</p>
            </div>
            """
        else:
            features = [
                "✅ <strong>200 API calls per month</strong>",
                "✅ <strong>Basic tools: Bills, Members, Committees</strong>",
                "✅ <strong>Congress information and search</strong>",
                "✅ <strong>Email support</strong>"
            ]
            setup_note = """
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #17a2b8; margin-top: 0;">🚀 Ready to Upgrade?</h3>
                <p style="margin-bottom: 10px;">Need more API calls or access to all tools?</p>
                <a href="https://congressmcp.com" style="display: inline-block; background: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">Upgrade to Pro →</a>
            </div>
            """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Welcome to CongressMCP</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .api-key-box {{ background: #f8f9fa; border: 2px solid #e9ecef; border-radius: 8px; padding: 20px; margin: 20px 0; font-family: monospace; }}
                .features {{ list-style: none; padding: 0; }}
                .features li {{ margin: 10px 0; }}
                .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #e9ecef; color: #6c757d; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="color: #2c3e50; margin-bottom: 10px;">🏛️ Welcome to CongressMCP!</h1>
                    <p style="color: #6c757d; font-size: 18px;">Hi {user_name}, your congressional data API is ready!</p>
                </div>
                
                <div style="margin: 30px 0;">
                    <h2 style="color: #495057;">🔑 Your API Key</h2>
                    <div class="api-key-box">
                        <p style="margin: 0 0 10px 0; font-weight: bold;">Your Personal API Key:</p>
                        <code style="background: #fff; padding: 10px; border-radius: 4px; display: block; word-break: break-all; border: 1px solid #dee2e6;">{api_key}</code>
                    </div>
                    <p style="color: #dc3545; margin: 10px 0;"><strong>⚠️ Keep this key secure and never share it publicly!</strong></p>
                </div>
                
                {setup_note}
                
                <div style="margin: 30px 0;">
                    <h2 style="color: #495057;">📋 Your Plan Features</h2>
                    <ul class="features">
                        {"".join(f'<li>{feature}</li>' for feature in features)}
                    </ul>
                </div>
                
                <div style="margin: 30px 0;">
                    <h2 style="color: #495057;">🚀 Quick Start Guide</h2>
                    <ol style="line-height: 1.6;">
                        <li><strong>Install the NPM package:</strong><br>
                            <code style="background: #f8f9fa; padding: 5px 10px; border-radius: 4px;">npm install -g congressional-mcp</code>
                        </li>
                        <li><strong>Configure Claude Desktop:</strong><br>
                            Add CongressMCP to your Claude Desktop MCP settings with your API key
                        </li>
                        <li><strong>Start using:</strong><br>
                            Ask Claude about bills, members, committees, and more!
                        </li>
                    </ol>
                </div>
                
                <div style="margin: 30px 0;">
                    <h2 style="color: #495057;">📚 Setup Guide & Support</h2>
                    <ul style="line-height: 1.6;">
                        <li><a href="https://github.com/your-repo/CongressionalMCP">📖 Setup Guide</a></li>
                        <li><a href="https://congressmcp.com/examples">💡 Usage Examples</a></li>
                        <li><a href="mailto:support@congressmcp.lawgiver.ai">✉️ Email Support</a></li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p>Questions? Reply to this email or contact <a href="mailto:support@congressmcp.lawgiver.ai">support@congressmcp.lawgiver.ai</a></p>
                    <p>CongressMCP - Access congressional data through the Model Context Protocol</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _generate_upgrade_email_html(self,
                                   email: str,
                                   api_key: str,
                                   tier: SubscriptionTier,
                                   user_name: str) -> str:
        """Generate HTML content for upgrade email"""
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>CongressMCP Upgrade Complete</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .api-key-box {{ background: #d4edda; border: 2px solid #c3e6cb; border-radius: 8px; padding: 20px; margin: 20px 0; font-family: monospace; }}
                .features {{ list-style: none; padding: 0; }}
                .features li {{ margin: 10px 0; }}
                .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #e9ecef; color: #6c757d; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="color: #28a745; margin-bottom: 10px;">🎉 Upgrade Complete!</h1>
                    <p style="color: #6c757d; font-size: 18px;">Hi {user_name}, welcome to CongressMCP {tier.value.title()}!</p>
                </div>
                
                <div style="background: #d1ecf1; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #0c5460; margin-top: 0;">🔄 New API Key Required</h3>
                    <p style="margin-bottom: 0;">Your subscription has been upgraded! Please use your new API key below to access your enhanced features.</p>
                </div>
                
                <div style="margin: 30px 0;">
                    <h2 style="color: #495057;">🔑 Your New API Key</h2>
                    <div class="api-key-box">
                        <p style="margin: 0 0 10px 0; font-weight: bold;">Your Updated API Key:</p>
                        <code style="background: #fff; padding: 10px; border-radius: 4px; display: block; word-break: break-all; border: 1px solid #dee2e6;">{api_key}</code>
                    </div>
                    <p style="color: #dc3545; margin: 10px 0;"><strong>⚠️ Update your configuration with this new key!</strong></p>
                </div>
                
                <div style="margin: 30px 0;">
                    <h2 style="color: #495057;">🚀 Your New Pro Features</h2>
                    <ul class="features">
                        <li>✅ <strong>5,000 API calls per month</strong> (up from 200)</li>
                        <li>✅ <strong>Access to all 23+ tool categories</strong></li>
                        <li>✅ <strong>Bills, Members, Committees, Votes, Amendments</strong></li>
                        <li>✅ <strong>Congressional Record, Hearings, Reports</strong></li>
                        <li>✅ <strong>CRS Reports, Treaties, Nominations</strong></li>
                        <li>✅ <strong>Standard email support</strong></li>
                    </ul>
                </div>
                
                <div style="margin: 30px 0;">
                    <h2 style="color: #495057;">🔧 Next Steps</h2>
                    <ol style="line-height: 1.6;">
                        <li><strong>Update your API key:</strong><br>
                            Replace your old API key with the new one above in your Claude Desktop MCP settings
                        </li>
                        <li><strong>Restart Claude Desktop:</strong><br>
                            Close and reopen Claude Desktop for the changes to take effect
                        </li>
                        <li><strong>Start exploring:</strong><br>
                            Try asking Claude about congressional data with your enhanced access!
                        </li>
                    </ol>
                </div>
                
                <div style="margin: 30px 0;">
                    <h2 style="color: #495057;">💡 Pro Tips</h2>
                    <ul style="line-height: 1.6;">
                        <li>📊 Access voting records with the new <code>votes</code> tools</li>
                        <li>📄 Search Congressional Record entries</li>
                        <li>🎧 Browse committee hearings and reports</li>
                        <li>📚 Access CRS research reports</li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p>Questions about your upgrade? Reply to this email or contact <a href="mailto:support@congressmcp.lawgiver.ai">support@congressmcp.lawgiver.ai</a></p>
                    <p>Thank you for upgrading to CongressMCP Pro! 🏛️</p>
                </div>
            </div>
        </body>
        </html>
        """

# Create global email service instance
email_service = EmailService()
