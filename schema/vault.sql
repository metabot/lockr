-- Lockr Vault Database Schema
-- This schema must be identical across all language implementations
-- to ensure vault file compatibility

-- Secrets table: Core key-value storage
CREATE TABLE IF NOT EXISTS secrets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL COLLATE NOCASE,    -- Case-insensitive unique keys
    value TEXT NOT NULL,                         -- Encrypted secret value
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    tags TEXT,                                   -- Future: comma-separated tags
    notes TEXT                                   -- Future: additional notes
);

-- Authentication attempts log
CREATE TABLE IF NOT EXISTS auth_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    username TEXT NOT NULL,
    success BOOLEAN DEFAULT FALSE,
    ip_address TEXT,                             -- Future: network info
    session_id TEXT                              -- Future: session tracking
);

-- Session management
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_secrets_key ON secrets(key COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_secrets_created ON secrets(created_at);
CREATE INDEX IF NOT EXISTS idx_secrets_accessed ON secrets(last_accessed);
CREATE INDEX IF NOT EXISTS idx_auth_timestamp ON auth_attempts(timestamp);
CREATE INDEX IF NOT EXISTS idx_auth_username ON auth_attempts(username);
CREATE INDEX IF NOT EXISTS idx_sessions_id ON sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- Version information for future migrations
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial schema version
INSERT OR IGNORE INTO schema_version (version) VALUES (1);