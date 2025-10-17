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

-- Maintain updated_at on projects table.
CREATE OR REPLACE FUNCTION touch_project_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Generic helper to refresh updated_at columns.
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Prevent modifications to archived projects and ensure assets reference a project.
CREATE OR REPLACE FUNCTION ensure_project_active_for_assets() RETURNS TRIGGER AS $$
DECLARE
    project_status project_status;
    project_uuid UUID;
BEGIN
    IF TG_OP = 'DELETE' THEN
        project_uuid := OLD.project_id;
    ELSE
        project_uuid := NEW.project_id;
    END IF;

    IF project_uuid IS NULL THEN
        RAISE EXCEPTION 'Assets must belong to a project.';
    END IF;

    SELECT status INTO project_status FROM projects WHERE id = project_uuid;

    IF project_status IS NULL THEN
        RAISE EXCEPTION 'Project % does not exist.', project_uuid;
    END IF;

    IF project_status = 'archived' THEN
        RAISE EXCEPTION 'Project % is archived and cannot be modified.', project_uuid;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Ensure project activity when mutating asset versions.
CREATE OR REPLACE FUNCTION ensure_project_active_for_asset_versions() RETURNS TRIGGER AS $$
DECLARE
    project_status project_status;
    project_uuid UUID;
    target_asset UUID;
BEGIN
    target_asset := CASE WHEN TG_OP = 'DELETE' THEN OLD.asset_id ELSE NEW.asset_id END;

    SELECT p.id, p.status
        INTO project_uuid, project_status
    FROM assets a
    JOIN projects p ON p.id = a.project_id
    WHERE a.id = target_asset;

    IF project_uuid IS NULL THEN
        RAISE EXCEPTION 'Asset % must belong to a project before versioning.', target_asset;
    END IF;

    IF project_status IS NULL THEN
        RAISE EXCEPTION 'Project % does not exist.', project_uuid;
    END IF;

    IF project_status = 'archived' THEN
        RAISE EXCEPTION 'Project % is archived and cannot accept version changes.', project_uuid;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Enforce project mapping for permissions and block archived updates.
CREATE OR REPLACE FUNCTION enforce_permission_project_scope() RETURNS TRIGGER AS $$
DECLARE
    project_status project_status;
    asset_project UUID;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.project_id IS NULL THEN
            RETURN OLD;
        END IF;

        SELECT status INTO project_status FROM projects WHERE id = OLD.project_id;

        IF project_status = 'archived' THEN
            RAISE EXCEPTION 'Project % is archived and cannot have permissions changed.', OLD.project_id;
        END IF;

        RETURN OLD;
    END IF;

    IF NEW.asset_id IS NOT NULL THEN
        SELECT project_id INTO asset_project FROM assets WHERE id = NEW.asset_id;
        IF asset_project IS NULL THEN
            RAISE EXCEPTION 'Asset % is missing project linkage.', NEW.asset_id;
        END IF;
        NEW.project_id := asset_project;
    END IF;

    IF NEW.project_id IS NULL THEN
        RAISE EXCEPTION 'project_id must be supplied for permissions.';
    END IF;

    SELECT status INTO project_status FROM projects WHERE id = NEW.project_id;

    IF project_status IS NULL THEN
        RAISE EXCEPTION 'Project % does not exist.', NEW.project_id;
    END IF;

    IF project_status = 'archived' THEN
        RAISE EXCEPTION 'Project % is archived and cannot have permissions changed.', NEW.project_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Prevent archived projects from accepting new members.
CREATE OR REPLACE FUNCTION ensure_project_active_for_members() RETURNS TRIGGER AS $$
DECLARE
    project_status project_status;
    project_uuid UUID;
BEGIN
    project_uuid := CASE WHEN TG_OP = 'DELETE' THEN OLD.project_id ELSE NEW.project_id END;

    SELECT status INTO project_status FROM projects WHERE id = project_uuid;

    IF project_status IS NULL THEN
        RAISE EXCEPTION 'Project % does not exist.', project_uuid;
    END IF;

    IF project_status = 'archived' THEN
        RAISE EXCEPTION 'Project % is archived and cannot be assigned members.', project_uuid;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Prevent archived projects from accepting new tags for assets.
CREATE OR REPLACE FUNCTION ensure_project_active_for_asset_tags() RETURNS TRIGGER AS $$
DECLARE
    project_status project_status;
    project_uuid UUID;
BEGIN
    SELECT p.id, p.status
        INTO project_uuid, project_status
    FROM assets a
    JOIN projects p ON p.id = a.project_id
    WHERE a.id = (CASE WHEN TG_OP = 'DELETE' THEN OLD.asset_id ELSE NEW.asset_id END);

    IF project_uuid IS NULL THEN
        RAISE EXCEPTION 'Asset % must belong to a project before tagging.', CASE WHEN TG_OP = 'DELETE' THEN OLD.asset_id ELSE NEW.asset_id END;
    END IF;

    IF project_status IS NULL THEN
        RAISE EXCEPTION 'Project % does not exist.', project_uuid;
    END IF;

    IF project_status = 'archived' THEN
        RAISE EXCEPTION 'Project % is archived and cannot be modified.', project_uuid;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Touch changelist updated_at when children change.
CREATE OR REPLACE FUNCTION refresh_changelist_timestamp() RETURNS TRIGGER AS $$
DECLARE
    target_id UUID;
BEGIN
    IF TG_OP = 'DELETE' THEN
        target_id := OLD.changelist_id;
    ELSE
        target_id := NEW.changelist_id;
    END IF;

    IF target_id IS NOT NULL THEN
        UPDATE changelists SET updated_at = CURRENT_TIMESTAMP WHERE id = target_id;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Touch branch merge updated_at when conflicts change.
CREATE OR REPLACE FUNCTION refresh_branch_merge_timestamp() RETURNS TRIGGER AS $$
DECLARE
    target_id UUID;
BEGIN
    IF TG_OP = 'DELETE' THEN
        target_id := OLD.branch_merge_id;
    ELSE
        target_id := NEW.branch_merge_id;
    END IF;

    IF target_id IS NOT NULL THEN
        UPDATE branch_merges SET updated_at = CURRENT_TIMESTAMP WHERE id = target_id;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION touch_project_updated_at();

CREATE TRIGGER trg_changelists_updated_at
    BEFORE UPDATE ON changelists
    FOR EACH ROW
    EXECUTE FUNCTION touch_updated_at();

CREATE TRIGGER trg_branch_merges_updated_at
    BEFORE UPDATE ON branch_merges
    FOR EACH ROW
    EXECUTE FUNCTION touch_updated_at();

CREATE TRIGGER trg_merge_jobs_updated_at
    BEFORE UPDATE ON merge_jobs
    FOR EACH ROW
    EXECUTE FUNCTION touch_updated_at();

CREATE TRIGGER trg_changelist_items_touch_parent
    AFTER INSERT OR UPDATE OR DELETE ON changelist_items
    FOR EACH ROW
    EXECUTE FUNCTION refresh_changelist_timestamp();

CREATE TRIGGER trg_shelves_touch_changelist
    AFTER INSERT OR UPDATE OR DELETE ON shelves
    FOR EACH ROW
    EXECUTE FUNCTION refresh_changelist_timestamp();

CREATE TRIGGER trg_merge_conflicts_touch_branch_merge
    AFTER INSERT OR UPDATE OR DELETE ON merge_conflicts
    FOR EACH ROW
    EXECUTE FUNCTION refresh_branch_merge_timestamp();

CREATE TRIGGER trg_merge_jobs_touch_branch_merge
    AFTER INSERT OR UPDATE OR DELETE ON merge_jobs
    FOR EACH ROW
    EXECUTE FUNCTION refresh_branch_merge_timestamp();

-- Prevent archived projects from getting new review records.
CREATE OR REPLACE FUNCTION ensure_project_active_for_asset_reviews() RETURNS TRIGGER AS $$
DECLARE
    project_status project_status;
    project_uuid UUID;
BEGIN
    SELECT p.id, p.status
        INTO project_uuid, project_status
    FROM asset_versions v
    JOIN assets a ON a.id = v.asset_id
    JOIN projects p ON p.id = a.project_id
    WHERE v.id = (CASE WHEN TG_OP = 'DELETE' THEN OLD.asset_version_id ELSE NEW.asset_version_id END);

    IF project_uuid IS NULL THEN
        RAISE EXCEPTION 'Asset version % must be linked to an existing project.', CASE WHEN TG_OP = 'DELETE' THEN OLD.asset_version_id ELSE NEW.asset_version_id END;
    END IF;

    IF project_status IS NULL THEN
        RAISE EXCEPTION 'Project % does not exist.', project_uuid;
    END IF;

    IF project_status = 'archived' THEN
        RAISE EXCEPTION 'Project % is archived and review workflow is immutable.', project_uuid;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Prevent archived projects from recording new storage telemetry.
CREATE OR REPLACE FUNCTION ensure_project_active_for_storage_snapshots() RETURNS TRIGGER AS $$
DECLARE
    project_status project_status;
    project_uuid UUID;
BEGIN
    project_uuid := CASE WHEN TG_OP = 'DELETE' THEN OLD.project_id ELSE NEW.project_id END;

    SELECT status INTO project_status FROM projects WHERE id = project_uuid;

    IF project_status IS NULL THEN
        RAISE EXCEPTION 'Project % does not exist.', project_uuid;
    END IF;

    IF project_status = 'archived' THEN
        RAISE EXCEPTION 'Project % is archived and storage telemetry is immutable.', project_uuid;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Log immutable archive snapshots when a project transitions to archived.
CREATE OR REPLACE FUNCTION log_project_archive() RETURNS TRIGGER AS $$
DECLARE
    asset_ct BIGINT;
    version_ct BIGINT;
    member_ct BIGINT;
    last_snapshot JSONB;
    archive_summary JSONB;
BEGIN
    IF OLD.status = 'archived' THEN
        RAISE EXCEPTION 'Archived project % is immutable.', OLD.id;
    END IF;

    IF NEW.status = 'archived' AND (OLD.status IS DISTINCT FROM 'archived') THEN
        SELECT COUNT(*) INTO asset_ct FROM assets WHERE project_id = NEW.id;
        SELECT COUNT(*) INTO version_ct
        FROM asset_versions v
        JOIN assets a ON a.id = v.asset_id
        WHERE a.project_id = NEW.id;
        SELECT COUNT(*) INTO member_ct FROM project_members WHERE project_id = NEW.id;
        SELECT to_jsonb(s) INTO last_snapshot
        FROM project_storage_snapshots s
        WHERE s.project_id = NEW.id
        ORDER BY captured_at DESC
        LIMIT 1;

        archive_summary := jsonb_build_object(
            'project', jsonb_build_object('name', NEW.name, 'code', NEW.code),
            'asset_count', asset_ct,
            'version_count', version_ct,
            'member_count', member_ct,
            'storage_snapshot', COALESCE(last_snapshot, '{}'::jsonb)
        );

        NEW.archived_at := COALESCE(NEW.archived_at, CURRENT_TIMESTAMP);

        INSERT INTO project_archive_log (project_id, archived_by, archived_at, summary)
        VALUES (NEW.id, NEW.archived_by, NEW.archived_at, archive_summary);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Prevent updates/deletes on archive log entries.
CREATE OR REPLACE FUNCTION prevent_archive_log_mutations() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Project archive log entries are immutable.';
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

DROP TRIGGER IF EXISTS audit_projects ON projects;
CREATE TRIGGER audit_projects
AFTER INSERT OR UPDATE OR DELETE ON projects
FOR EACH ROW EXECUTE FUNCTION audit_log_func();

DROP TRIGGER IF EXISTS audit_project_members ON project_members;
CREATE TRIGGER audit_project_members
AFTER INSERT OR UPDATE OR DELETE ON project_members
FOR EACH ROW EXECUTE FUNCTION audit_log_func();

DROP TRIGGER IF EXISTS audit_asset_reviews ON asset_reviews;
CREATE TRIGGER audit_asset_reviews
AFTER INSERT OR UPDATE OR DELETE ON asset_reviews
FOR EACH ROW EXECUTE FUNCTION audit_log_func();

DROP TRIGGER IF EXISTS audit_project_storage_snapshots ON project_storage_snapshots;
CREATE TRIGGER audit_project_storage_snapshots
AFTER INSERT OR UPDATE OR DELETE ON project_storage_snapshots
FOR EACH ROW EXECUTE FUNCTION audit_log_func();

DROP TRIGGER IF EXISTS audit_project_archive_log ON project_archive_log;
CREATE TRIGGER audit_project_archive_log
AFTER INSERT OR DELETE ON project_archive_log
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

-- Project updated_at maintenance and archive logging.
DROP TRIGGER IF EXISTS touch_projects_updated_at ON projects;
CREATE TRIGGER touch_projects_updated_at
BEFORE UPDATE ON projects
FOR EACH ROW EXECUTE FUNCTION touch_project_updated_at();

DROP TRIGGER IF EXISTS project_archive_logger ON projects;
CREATE TRIGGER project_archive_logger
BEFORE UPDATE ON projects
FOR EACH ROW EXECUTE FUNCTION log_project_archive();

-- Enforce active projects for mutations across tables.
DROP TRIGGER IF EXISTS enforce_active_project_assets ON assets;
CREATE TRIGGER enforce_active_project_assets
BEFORE INSERT OR UPDATE OR DELETE ON assets
FOR EACH ROW EXECUTE FUNCTION ensure_project_active_for_assets();

DROP TRIGGER IF EXISTS enforce_active_project_asset_versions ON asset_versions;
CREATE TRIGGER enforce_active_project_asset_versions
BEFORE INSERT OR UPDATE OR DELETE ON asset_versions
FOR EACH ROW EXECUTE FUNCTION ensure_project_active_for_asset_versions();

DROP TRIGGER IF EXISTS enforce_active_project_permissions ON permissions;
CREATE TRIGGER enforce_active_project_permissions
BEFORE INSERT OR UPDATE OR DELETE ON permissions
FOR EACH ROW EXECUTE FUNCTION enforce_permission_project_scope();

DROP TRIGGER IF EXISTS enforce_active_project_members ON project_members;
CREATE TRIGGER enforce_active_project_members
BEFORE INSERT OR UPDATE OR DELETE ON project_members
FOR EACH ROW EXECUTE FUNCTION ensure_project_active_for_members();

DROP TRIGGER IF EXISTS enforce_active_project_asset_tags ON asset_tags;
CREATE TRIGGER enforce_active_project_asset_tags
BEFORE INSERT OR UPDATE OR DELETE ON asset_tags
FOR EACH ROW EXECUTE FUNCTION ensure_project_active_for_asset_tags();

DROP TRIGGER IF EXISTS enforce_active_project_asset_reviews ON asset_reviews;
CREATE TRIGGER enforce_active_project_asset_reviews
BEFORE INSERT OR UPDATE OR DELETE ON asset_reviews
FOR EACH ROW EXECUTE FUNCTION ensure_project_active_for_asset_reviews();

DROP TRIGGER IF EXISTS enforce_active_project_storage_snapshots ON project_storage_snapshots;
CREATE TRIGGER enforce_active_project_storage_snapshots
BEFORE INSERT OR UPDATE OR DELETE ON project_storage_snapshots
FOR EACH ROW EXECUTE FUNCTION ensure_project_active_for_storage_snapshots();

DROP TRIGGER IF EXISTS immutable_project_archive_log ON project_archive_log;
CREATE TRIGGER immutable_project_archive_log
BEFORE UPDATE OR DELETE ON project_archive_log
FOR EACH ROW EXECUTE FUNCTION prevent_archive_log_mutations();
