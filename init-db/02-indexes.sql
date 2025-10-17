-- Indexes for Performance
-- Author: [Your Name]
-- Description: Creates indexes on frequently queried fields to optimize for asset searches in game pipelines.

CREATE INDEX IF NOT EXISTS idx_assets_name ON assets(name);
CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(type);
CREATE INDEX IF NOT EXISTS idx_assets_created_by ON assets(created_by);
CREATE INDEX IF NOT EXISTS idx_assets_project_id ON assets(project_id);
CREATE INDEX IF NOT EXISTS idx_assets_metadata_format ON assets USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_asset_versions_asset_id ON asset_versions(asset_id);
CREATE INDEX IF NOT EXISTS idx_permissions_asset_id ON permissions(asset_id);
CREATE INDEX IF NOT EXISTS idx_permissions_user_id ON permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_permissions_project_id ON permissions(project_id);
CREATE INDEX IF NOT EXISTS idx_asset_tags_asset_id ON asset_tags(asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_tags_tag_id ON asset_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_projects_code ON projects(code);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_project_members_user_id ON project_members(user_id);
CREATE INDEX IF NOT EXISTS idx_asset_reviews_status ON asset_reviews(status);
CREATE INDEX IF NOT EXISTS idx_asset_reviews_version ON asset_reviews(asset_version_id);
CREATE INDEX IF NOT EXISTS idx_project_storage_snapshots_project ON project_storage_snapshots(project_id);
CREATE INDEX IF NOT EXISTS idx_project_archive_log_project ON project_archive_log(project_id);
