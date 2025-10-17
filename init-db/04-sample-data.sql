-- Sample Data
-- Description: Inserts demo data for testing asset management workflows.

INSERT INTO users (username, password_hash, role) VALUES
('admin_user', 'pbkdf2_sha256$120000$Vk/p8a1teRo3QPH4IYMnXA$kStuu3gnqMorVZtdegDIPyyf/wgbeDZQLBi8YhM1pLM', 'admin'),
('lead_artist', 'pbkdf2_sha256$120000$iaCk2u2XrGF6HM7lxXp5gg$5GbftgHpOr/awm7WxW5yn0NKf6PKIjdYG6TngMhqDhk', 'editor'),
('qa_reviewer', 'pbkdf2_sha256$120000$HTQxsvcGkopHpEnMZb7a7w$iqBhnTYdDtiI9HFghUQ6W6Ut0Y9yUyE8SxFouhg21jY', 'viewer');

INSERT INTO projects (name, code, description, status, storage_quota_tb)
VALUES (
    'Mythic Quest',
    'MYTHIC',
    'Hero assets and environments for the Mythic Quest franchise.',
    'active',
    10.00
);

INSERT INTO project_members (project_id, user_id, role)
VALUES
(
    (SELECT id FROM projects WHERE code = 'MYTHIC'),
    (SELECT id FROM users WHERE username = 'admin_user'),
    'owner'
),
(
    (SELECT id FROM projects WHERE code = 'MYTHIC'),
    (SELECT id FROM users WHERE username = 'lead_artist'),
    'lead'
),
(
    (SELECT id FROM projects WHERE code = 'MYTHIC'),
    (SELECT id FROM users WHERE username = 'qa_reviewer'),
    'reviewer'
);

INSERT INTO project_storage_snapshots (project_id, asset_count, total_bytes, notes)
VALUES (
    (SELECT id FROM projects WHERE code = 'MYTHIC'),
    0,
    0,
    'Initial allocation for 10TB scalable object storage'
);

INSERT INTO branches (project_id, name, description, created_by)
VALUES (
    (SELECT id FROM projects WHERE code = 'MYTHIC'),
    'main',
    'Primary integration stream for live production',
    (SELECT id FROM users WHERE username = 'admin_user')
);

INSERT INTO tags (name) VALUES ('texture'), ('model');

INSERT INTO assets (name, type, metadata, project_id, created_by)
VALUES (
    'hero_texture',
    'texture',
    '{"size": 2048, "format": "png", "file_path": "depot://hero_texture_v1.png"}',
    (SELECT id FROM projects WHERE code = 'MYTHIC'),
    (SELECT id FROM users WHERE username = 'admin_user')
);

INSERT INTO asset_tags (asset_id, tag_id)
VALUES (
    (SELECT id FROM assets WHERE name = 'hero_texture'),
    (SELECT id FROM tags WHERE name = 'texture')
);

INSERT INTO asset_versions (asset_id, version_number, branch_id, file_path, notes)
VALUES (
    (SELECT id FROM assets WHERE name = 'hero_texture'),
    1,
    (SELECT id FROM branches WHERE name = 'main' AND project_id = (SELECT id FROM projects WHERE code = 'MYTHIC')),
    'depot://hero_texture_v1.png',
    'Initial ingest of hero texture for milestone alpha.'
);

INSERT INTO project_storage_snapshots (project_id, asset_count, total_bytes, notes)
VALUES (
    (SELECT id FROM projects WHERE code = 'MYTHIC'),
    1,
    1073741824, -- 1 GiB consumed by hero texture revisions
    'Baseline usage after first hero texture ingest'
);

INSERT INTO permissions (project_id, asset_id, user_id, read, write, delete)
VALUES
(
    (SELECT project_id FROM assets WHERE name = 'hero_texture'),
    (SELECT id FROM assets WHERE name = 'hero_texture'),
    (SELECT id FROM users WHERE username = 'lead_artist'),
    TRUE,
    TRUE,
    FALSE
),
(
    (SELECT project_id FROM assets WHERE name = 'hero_texture'),
    (SELECT id FROM assets WHERE name = 'hero_texture'),
    (SELECT id FROM users WHERE username = 'qa_reviewer'),
    TRUE,
    FALSE,
    FALSE
);

INSERT INTO workspaces (project_id, user_id, branch_id, name, description, last_synced_at)
VALUES (
    (SELECT id FROM projects WHERE code = 'MYTHIC'),
    (SELECT id FROM users WHERE username = 'lead_artist'),
    (SELECT id FROM branches WHERE name = 'main' AND project_id = (SELECT id FROM projects WHERE code = 'MYTHIC')),
    'LeadArtist_Workstation',
    'Primary modeling workspace',
    CURRENT_TIMESTAMP
);

INSERT INTO asset_locks (asset_id, locked_by, workspace_id, notes)
VALUES (
    (SELECT id FROM assets WHERE name = 'hero_texture'),
    (SELECT id FROM users WHERE username = 'lead_artist'),
    (SELECT id FROM workspaces WHERE name = 'LeadArtist_Workstation'),
    'Lock held for texture polish pass'
);

INSERT INTO shelves (workspace_id, asset_version_id, created_by, description)
VALUES (
    (SELECT id FROM workspaces WHERE name = 'LeadArtist_Workstation'),
    (SELECT id FROM asset_versions WHERE asset_id = (SELECT id FROM assets WHERE name = 'hero_texture') AND version_number = 1),
    (SELECT id FROM users WHERE username = 'lead_artist'),
    'Ready for QA once lighting tweaks are verified.'
);

INSERT INTO workspace_activity (workspace_id, user_id, action, asset_id, asset_version_id, metadata)
VALUES (
    (SELECT id FROM workspaces WHERE name = 'LeadArtist_Workstation'),
    (SELECT id FROM users WHERE username = 'lead_artist'),
    'sync',
    (SELECT id FROM assets WHERE name = 'hero_texture'),
    (SELECT id FROM asset_versions WHERE asset_id = (SELECT id FROM assets WHERE name = 'hero_texture') AND version_number = 1),
    '{"notes": "Pulled latest main branch changes"}'
);

-- Example review request for the initial asset version.
INSERT INTO asset_reviews (asset_version_id, reviewer_id, status, comments)
VALUES (
    (SELECT id FROM asset_versions WHERE asset_id = (SELECT id FROM assets WHERE name = 'hero_texture') AND version_number = 1),
    (SELECT id FROM users WHERE username = 'qa_reviewer'),
    'pending',
    'Awaiting QA validation before milestone lock.'
);
