-- Description: Defines tables for assets, versions, users, projects, permissions, tags, and audit logs.
-- This ensures relational integrity and supports efficient querying for game dev workflows across multi-project studios.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enumerated type for user roles.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM ('admin', 'editor', 'viewer');
    END IF;
END $$;

-- Enumerated type for project membership roles to provide a hierarchy of access.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'project_role') THEN
        CREATE TYPE project_role AS ENUM ('owner', 'manager', 'lead', 'contributor', 'reviewer', 'viewer');
    END IF;
END $$;

-- Enumerated type for project lifecycle status.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'project_status') THEN
        CREATE TYPE project_status AS ENUM ('planning', 'active', 'on_hold', 'archived');
    END IF;
END $$;

-- Enumerated type for review workflow state.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'review_status') THEN
        CREATE TYPE review_status AS ENUM ('pending', 'approved', 'changes_requested');
    END IF;
END $$;

-- Users table: Stores user info with roles for access control.
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role user_role DEFAULT 'viewer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Projects table: Supports multi-project studio management.
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(150) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    status project_status DEFAULT 'planning',
    storage_quota_tb NUMERIC(10,2) DEFAULT 10.00 CHECK (storage_quota_tb > 0), -- default studio allocation with ability to scale
    storage_provider TEXT DEFAULT 'object-storage',
    storage_location TEXT, -- e.g., bucket name or NAS path
    archived_at TIMESTAMP,
    archived_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Streams/Branches to track Helix-style branch semantics.
CREATE TABLE IF NOT EXISTS branches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    parent_branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, name)
);

-- Track membership with explicit hierarchy per project.
CREATE TABLE IF NOT EXISTS project_members (
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role project_role NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, user_id)
);

-- Storage telemetry snapshots per project to support scaling decisions.
CREATE TABLE IF NOT EXISTS project_storage_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    asset_count BIGINT DEFAULT 0,
    total_bytes BIGINT DEFAULT 0,
    notes TEXT
);

-- Assets table: Core metadata storage. Uses JSONB for flexible ext. data.
CREATE TABLE IF NOT EXISTS assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,  -- e.g., 'texture', 'model', 'audio'
    metadata JSONB,  -- e.g., {"size": 1024, "format": "png"}
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Asset Versions: Tracks changes/history for versioning during releases.
CREATE TABLE IF NOT EXISTS asset_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
    file_path VARCHAR(255),  -- e.g., S3 URL
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (asset_id, version_number)
);

-- Workspace semantics for end users to manage local clones/sandboxes.
CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_synced_at TIMESTAMP,
    UNIQUE (project_id, user_id, name)
);

-- File locking for binary assets.
CREATE TABLE IF NOT EXISTS asset_locks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    locked_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
    locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    notes TEXT,
    UNIQUE (asset_id)
);

-- Shelved changes for pending submissions.
CREATE TABLE IF NOT EXISTS shelves (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    asset_version_id UUID NOT NULL REFERENCES asset_versions(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Workspace activity audit log for collaboration insights.
CREATE TABLE IF NOT EXISTS workspace_activity (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(120) NOT NULL,
    asset_id UUID REFERENCES assets(id) ON DELETE SET NULL,
    asset_version_id UUID REFERENCES asset_versions(id) ON DELETE SET NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Session helper functions for row-level security integration. The application
-- sets the request user via SELECT set_app_user('uuid').
CREATE OR REPLACE FUNCTION set_app_user(user_uuid UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_user_id', user_uuid::text, true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION current_app_user()
RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(current_setting('app.current_user_id', true), '')::uuid;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION current_app_user_role()
RETURNS user_role AS $$
DECLARE
    role_value user_role;
BEGIN
    SELECT role INTO role_value FROM users WHERE id = current_app_user();
    RETURN role_value;
END;
$$ LANGUAGE plpgsql STABLE;

-- Permissions: Row-level access control.
CREATE TABLE IF NOT EXISTS permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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

-- Review workflow per asset version.
CREATE TABLE IF NOT EXISTS asset_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_version_id UUID REFERENCES asset_versions(id) ON DELETE CASCADE,
    reviewer_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status review_status DEFAULT 'pending',
    comments TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (asset_version_id, reviewer_id)
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

-- Immutable archive log entries to record final project snapshots.
CREATE TABLE IF NOT EXISTS project_archive_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    archived_by UUID REFERENCES users(id),
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    summary JSONB
);
