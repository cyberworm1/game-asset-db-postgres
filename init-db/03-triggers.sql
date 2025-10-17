-- Triggers for Auditing and Versioning
-- Author: [Your Name]
-- Description: Automates logging changes and auto-incrementing versions.

-- Function for audit logging.
CREATE OR REPLACE FUNCTION audit_log_func() RETURNS TRIGGER AS $$
DECLARE
    actor TEXT := current_user;
BEGIN
    IF (TG_OP = 'DELETE') THEN
        INSERT INTO audit_log (table_name, operation, old_row, executed_by)
        VALUES (TG_RELNAME, 'D', row_to_json(OLD), actor);
        RETURN OLD;
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO audit_log (table_name, operation, old_row, new_row, executed_by)
        VALUES (TG_RELNAME, 'U', row_to_json(OLD), row_to_json(NEW), actor);
        RETURN NEW;
    ELSIF (TG_OP = 'INSERT') THEN
        INSERT INTO audit_log (table_name, operation, new_row, executed_by)
        VALUES (TG_RELNAME, 'I', row_to_json(NEW), actor);
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Drop existing triggers to allow reruns in Docker init.
DROP TRIGGER IF EXISTS audit_assets ON assets;
CREATE TRIGGER audit_assets
AFTER INSERT OR UPDATE OR DELETE ON assets
FOR EACH ROW EXECUTE FUNCTION audit_log_func();

DROP TRIGGER IF EXISTS audit_asset_versions ON asset_versions;
CREATE TRIGGER audit_asset_versions
AFTER INSERT OR UPDATE OR DELETE ON asset_versions
FOR EACH ROW EXECUTE FUNCTION audit_log_func();

DROP TRIGGER IF EXISTS audit_permissions ON permissions;
CREATE TRIGGER audit_permissions
AFTER INSERT OR UPDATE OR DELETE ON permissions
FOR EACH ROW EXECUTE FUNCTION audit_log_func();

DROP TRIGGER IF EXISTS audit_asset_tags ON asset_tags;
CREATE TRIGGER audit_asset_tags
AFTER INSERT OR UPDATE OR DELETE ON asset_tags
FOR EACH ROW EXECUTE FUNCTION audit_log_func();

-- Versioning trigger: Auto-create version on asset insert/update.
CREATE OR REPLACE FUNCTION create_version_func() RETURNS TRIGGER AS $$
DECLARE
    max_version INT;
    file_path TEXT := NEW.metadata->>'file_path';
BEGIN
    SELECT COALESCE(MAX(version_number), 0) INTO max_version FROM asset_versions WHERE asset_id = NEW.id;
    INSERT INTO asset_versions (asset_id, version_number, file_path, notes)
    VALUES (NEW.id, max_version + 1, file_path, 'Auto-versioned');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS version_assets ON assets;
CREATE TRIGGER version_assets
AFTER INSERT OR UPDATE ON assets
FOR EACH ROW EXECUTE FUNCTION create_version_func();
