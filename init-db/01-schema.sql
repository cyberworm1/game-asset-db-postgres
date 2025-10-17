-- Schema for Game Asset Management
-- Author: [Your Name]
-- Description: Defines tables for assets, versions, users, permissions, tags, and audit logs.
-- This ensures relational integrity and supports efficient querying for game dev workflows.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enumerated type for user roles.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM ('admin', 'editor', 'viewer');
    END IF;
END $$;

-- Users table: Stores user info with roles for access control.
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    role user_role DEFAULT 'viewer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Assets table: Core metadata storage. Uses JSONB for flexible ext. data.
CREATE TABLE IF NOT EXISTS assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,  -- e.g., 'texture', 'model', 'audio'
    metadata JSONB,  -- e.g., {"size": 1024, "format": "png"}
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Asset Versions: Tracks changes/history for versioning during releases.
CREATE TABLE IF NOT EXISTS asset_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    file_path VARCHAR(255),  -- e.g., S3 URL
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (asset_id, version_number)
);

-- Permissions: Row-level access control.
CREATE TABLE IF NOT EXISTS permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    read BOOLEAN DEFAULT TRUE,
    write BOOLEAN DEFAULT FALSE,
    delete BOOLEAN DEFAULT FALSE
);

-- Tags: For categorization and fast searches.
CREATE TABLE IF NOT EXISTS tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) UNIQUE NOT NULL
);

-- Asset-Tags Junction: Many-to-many.
CREATE TABLE IF NOT EXISTS asset_tags (
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    tag_id UUID REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (asset_id, tag_id)
);

-- Audit Log: For tracking changes, crucial for compliance in title releases.
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(50),
    operation CHAR(1),  -- I/U/D
    old_row JSONB,
    new_row JSONB,
    executed_by TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
