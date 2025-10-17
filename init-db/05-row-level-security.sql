-- Row Level Security policies for Helix-like protections.

-- Helper function to evaluate project membership for the current session user.
CREATE OR REPLACE FUNCTION is_project_member(project_uuid UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM project_members
        WHERE project_id = project_uuid AND user_id = current_app_user()
    );
END;
$$ LANGUAGE plpgsql STABLE;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY users_self_select ON users
    FOR SELECT USING (
        current_app_user_role() = 'admin' OR id = current_app_user()
    );
CREATE POLICY users_self_update ON users
    FOR UPDATE USING (id = current_app_user())
    WITH CHECK (id = current_app_user());
CREATE POLICY users_admin_manage ON users
    FOR ALL USING (current_app_user_role() = 'admin')
    WITH CHECK (current_app_user_role() = 'admin');

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
CREATE POLICY projects_member_read ON projects
    FOR SELECT USING (
        current_app_user_role() = 'admin' OR is_project_member(id)
    );
CREATE POLICY projects_admin_manage ON projects
    FOR ALL USING (current_app_user_role() = 'admin')
    WITH CHECK (current_app_user_role() = 'admin');

ALTER TABLE project_members ENABLE ROW LEVEL SECURITY;
CREATE POLICY project_members_visibility ON project_members
    FOR SELECT USING (
        current_app_user_role() = 'admin' OR user_id = current_app_user() OR is_project_member(project_id)
    );
CREATE POLICY project_members_manage ON project_members
    FOR ALL USING (current_app_user_role() = 'admin')
    WITH CHECK (current_app_user_role() = 'admin');

ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
CREATE POLICY assets_member_read ON assets
    FOR SELECT USING (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM permissions p
            WHERE p.asset_id = assets.id AND p.user_id = current_app_user() AND p.read = TRUE
        )
        OR EXISTS (
            SELECT 1 FROM project_members pm
            WHERE pm.project_id = assets.project_id AND pm.user_id = current_app_user()
        )
    );
CREATE POLICY assets_writer_manage ON assets
    FOR INSERT WITH CHECK (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM project_members pm
            WHERE pm.project_id = assets.project_id
              AND pm.user_id = current_app_user()
              AND pm.role IN ('owner','manager','lead','contributor')
        )
    );
CREATE POLICY assets_update_delete ON assets
    FOR UPDATE USING (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM permissions p
            WHERE p.asset_id = assets.id AND p.user_id = current_app_user() AND (p.write OR p.delete)
        )
    )
    WITH CHECK (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM permissions p
            WHERE p.asset_id = assets.id AND p.user_id = current_app_user() AND p.write = TRUE
        )
    );

ALTER TABLE asset_versions ENABLE ROW LEVEL SECURITY;
CREATE POLICY asset_versions_visibility ON asset_versions
    FOR SELECT USING (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM assets a
            JOIN permissions p ON p.asset_id = a.id
            WHERE a.id = asset_versions.asset_id
              AND p.user_id = current_app_user()
              AND p.read = TRUE
        )
        OR EXISTS (
            SELECT 1 FROM project_members pm
            JOIN assets a ON a.id = asset_versions.asset_id
            WHERE pm.project_id = a.project_id AND pm.user_id = current_app_user()
        )
    );
CREATE POLICY asset_versions_write ON asset_versions
    FOR INSERT WITH CHECK (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM permissions p
            WHERE p.asset_id = asset_versions.asset_id
              AND p.user_id = current_app_user()
              AND p.write = TRUE
        )
    );

ALTER TABLE permissions ENABLE ROW LEVEL SECURITY;
CREATE POLICY permissions_visibility ON permissions
    FOR SELECT USING (
        current_app_user_role() = 'admin' OR user_id = current_app_user()
    );
CREATE POLICY permissions_admin_manage ON permissions
    FOR ALL USING (current_app_user_role() = 'admin')
    WITH CHECK (current_app_user_role() = 'admin');

ALTER TABLE asset_reviews ENABLE ROW LEVEL SECURITY;
CREATE POLICY asset_reviews_visibility ON asset_reviews
    FOR SELECT USING (
        current_app_user_role() = 'admin'
        OR reviewer_id = current_app_user()
        OR EXISTS (
            SELECT 1 FROM assets a
            JOIN asset_versions av ON av.asset_id = a.id
            JOIN project_members pm ON pm.project_id = a.project_id
            WHERE av.id = asset_reviews.asset_version_id AND pm.user_id = current_app_user()
        )
    );
CREATE POLICY asset_reviews_update ON asset_reviews
    FOR UPDATE USING (
        current_app_user_role() = 'admin' OR reviewer_id = current_app_user()
    )
    WITH CHECK (
        current_app_user_role() = 'admin' OR reviewer_id = current_app_user()
    );
CREATE POLICY asset_reviews_insert ON asset_reviews
    FOR INSERT WITH CHECK (
        current_app_user_role() = 'admin'
        OR reviewer_id = current_app_user()
        OR EXISTS (
            SELECT 1 FROM project_members pm
            JOIN asset_versions av ON av.asset_id = (SELECT asset_id FROM asset_versions WHERE id = asset_reviews.asset_version_id)
            JOIN assets a ON a.id = av.asset_id
            WHERE pm.project_id = a.project_id AND pm.user_id = current_app_user()
        )
    );

ALTER TABLE branches ENABLE ROW LEVEL SECURITY;
CREATE POLICY branches_member_read ON branches
    FOR SELECT USING (
        current_app_user_role() = 'admin' OR is_project_member(project_id)
    );
CREATE POLICY branches_manage ON branches
    FOR ALL USING (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM project_members pm
            WHERE pm.project_id = branches.project_id
              AND pm.user_id = current_app_user()
              AND pm.role IN ('owner','manager','lead')
        )
    )
    WITH CHECK (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM project_members pm
            WHERE pm.project_id = branches.project_id
              AND pm.user_id = current_app_user()
              AND pm.role IN ('owner','manager','lead')
        )
    );

ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
CREATE POLICY workspaces_visibility ON workspaces
    FOR SELECT USING (
        current_app_user_role() = 'admin' OR user_id = current_app_user() OR is_project_member(project_id)
    );
CREATE POLICY workspaces_manage ON workspaces
    FOR ALL USING (
        current_app_user_role() = 'admin' OR user_id = current_app_user()
    )
    WITH CHECK (
        current_app_user_role() = 'admin' OR user_id = current_app_user()
    );

ALTER TABLE asset_locks ENABLE ROW LEVEL SECURITY;
CREATE POLICY asset_locks_visibility ON asset_locks
    FOR SELECT USING (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM project_members pm
            JOIN assets a ON a.id = asset_locks.asset_id
            WHERE pm.project_id = a.project_id AND pm.user_id = current_app_user()
        )
    );
CREATE POLICY asset_locks_manage ON asset_locks
    FOR ALL USING (
        current_app_user_role() = 'admin'
        OR locked_by = current_app_user()
    )
    WITH CHECK (
        current_app_user_role() = 'admin'
        OR locked_by = current_app_user()
    );

ALTER TABLE changelists ENABLE ROW LEVEL SECURITY;
CREATE POLICY changelists_visibility ON changelists
    FOR SELECT USING (
        current_app_user_role() = 'admin'
        OR is_project_member(project_id)
        OR created_by = current_app_user()
    );
CREATE POLICY changelists_manage ON changelists
    FOR ALL USING (
        current_app_user_role() = 'admin'
        OR created_by = current_app_user()
        OR EXISTS (
            SELECT 1 FROM project_members pm
            WHERE pm.project_id = changelists.project_id
              AND pm.user_id = current_app_user()
              AND pm.role IN ('owner','manager','lead','contributor')
        )
    )
    WITH CHECK (
        current_app_user_role() = 'admin'
        OR created_by = current_app_user()
        OR EXISTS (
            SELECT 1 FROM project_members pm
            WHERE pm.project_id = changelists.project_id
              AND pm.user_id = current_app_user()
              AND pm.role IN ('owner','manager','lead','contributor')
        )
    );

ALTER TABLE changelist_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY changelist_items_visibility ON changelist_items
    FOR SELECT USING (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM changelists c
            WHERE c.id = changelist_items.changelist_id
              AND (c.created_by = current_app_user() OR is_project_member(c.project_id))
        )
    );
CREATE POLICY changelist_items_manage ON changelist_items
    FOR ALL USING (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM changelists c
            WHERE c.id = changelist_items.changelist_id
              AND (
                    c.created_by = current_app_user()
                    OR EXISTS (
                        SELECT 1 FROM project_members pm
                        WHERE pm.project_id = c.project_id
                          AND pm.user_id = current_app_user()
                          AND pm.role IN ('owner','manager','lead','contributor')
                    )
                )
        )
    )
    WITH CHECK (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM changelists c
            WHERE c.id = changelist_items.changelist_id
              AND (
                    c.created_by = current_app_user()
                    OR EXISTS (
                        SELECT 1 FROM project_members pm
                        WHERE pm.project_id = c.project_id
                          AND pm.user_id = current_app_user()
                          AND pm.role IN ('owner','manager','lead','contributor')
                    )
                )
        )
    );

ALTER TABLE shelves ENABLE ROW LEVEL SECURITY;
CREATE POLICY shelves_visibility ON shelves
    FOR SELECT USING (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM workspaces w
            WHERE w.id = shelves.workspace_id AND (w.user_id = current_app_user() OR is_project_member(w.project_id))
        )
    );
CREATE POLICY shelves_manage ON shelves
    FOR ALL USING (
        current_app_user_role() = 'admin' OR created_by = current_app_user()
    )
    WITH CHECK (
        current_app_user_role() = 'admin' OR created_by = current_app_user()
    );

ALTER TABLE branch_merges ENABLE ROW LEVEL SECURITY;
CREATE POLICY branch_merges_visibility ON branch_merges
    FOR SELECT USING (
        current_app_user_role() = 'admin'
        OR is_project_member(project_id)
    );
CREATE POLICY branch_merges_manage ON branch_merges
    FOR ALL USING (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM project_members pm
            WHERE pm.project_id = branch_merges.project_id
              AND pm.user_id = current_app_user()
              AND pm.role IN ('owner','manager','lead')
        )
    )
    WITH CHECK (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM project_members pm
            WHERE pm.project_id = branch_merges.project_id
              AND pm.user_id = current_app_user()
              AND pm.role IN ('owner','manager','lead')
        )
    );

ALTER TABLE merge_conflicts ENABLE ROW LEVEL SECURITY;
CREATE POLICY merge_conflicts_visibility ON merge_conflicts
    FOR SELECT USING (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM branch_merges bm
            WHERE bm.id = merge_conflicts.branch_merge_id
              AND (bm.initiated_by = current_app_user() OR is_project_member(bm.project_id))
        )
    );
CREATE POLICY merge_conflicts_manage ON merge_conflicts
    FOR ALL USING (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM branch_merges bm
            WHERE bm.id = merge_conflicts.branch_merge_id
              AND (bm.initiated_by = current_app_user() OR is_project_member(bm.project_id))
        )
    )
    WITH CHECK (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM branch_merges bm
            WHERE bm.id = merge_conflicts.branch_merge_id
              AND (bm.initiated_by = current_app_user() OR is_project_member(bm.project_id))
        )
    );

ALTER TABLE workspace_activity ENABLE ROW LEVEL SECURITY;
CREATE POLICY workspace_activity_visibility ON workspace_activity
    FOR SELECT USING (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM workspaces w
            WHERE w.id = workspace_activity.workspace_id
              AND (w.user_id = current_app_user() OR is_project_member(w.project_id))
        )
    );
CREATE POLICY workspace_activity_insert ON workspace_activity
    FOR INSERT WITH CHECK (
        current_app_user_role() = 'admin'
        OR user_id = current_app_user()
    );

ALTER TABLE project_storage_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY project_storage_snapshots_visibility ON project_storage_snapshots
    FOR SELECT USING (
        current_app_user_role() = 'admin' OR is_project_member(project_id)
    );
CREATE POLICY project_storage_snapshots_insert ON project_storage_snapshots
    FOR INSERT WITH CHECK (
        current_app_user_role() = 'admin'
        OR EXISTS (
            SELECT 1 FROM project_members pm
            WHERE pm.project_id = project_storage_snapshots.project_id
              AND pm.user_id = current_app_user()
              AND pm.role IN ('owner','manager','lead')
        )
    );

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_log_visibility ON audit_log
    FOR SELECT USING (current_app_user_role() = 'admin');

ALTER TABLE project_archive_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY project_archive_log_visibility ON project_archive_log
    FOR SELECT USING (
        current_app_user_role() = 'admin' OR is_project_member(project_id)
    );
CREATE POLICY project_archive_log_manage ON project_archive_log
    FOR ALL USING (current_app_user_role() = 'admin')
    WITH CHECK (current_app_user_role() = 'admin');
