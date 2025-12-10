-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),  -- NULL for SSO users
    auth_provider VARCHAR(50) NOT NULL,  -- 'google', 'apple', 'email'
    auth_provider_id VARCHAR(255),  -- External ID from OAuth
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Devices table
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_code VARCHAR(20) UNIQUE NOT NULL,  -- e.g., 'PD-7X4K9M'
    device_secret VARCHAR(255) NOT NULL,  -- For device authentication
    owner_id UUID REFERENCES users(id),  -- NULL until claimed
    friendly_name VARCHAR(255) DEFAULT 'My PaperDrop',
    status VARCHAR(50) DEFAULT 'setup_pending',  -- setup_pending, online, offline
    firmware_version VARCHAR(50),
    last_seen_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Device access (who can send to which device)
CREATE TABLE device_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'sender',  -- 'owner' or 'sender'
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(device_id, user_id)
);

-- Messages table
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_id UUID NOT NULL REFERENCES users(id),
    device_id UUID NOT NULL REFERENCES devices(id),
    content_type VARCHAR(50) NOT NULL,  -- 'text', 'image', 'template'
    content JSONB NOT NULL,  -- Structured content based on type
    status VARCHAR(50) DEFAULT 'queued',  -- queued, sent, printed, failed
    error_message TEXT,
    scheduled_at TIMESTAMP,  -- NULL = send immediately
    sent_at TIMESTAMP,
    printed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Templates table (for future use)
CREATE TABLE templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    layout JSONB NOT NULL,  -- Template definition
    is_system BOOLEAN DEFAULT FALSE,  -- System vs user-created
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Automations table (for future use)
CREATE TABLE automations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    device_id UUID NOT NULL REFERENCES devices(id),
    name VARCHAR(255) NOT NULL,
    trigger_type VARCHAR(50) NOT NULL,  -- 'schedule', 'webhook', etc.
    trigger_config JSONB NOT NULL,
    action_config JSONB NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_messages_device_status ON messages(device_id, status);
CREATE INDEX idx_messages_scheduled ON messages(scheduled_at) WHERE scheduled_at IS NOT NULL AND status = 'queued';
CREATE INDEX idx_device_access_user ON device_access(user_id);
CREATE INDEX idx_devices_code ON devices(device_code);
