-- Sample Data
-- Author: [Your Name]
-- Description: Inserts demo data for testing asset management workflows.

INSERT INTO users (username, role) VALUES ('admin_user', 'admin');
INSERT INTO users (username, role) VALUES ('lead_artist', 'editor');
INSERT INTO users (username, role) VALUES ('qa_reviewer', 'viewer');

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


INSERT INTO tags (name) VALUES ('texture'), ('model');

INSERT INTO assets (name, type, metadata, project_id, created_by)
VALUES (
    'hero_texture',
    'texture',
    '{"size": 2048, "format": "png", "file_path": "s3://bucket/hero_texture_v1.png"}',
    (SELECT id FROM projects WHERE code = 'MYTHIC'),
    (SELECT id FROM users WHERE username = 'admin_user')
);

INSERT INTO asset_tags (asset_id, tag_id)
VALUES (
    (SELECT id FROM assets WHERE name = 'hero_texture'),
    (SELECT id FROM tags WHERE name = 'texture')
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

-- Example review request for the initial asset version.
INSERT INTO asset_reviews (asset_version_id, reviewer_id, status, comments)
VALUES (
    (SELECT id FROM asset_versions ORDER BY created_at DESC LIMIT 1),
    (SELECT id FROM users WHERE username = 'qa_reviewer'),
    'pending',
    'Awaiting QA validation before milestone lock.'
);

-- Add more as needed.
