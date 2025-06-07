# email_service.py
import os
import logging
import resend
from typing import Optional, Dict, Any
from enum import Enum

from ..auth.auth import SubscriptionTier

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
                               api_key: Optional[str], 
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
                                   api_key: Optional[str], 
                                   tier: SubscriptionTier,
                                   user_name: str) -> str:
        """Generate HTML content for welcome email"""
        
        # Feature lists based on tier with updated data
        if tier == SubscriptionTier.PRO:
            features = [
                "✅ <strong>5,000 API calls per month</strong>",
                "✅ <strong>Access to all 116+ congressional tools</strong>",
                "✅ <strong>6 organized tool buckets for easy discovery</strong>",
                "✅ <strong>Bills, votes, members, committees, amendments</strong>",
                "✅ <strong>Congressional Record, hearings, committee reports</strong>",
                "✅ <strong>CRS reports, treaties, nominations</strong>",
                "✅ <strong>Committee intelligence and professional research</strong>",
                "✅ <strong>Priority email support</strong>"
            ]
            tier_badge = """
            <div class="glass-card" style="text-align: center; border: 1px solid rgba(16, 185, 129, 0.3); background: linear-gradient(108.74deg, rgba(16, 185, 129, 0.12) 0%, rgba(16, 185, 129, 0.04) 100%);">
                <div style="font-size: 32px; margin-bottom: 12px;">🎉</div>
                <h3 style="color: #34d399; margin: 0 0 8px 0; font-size: 20px; font-weight: 600;">Pro Features Unlocked!</h3>
                <p style="margin: 0; color: rgba(255,255,255,0.8); font-size: 16px;">Complete congressional intelligence suite with 5,000 monthly API calls</p>
            </div>
            """
            cta_section = """
            <div class="glass-card" style="text-align: center;">
                <h3 style="color: rgba(255,255,255,0.9); margin: 0 0 12px 0;">🚀 Ready to Start?</h3>
                <p class="body-lg" style="margin: 0 0 20px 0;">Get up and running in minutes with our setup guide</p>
                <a href="https://congressmcp.lawgiver.ai/setup" class="btn-primary">View Setup Guide</a>
            </div>
            """
        else:
            features = [
                "✅ <strong>200 API calls per month</strong>",
                "✅ <strong>16 essential congressional tools</strong>",
                "✅ <strong>Bills, members, committees, voting records</strong>",
                "✅ <strong>Congress information and basic search</strong>",
                "✅ <strong>Community email support</strong>"
            ]
            tier_badge = """
            <div class="glass-card" style="text-align: center; border: 1px solid rgba(59, 130, 246, 0.3); background: linear-gradient(108.74deg, rgba(59, 130, 246, 0.12) 0%, rgba(59, 130, 246, 0.04) 100%);">
                <div style="font-size: 32px; margin-bottom: 12px;">🚀</div>
                <h3 style="color: #60a5fa; margin: 0 0 8px 0; font-size: 20px; font-weight: 600;">You're All Set!</h3>
                <p style="margin: 0; color: rgba(255,255,255,0.8); font-size: 16px;">Everything you need to start exploring congressional data with AI</p>
            </div>
            """
            cta_section = """
            <div class="glass-card" style="text-align: center;">
                <h3 style="color: rgba(255,255,255,0.9); margin: 0 0 12px 0;">🚀 Ready to Start?</h3>
                <p class="body-lg" style="margin: 0 0 20px 0;">Get up and running in minutes with our setup guide</p>
                <div style="margin-bottom: 20px;">
                    <a href="https://congressmcp.lawgiver.ai/setup" class="btn-primary">View Setup Guide</a>
                </div>
                <p class="body-sm" style="margin: 0;">
                    Want more tools? <a href="https://congressmcp.lawgiver.ai/pricing" style="color: #34d399; text-decoration: none; font-weight: 600;">Upgrade to Pro</a> for 25x more API calls and all 116+ tools
                </p>
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
                .api-key-box {{ 
                    background: linear-gradient(108.74deg, rgba(255, 255, 255, 0.04) 0%, rgba(255, 255, 255, 0.01) 100%); 
                    border: 1px solid rgba(196, 213, 232, 0.22); 
                    border-radius: 12px; 
                    padding: 24px; 
                    margin: 24px 0; 
                    font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
                    backdrop-filter: blur(20px);
                }}
                .features {{ 
                    list-style: none; 
                    padding: 0; 
                    margin: 0;
                }}
                .features li {{ 
                    margin: 16px 0; 
                    padding: 12px 0;
                    border-bottom: 1px solid rgba(196, 213, 232, 0.1);
                    color: rgba(255, 255, 255, 0.8);
                }}
                .features li:last-child {{ border-bottom: none; }}
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
                .glass-subtle {{
                    background: linear-gradient(108.74deg, rgba(255, 255, 255, 0.04) 0%, rgba(255, 255, 255, 0.01) 100%);
                    border-radius: 8px;
                    padding: 16px;
                    margin: 12px 0;
                    border: 1px solid rgba(196, 213, 232, 0.15);
                    backdrop-filter: blur(20px);
                }}
                .btn-primary {{
                    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
                    color: white;
                    padding: 14px 28px;
                    border-radius: 8px;
                    font-weight: 600;
                    text-decoration: none;
                    display: inline-block;
                    transition: all 0.2s ease;
                    border: none;
                    box-shadow: 0 4px 14px rgba(59, 130, 246, 0.25);
                }}
                .code-block {{ 
                    background: #1e293b; 
                    color: #e2e8f0; 
                    padding: 12px 16px; 
                    border-radius: 8px; 
                    font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; 
                    font-size: 14px;
                    display: inline-block;
                    margin: 8px 0;
                    border: 1px solid rgba(59, 130, 246, 0.2);
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
                .heading-md {{
                    font-size: 1.25rem;
                    font-weight: 600;
                    line-height: 1.4;
                    color: rgba(255, 255, 255, 0.9);
                    margin: 0 0 12px 0;
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
                        <h1 class="heading-xl">Welcome to CongressMCP!</h1>
                        <p style="color: rgba(255,255,255,0.9); font-size: 18px; margin: 8px 0 0 0;">Hi {user_name}! You're now connected to AI-powered legislative intelligence.</p>
                    </div>
                    
                    <div class="content">
                        {"" if not api_key else f'''
                        <div style="margin: 24px 0;">
                            <h2 class="heading-lg">🔑 Your API Key</h2>
                            <div class="api-key-box">
                                <p style="margin: 0 0 12px 0; font-weight: 600; color: rgba(255,255,255,0.9);">Your Personal API Key:</p>
                                <code style="background: rgba(255,255,255,0.05); padding: 12px; border-radius: 6px; display: block; word-break: break-all; border: 1px solid rgba(196, 213, 232, 0.22); font-size: 13px; color: #e2e8f0;">{api_key}</code>
                            </div>
                            <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 12px;">
                                <p style="margin: 0; color: #fca5a5; font-size: 14px;"><strong>⚠️ Security Notice:</strong> Keep this key secure and never share it publicly!</p>
                            </div>
                        </div>
                        '''}
                        
                        {tier_badge}
                        
                        <div style="margin: 32px 0;">
                            <h2 class="heading-lg">📋 Your Plan Features</h2>
                            <ul class="features">
                                {"".join(f'<li>{feature}</li>' for feature in features)}
                            </ul>
                        </div>
                        
                        {cta_section}
                        
                        <div style="margin: 32px 0;">
                            <h2 class="heading-lg">🚀 Quick Start (3 steps)</h2>
                            
                            <div class="glass-subtle">
                                <h3 class="heading-md">1. Install the NPM package</h3>
                                <div class="code-block">npm install -g congressmcp</div>
                            </div>
                            
                            <div class="glass-subtle">
                                <h3 class="heading-md">2. Configure Claude Desktop</h3>
                                <p class="body-sm">Add CongressMCP to your Claude Desktop MCP settings with your API key</p>
                            </div>
                            
                            <div class="glass-subtle">
                                <h3 class="heading-md">3. Start exploring</h3>
                                <p class="body-sm">Ask Claude: "What bills were introduced this week?" or "Show me the House Intelligence Committee members"</p>
                            </div>
                        </div>
                        
                        <div class="glass-card" style="border-left: 4px solid #3b82f6;">
                            <h3 style="color: #60a5fa; margin: 0 0 12px 0; font-size: 16px;">💡 Pro Tip</h3>
                            <p class="body-sm">Try asking Claude about current legislation, member voting records, or committee activities. CongressMCP provides real-time access to Congress.gov data through AI.</p>
                        </div>
                        
                        <div style="margin: 32px 0;">
                            <h2 class="heading-lg">📚 Resources</h2>
                            <div style="display: grid; gap: 12px;">
                                <a href="https://congressmcp.lawgiver.ai/setup" class="glass-subtle" style="display: block; text-decoration: none; color: rgba(255,255,255,0.9); transition: all 0.2s ease;">
                                    <strong>📖 Setup Guide</strong><br>
                                    <span class="body-sm">Step-by-step installation instructions</span>
                                </a>
                                <a href="https://congressmcp.lawgiver.ai/examples" class="glass-subtle" style="display: block; text-decoration: none; color: rgba(255,255,255,0.9); transition: all 0.2s ease;">
                                    <strong>💡 Usage Examples</strong><br>
                                    <span class="body-sm">Sample queries and use cases</span>
                                </a>
                                <a href="mailto:support@congressmcp.lawgiver.ai" class="glass-subtle" style="display: block; text-decoration: none; color: rgba(255,255,255,0.9); transition: all 0.2s ease;">
                                    <strong>✉️ Email Support</strong><br>
                                    <span class="body-sm">Get help from our team</span>
                                </a>
                            </div>
                        </div>
                    </div>
                    
                    <div class="footer">
                        <p style="margin: 0 0 8px 0;">Questions? Reply to this email or contact <a href="mailto:support@congressmcp.lawgiver.ai" style="color: #60a5fa; text-decoration: none;">support@congressmcp.lawgiver.ai</a></p>
                        <p style="margin: 0; font-size: 13px;">CongressMCP - AI-powered legislative intelligence through the Model Context Protocol</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _generate_upgrade_email_html(self,
                                   user_email: str,
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
                    background: linear-gradient(135deg, #059669, #10b981); 
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
                .api-key-box {{ 
                    background: linear-gradient(108.74deg, rgba(16, 185, 129, 0.08) 0%, rgba(16, 185, 129, 0.02) 100%); 
                    border: 1px solid rgba(16, 185, 129, 0.3); 
                    border-radius: 12px; 
                    padding: 24px; 
                    margin: 24px 0; 
                    font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
                    backdrop-filter: blur(20px);
                }}
                .glass-card {{ 
                    background: linear-gradient(108.74deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.02) 50%); 
                    border-radius: 12px; 
                    padding: 24px; 
                    margin: 20px 0; 
                    border: 1px solid rgba(196, 213, 232, 0.22);
                    backdrop-filter: blur(30px);
                }}
                .glass-subtle {{
                    background: linear-gradient(108.74deg, rgba(255, 255, 255, 0.04) 0%, rgba(255, 255, 255, 0.01) 100%);
                    border-radius: 8px;
                    padding: 16px;
                    margin: 12px 0;
                    border: 1px solid rgba(196, 213, 232, 0.15);
                    backdrop-filter: blur(20px);
                }}
                .features {{ 
                    list-style: none; 
                    padding: 0; 
                    margin: 0;
                }}
                .features li {{ 
                    margin: 16px 0; 
                    padding: 12px 0;
                    border-bottom: 1px solid rgba(196, 213, 232, 0.1);
                    color: rgba(255, 255, 255, 0.8);
                }}
                .features li:last-child {{ border-bottom: none; }}
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
            </style>
        </head>
        <body>
            <div class="email-wrapper">
                <div class="container">
                    <div class="header">
                        <div style="font-size: 56px; margin-bottom: 16px;">🎉</div>
                        <h1 class="heading-xl">Upgrade Complete!</h1>
                        <p style="color: rgba(255,255,255,0.9); font-size: 18px; margin: 8px 0 0 0;">Hi {user_name}, welcome to CongressMCP {tier.value.title()}!</p>
                    </div>
                    
                    <div class="content">
                        <div class="glass-card" style="border: 1px solid rgba(16, 185, 129, 0.3); background: linear-gradient(108.74deg, rgba(16, 185, 129, 0.12) 0%, rgba(16, 185, 129, 0.04) 100%);">
                            <h3 style="color: #34d399; margin: 0 0 12px 0; font-size: 18px;">🔄 New API Key Required</h3>
                            <p class="body-lg">Your subscription has been upgraded! Please use your new API key below to access your enhanced features.</p>
                        </div>
                        
                        <div style="margin: 32px 0;">
                            <h2 class="heading-lg">🔑 Your New API Key</h2>
                            <div class="api-key-box">
                                <p style="margin: 0 0 12px 0; font-weight: 600; color: #34d399;">Your Updated API Key:</p>
                                <code style="background: rgba(255,255,255,0.05); padding: 12px; border-radius: 6px; display: block; word-break: break-all; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 13px; color: #e2e8f0;">{api_key}</code>
                            </div>
                            <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 12px;">
                                <p style="margin: 0; color: #fca5a5; font-size: 14px;"><strong>⚠️ Update your configuration with this new key!</strong></p>
                            </div>
                        </div>
                        
                        <div style="margin: 32px 0;">
                            <h2 class="heading-lg">🚀 Your New Pro Features</h2>
                            <ul class="features">
                                <li>✅ <strong>5,000 API calls per month</strong> (up from 200)</li>
                                <li>✅ <strong>Access to all 116+ congressional tools</strong></li>
                                <li>✅ <strong>6 organized tool buckets for easy discovery</strong></li>
                                <li>✅ <strong>Bills, Members, Committees, Votes, Amendments</strong></li>
                                <li>✅ <strong>Congressional Record, Hearings, Reports</strong></li>
                                <li>✅ <strong>CRS Reports, Treaties, Nominations</strong></li>
                                <li>✅ <strong>Committee intelligence and professional research</strong></li>
                                <li>✅ <strong>Priority email support</strong></li>
                            </ul>
                        </div>
                        
                        <div style="margin: 32px 0;">
                            <h2 class="heading-lg">🔧 Next Steps</h2>
                            
                            <div class="glass-subtle">
                                <h3 style="color: rgba(255,255,255,0.9); margin: 0 0 8px 0; font-size: 16px;">1. Update your API key</h3>
                                <p style="margin: 0; color: rgba(255,255,255,0.7); font-size: 14px;">Replace your old API key with the new one above in your Claude Desktop MCP settings</p>
                            </div>
                            
                            <div class="glass-subtle">
                                <h3 style="color: rgba(255,255,255,0.9); margin: 0 0 8px 0; font-size: 16px;">2. Restart Claude Desktop</h3>
                                <p style="margin: 0; color: rgba(255,255,255,0.7); font-size: 14px;">Close and reopen Claude Desktop for the changes to take effect</p>
                            </div>
                            
                            <div class="glass-subtle">
                                <h3 style="color: rgba(255,255,255,0.9); margin: 0 0 8px 0; font-size: 16px;">3. Start exploring</h3>
                                <p style="margin: 0; color: rgba(255,255,255,0.7); font-size: 14px;">Try asking Claude about congressional data with your enhanced access!</p>
                            </div>
                        </div>
                        
                        <div class="glass-card" style="border-left: 4px solid #34d399;">
                            <h3 style="color: #34d399; margin: 0 0 16px 0; font-size: 18px;">💡 Pro Tips</h3>
                            <ul style="line-height: 1.6; color: rgba(255, 255, 255, 0.7); margin: 0; padding-left: 20px;">
                                <li>📊 Access voting records with enhanced tools</li>
                                <li>📄 Search Congressional Record entries</li>
                                <li>🎧 Browse committee hearings and reports</li>
                                <li>📚 Access CRS research reports</li>
                                <li>🔍 Use committee intelligence features</li>
                            </ul>
                        </div>
                    </div>
                    
                    <div class="footer">
                        <p style="margin: 0 0 8px 0;">Questions about your upgrade? Reply to this email or contact <a href="mailto:support@congressmcp.lawgiver.ai" style="color: #60a5fa; text-decoration: none;">support@congressmcp.lawgiver.ai</a></p>
                        <p style="margin: 0; font-size: 13px;">Thank you for upgrading to CongressMCP Pro! 🏛️</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

    async def send_payment_failed_email(self,
                                       email: str,
                                       tier: SubscriptionTier,
                                       user_name: Optional[str] = None) -> bool:
        """Send payment failed notification email"""
        if not self.enabled:
            logger.warning(f"Email service disabled - cannot send payment failed email to {email}")
            return False
        
        try:
            subject = "🚨 CongressMCP Payment Failed - Action Required"
            
            html_content = self._generate_payment_failed_email_html(
                email=email,
                tier=tier,
                user_name=user_name or email.split('@')[0]
            )
            
            params = {
                "from": self.from_email,
                "to": [email],
                "subject": subject,
                "html": html_content,
                "tags": [
                    {"name": "category", "value": "payment_failed"},
                    {"name": "tier", "value": tier.value}
                ]
            }
            
            email_response = resend.Emails.send(params)
            
            if email_response:
                logger.info(f"Payment failed email sent successfully to {email} (ID: {email_response.get('id')})")
                return True
            else:
                logger.error(f"Failed to send payment failed email to {email}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending payment failed email to {email}: {e}")
            return False

    def _generate_payment_failed_email_html(self, 
                                           email: str, 
                                           tier: SubscriptionTier,
                                           user_name: str) -> str:
        """Generate HTML content for payment failed email"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>CongressMCP Payment Failed</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #dc3545 0%, #c82333 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; text-align: center; }}
                .content {{ padding: 30px; line-height: 1.6; color: #333333; }}
                .footer {{ background-color: #f8f9fa; padding: 20px; border-radius: 0 0 8px 8px; text-align: center; color: #6c757d; font-size: 14px; }}
                .button {{ display: inline-block; background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 10px 0; }}
                .alert {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚨 Payment Failed</h1>
                    <p>Action required for your CongressMCP subscription</p>
                </div>
                
                <div class="content">
                    <p>Hi {user_name},</p>
                    
                    <div class="alert">
                        <strong>Payment Failed:</strong> We were unable to process payment for your CongressMCP {tier.value.title()} subscription.
                    </div>
                    
                    <p>We'll automatically retry your payment in the next few days. To avoid any service interruption, please:</p>
                    
                    <ol>
                        <li>Check that your payment method is up to date in your Stripe customer portal</li>
                        <li>Ensure sufficient funds are available</li>
                        <li>Contact your bank if the payment method should be valid</li>
                    </ol>
                    
                    <p style="text-align: center;">
                        <a href="https://billing.stripe.com/p/login/test_00000000000000" class="button">Update Payment Method</a>
                    </p>
                    
                    <p>If you continue to experience issues, please don't hesitate to reach out to our support team.</p>
                    
                    <p>Best regards,<br>The CongressMCP Team</p>
                </div>
                
                <div class="footer">
                    <p>Questions? Contact <a href="mailto:support@congressmcp.lawgiver.ai">support@congressmcp.lawgiver.ai</a></p>
                    <p>CongressMCP - AI-powered legislative intelligence</p>
                </div>
            </div>
        </body>
        </html>
        """

# Create global email service instance
email_service = EmailService()
