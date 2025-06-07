-- Magic Links Table Update for CongressMCP
-- Run this in your Supabase SQL Editor to add magic links functionality

-- Magic links table for passwordless authentication
CREATE TABLE IF NOT EXISTS magic_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    is_used BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    purpose VARCHAR(50) DEFAULT 'key_management' CHECK (purpose IN ('key_management', 'registration')),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for magic links performance
CREATE INDEX IF NOT EXISTS idx_magic_links_token ON magic_links(token);
CREATE INDEX IF NOT EXISTS idx_magic_links_email ON magic_links(email);
CREATE INDEX IF NOT EXISTS idx_magic_links_expires ON magic_links(expires_at);
CREATE INDEX IF NOT EXISTS idx_magic_links_user_id ON magic_links(user_id);

-- Enable Row Level Security for magic_links
ALTER TABLE magic_links ENABLE ROW LEVEL SECURITY;

-- Service role can access all magic_links data
CREATE POLICY "Service role can access all magic_links" ON magic_links
    FOR ALL USING (auth.role() = 'service_role');