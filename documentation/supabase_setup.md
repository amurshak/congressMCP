# Supabase Database Setup Guide

This guide walks you through setting up the Supabase database for the Congressional MCP server's authentication and subscription management system.

## Prerequisites

1. A Supabase account (sign up at https://supabase.com)
2. Python environment with the Congressional MCP dependencies installed

## Step 1: Create a New Supabase Project

1. Go to https://app.supabase.com
2. Click "New project"
3. Choose your organization
4. Enter project details:
   - **Name**: `congressional-mcp` (or your preferred name)
   - **Database Password**: Generate a strong password and save it securely
   - **Region**: Choose the region closest to your users
5. Click "Create new project"

## Step 2: Get Your Supabase Credentials

Once your project is created, you'll need these credentials:

1. **Project URL**: Found in Settings > API > Project URL
2. **Anon Key**: Found in Settings > API > Project API keys > anon/public
3. **Service Role Key**: Found in Settings > API > Project API keys > service_role (click "Reveal" to see it)

## Step 3: Set Up Environment Variables

Update your `.env.development` and `.env.production` files with your Supabase credentials:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here
SUPABASE_SERVICE_KEY=your-service-role-key-here
ENABLE_DATABASE=true
```

**Important Security Notes:**
- The **service role key** bypasses Row Level Security (RLS) and should only be used server-side
- Never expose the service role key in client-side code
- Keep all keys secure and rotate them if compromised

## Step 4: Create Database Schema

1. Go to your Supabase project dashboard
2. Navigate to "SQL Editor" in the left sidebar
3. Copy the contents of `supabase_schema.sql` from the project root
4. Paste it into the SQL editor
5. Click "Run" to execute the schema

This will create:
- `users` table for user account management
- `api_keys` table for API key storage and validation
- `usage_tracking` table for rate limiting and analytics
- Necessary indexes for performance
- Row Level Security (RLS) policies for data protection
- Triggers for automatic timestamp updates

## Step 5: Verify Database Setup

You can verify the setup by running this test query in the SQL Editor:

```sql
-- Check that tables were created
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('users', 'api_keys', 'usage_tracking');
```

You should see all three tables listed.

## Step 6: Test the Connection

Run the Congressional MCP server in development mode to test the database connection:

```bash
# Make sure your .env.development file has the correct Supabase credentials
python congress_api/main.py
```

Check the logs for a successful connection message:
```
INFO: Connected to Supabase database
```

## Step 7: Configure Stripe Price IDs (Production)

When you're ready for production, update the price ID mappings in `congress_api/core/user_service.py`:

```python
STRIPE_PRICE_TO_TIER = {
    "price_1234567890": SubscriptionTier.FREE,      # Replace with actual Stripe price ID
    "price_1234567891": SubscriptionTier.PRO,       # Replace with actual Stripe price ID  
    "price_1234567892": SubscriptionTier.ENTERPRISE # Replace with actual Stripe price ID
}
```

## Troubleshooting

### Connection Issues

If you see "Failed to connect to Supabase" errors:

1. **Check credentials**: Verify URL and service key are correct
2. **Network access**: Ensure your server can reach supabase.co
3. **Project status**: Confirm your Supabase project is active and not paused

### Schema Issues

If table creation fails:

1. **Permissions**: Ensure you're using the service role key, not the anon key
2. **Syntax**: Check for any SQL syntax errors in the schema file
3. **Existing tables**: Drop existing tables if you're re-running the schema

### Authentication Issues

If API key validation fails:

1. **Database enabled**: Verify `ENABLE_DATABASE=true` in environment
2. **Schema applied**: Confirm all tables exist and have proper structure
3. **RLS policies**: Check that Row Level Security policies are correctly applied

## Database Schema Overview

### Users Table
- Stores user account information
- Links to Stripe customer IDs
- Tracks subscription tiers and status

### API Keys Table  
- Stores hashed API keys for security
- Associates keys with users and subscription tiers
- Tracks key creation and last usage

### Usage Tracking Table
- Records API usage for rate limiting
- Enables usage analytics and reporting
- Supports tier-based feature access control

## Security Considerations

1. **Row Level Security**: All tables have RLS enabled to protect user data
2. **Key Hashing**: API keys are stored as SHA-256 hashes, not plaintext
3. **Service Role Usage**: Database operations use the service role for admin access
4. **Environment Separation**: Use different Supabase projects for development and production

## Next Steps

After completing this setup:

1. Test user creation and API key generation via Stripe webhooks
2. Verify rate limiting and feature access controls
3. Set up monitoring and alerts for database health
4. Configure backup and disaster recovery procedures

For additional help, consult the [Supabase documentation](https://supabase.com/docs) or the Congressional MCP project documentation.
