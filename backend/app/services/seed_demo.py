from datetime import datetime, timedelta, timezone
import sqlite3
from typing import Any

from backend.app.core.database import new_uuid, utc_now_iso
from backend.app.services.sop_gate_service import SOPGateService


class BootstrapSeedService:
    @classmethod
    def ensure_baseline_seed(cls, conn: sqlite3.Connection) -> dict[str, Any]:
        org = conn.execute("SELECT * FROM organizations LIMIT 1").fetchone()
        if org:
            users_list = [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]
            users_map = {r["role"]: r for r in users_list}
            return {
                "organization": dict(org),
                "users": users_list,
                "users_by_role": users_map,
                "projects": [dict(r) for r in conn.execute("SELECT * FROM projects").fetchall()],
                "websites": [dict(r) for r in conn.execute("SELECT * FROM websites").fetchall()],
            }

        now = utc_now_iso()
        org_id = new_uuid()
        conn.execute(
            "INSERT INTO organizations (id, name, slug, settings_json, created_at) VALUES (?, ?, ?, '{}', ?)",
            (org_id, "OpsHub Operations Division", "opshub-core", now),
        )

        role_seeds = [
            ("system_admin", "admin@opshub.internal", "Anik Karmakar (System Admin)"),
            ("Dev_Ops_Engineer", "devops@opshub.internal", "SK Sahinur Islam (DevOps Engineer)"),
            ("manager", "manager@opshub.internal", "Elena Vance (Operations Manager)"),
            ("maintenance_engineer", "maintainer@opshub.internal", "Soumyanil Das (Maintenance Engineer)"),
            ("developer", "developer@opshub.internal", "Srijan Paul (Senior Developer)"),
            ("reviewer_qa", "qa@opshub.internal", "Marcus Chen (QA & Security Reviewer)"),
            ("readonly_stakeholder", "stakeholder@opshub.internal", "Sophia Sterling (Client Executive)"),
            ("report_recipient", "recipient@client.example.com", "David Ward (External Report Recipient)"),
        ]

        users_by_role: dict[str, dict[str, Any]] = {}
        for role_val, email, full_name in role_seeds:
            uid = new_uuid()
            conn.execute(
                """
                INSERT INTO users (id, org_id, email, full_name, role, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (uid, org_id, email, full_name, role_val, now),
            )
            users_by_role[role_val] = {
                "id": uid,
                "email": email,
                "full_name": full_name,
                "role": role_val,
                "is_active": 1,
            }

        admin_id = users_by_role["system_admin"]["id"]
        manager_id = users_by_role["Dev_Ops_Engineer"]["id"]
        maintainer_id = users_by_role["maintenance_engineer"]["id"]
        dev_id = users_by_role["developer"]["id"]
        qa_id = users_by_role["reviewer_qa"]["id"]

        SOPGateService.ensure_default_template(conn, created_by=admin_id)

        proj_id = new_uuid()
        conn.execute(
            """
            INSERT INTO projects (
                id, org_id, code, name, description, client_name, lead_user_id, status, priority, created_at, updated_at
            ) VALUES (?, ?, 'PRJ-WP-FLEET', 'Managed WordPress Production & Staging Fleet',
                      'SOP maintenance across WordPress properties', 'Enterprise Clients', ?, 'active', 'high', ?, ?)
            """,
            (proj_id, org_id, manager_id, now, now),
        )

        today_iso = datetime.now(timezone.utc).date().isoformat()
        overdue_iso = (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat()

        sample_sites = [
            ("Acme Commerce Live", "acme-commerce.example.com", "live", "due", "divi", today_iso),
            ("Acme Commerce Staging", "staging.acme-commerce.example.com", "staging", "due", "divi", today_iso),
            ("Apex Corporate Portal", "apex-portal.example.org", "live", "overdue", "gutenberg", overdue_iso),
        ]

        for name, domain, env, wf_st, bldr, due in sample_sites:
            sid = new_uuid()
            conn.execute(
                """
                INSERT INTO websites (
                    id, project_id, name, domain, url, environment, health_status, workflow_status,
                    maintainer_id, developer_id, reviewer_id, frequency, next_due_at, wp_version,
                    php_version, builder, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'online', ?, ?, ?, ?, 'monthly', ?, '6.6.2', '8.2', ?, ?, ?)
                """,
                (
                    sid,
                    proj_id,
                    name,
                    domain,
                    f"https://{domain}",
                    env,
                    wf_st,
                    maintainer_id,
                    dev_id,
                    qa_id,
                    due,
                    bldr,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO maintenance_schedules (
                    id, website_id, template_code, frequency, interval_days, anchor_policy,
                    planned_due_at, next_due_at, owner_id, is_active, updated_at
                ) VALUES (?, ?, 'WP_MAINT_SOP', 'monthly', 30, 'planned_date', ?, ?, ?, 1, ?)
                """,
                (
                    new_uuid(),
                    sid,
                    due,
                    due,
                    maintainer_id,
                    now,
                ),
            )

        issue_id = new_uuid()
        conn.execute(
            """
            INSERT INTO issues (
                id, project_id, category, severity, priority, title, description,
                owner_id, reviewer_id, status, created_at, updated_at
            ) VALUES (?, ?, 'security_vulnerability', 'high', 'high',
                      'Missing HSTS Security Header on Apex Portal',
                      'Strict-Transport-Security header missing on HTTPS responses.',
                      ?, ?, 'assigned', ?, ?)
            """,
            (issue_id, proj_id, dev_id, qa_id, now, now),
        )

        task_id = new_uuid()
        conn.execute(
            """
            INSERT INTO tasks (
                id, project_id, title, description, owner_id, reviewer_id, priority, status, due_at, created_at, updated_at
            ) VALUES (?, ?, 'Complete Monthly SOP Maintenance for Acme Commerce',
                      'Execute all 23 SOP checks and verify backup archive.',
                      ?, ?, 'high', 'in_progress', ?, ?, ?)
            """,
            (task_id, proj_id, maintainer_id, qa_id, today_iso, now, now),
        )

        return cls.ensure_baseline_seed(conn)
