-- Sample Data
-- Author: [Your Name]
-- Description: Inserts demo data for testing asset management workflows.

INSERT INTO users (username, role) VALUES ('admin_user', 'admin');
INSERT INTO users (username, role) VALUES ('editor_user', 'editor');

INSERT INTO tags (name) VALUES ('texture'), ('model');

INSERT INTO assets (name, type, metadata, created_by)
VALUES (
    'hero_texture',
    'texture',
    '{"size": 2048, "format": "png", "file_path": "s3://bucket/hero_texture_v1.png"}',
    (SELECT id FROM users WHERE username = 'admin_user')
);

INSERT INTO asset_tags (asset_id, tag_id)
VALUES (
    (SELECT id FROM assets WHERE name = 'hero_texture'),
    (SELECT id FROM tags WHERE name = 'texture')
);

-- Add more as needed.
