
# 🔐 Lawgiver MCP Server – Authentication & Stripe Integration Summary

**Date**: June 1, 2025  
**Context**: Lawgiver has deployed a production-grade MCP server architecture to deliver AI-native access to legislative data. With monetization and access control now a priority, this document summarizes the finalized authentication and billing model.

---

## ✅ Key Conclusions

### 1. OAuth2 Not Needed
- While FastMCP supports OAuth2, MCP clients like Claude Desktop and Continue **cannot perform browser-based OAuth flows**.
- Therefore, **OAuth2 is not suitable** for your current agent-compatible architecture.
- Instead, **API key or JWT authentication** provides a secure, agent-compatible solution.

### 2. Auth Architecture Overview
- Each user is issued a **Lawgiver API key** or **JWT**, tied to their account and subscription tier.
- MCP clients pass this key via environment variables or initial prompts.
- Your **Node.js bridge** injects the token into an HTTP `Authorization: Bearer <token>` header.
- The **ASGI FastMCP server** includes middleware that:
  - Validates the token
  - Checks user tier (free, pro, etc.)
  - Enforces feature access and rate limits
- User and token metadata are stored in **PostgreSQL or Supabase**.

### 3. Dual Key Requirement
- Users must also supply a **Congress.gov API key**, since your system directly calls the official Congress API.
- Two approaches:
  - **Recommended**: User provides their own Congress key via `.env` or config
  - **Alternative**: Proxy a shared Congress key from the backend (risk: quota limits, abuse)

### 4. Stripe Integration Directly Affects API Key Issuance
- Stripe manages user subscriptions and billing tiers.
- Upon successful checkout:
  - A **Stripe webhook** updates the user’s record in your database
  - A **new API key or JWT** is generated with **encoded subscription tier metadata**
- API key or token payload reflects:
  - Tier (free, pro, enterprise)
  - Rate limit thresholds
  - Feature access rights
  - (Optional) Expiry timestamps
- If a subscription is canceled or lapses, the key is invalidated or downgraded.

### 5. Agent-Compatible Monetization
- This entire flow works **seamlessly with Claude, Continue, and other MCP clients**.
- No need for OAuth, no UI changes — just configuration of `.env` with:

  ```bash
  LAW_API_KEY=lawgiver-abc123
  CONGRESS_API_KEY=congress-xyz789
  ```

- Monetization and feature access are **enforced entirely server-side**, based on the decoded API key.

---

## 🔧 Implementation Checklist

- [ ] Create Stripe Checkout flow  
- [ ] Implement Stripe webhooks to update user tiers  
- [ ] Generate/refresh API keys or JWTs post-payment  
- [ ] Update FastAPI middleware to validate tokens and check encoded tier  
- [ ] Add tier-based rate limiting and access controls  
- [ ] Update Node.js bridge to inject `Authorization` header  
- [ ] Document `.env` usage for end users (MCP + Congress keys)
