CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    platform TEXT NOT NULL,
    encrypted_session BYTEA NOT NULL,
    encryption_key_id TEXT NOT NULL,
    status TEXT NOT NULL,
    expires_at TIMESTAMP,
    last_checked_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    UNIQUE(user_id, platform)
);

CREATE TABLE IF NOT EXISTS connect_tokens (
    id UUID PRIMARY KEY,
    token_hash TEXT UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    platform TEXT NOT NULL,
    used_at TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS download_jobs (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    telegram_chat_id BIGINT NOT NULL,
    platform TEXT,
    url TEXT NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS download_results (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES download_jobs(id),
    media_type TEXT NOT NULL,
    file_path TEXT,
    file_size BIGINT,
    mime_type TEXT,
    telegram_file_id TEXT,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    event_type TEXT NOT NULL,
    platform TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_telegram_user_id ON users (telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_platform ON user_sessions (user_id, platform);
CREATE INDEX IF NOT EXISTS idx_download_jobs_user_created_at ON download_jobs (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_download_jobs_status ON download_jobs (status);
CREATE INDEX IF NOT EXISTS idx_connect_tokens_token_hash ON connect_tokens (token_hash);
CREATE INDEX IF NOT EXISTS idx_connect_tokens_expires_at ON connect_tokens (expires_at);
