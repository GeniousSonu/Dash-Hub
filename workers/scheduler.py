from datetime import datetime, timezone
import sqlite3
from typing import Any

from backend.app.core.database import new_uuid, utc_now_iso


class MaintenanceSchedulerWorker:
    @classmethod
    def run_cycle(cls, conn: sqlite3.Connection) -> dict[str, Any]:
        today_str = datetime.now(timezone.utc).date().isoformat()
        now = utc_now_iso()

        overdue_sites = conn.execute(
            """
            SELECT id, name, domain, environment, next_due_at, maintainer_id
            FROM websites
            WHERE workflow_status = 'overdue' OR (next_due_at IS NOT NULL AND substr(next_due_at, 1, 10) < ?)
            """,
            (today_str,),
        ).fetchall()

        reminders_created = 0
        for site in overdue_sites:
            already_sent = conn.execute(
                """
                SELECT COUNT(*) FROM reminders_and_reports
                WHERE target_entity_id = ? AND subtype = 'overdue_website' AND substr(generated_at, 1, 10) = ?
                """,
                (site["id"], today_str),
            ).fetchone()[0]

            if already_sent == 0:
                conn.execute(
                    """
                    INSERT INTO reminders_and_reports (
                        id, record_type, subtype, target_entity_type, target_entity_id,
                        title, status, generated_at, sent_at
                    ) VALUES (?, 'reminder', 'overdue_website', 'website', ?, ?, 'sent', ?, ?)
                    """,
                    (
                        new_uuid(),
                        site["id"],
                        f"[OVERDUE REMINDER] Website {site['name']} ({site['domain']}) maintenance is overdue",
                        now,
                        now,
                    ),
                )
                reminders_created += 1

        critical_issues = conn.execute(
            """
            SELECT id, title, severity, project_id, owner_id
            FROM issues
            WHERE severity IN ('critical', 'high') AND status NOT IN ('resolved', 'closed', 'rejected')
            """
        ).fetchall()

        escalations_created = 0
        for issue in critical_issues:
            already_escalated = conn.execute(
                """
                SELECT COUNT(*) FROM reminders_and_reports
                WHERE target_entity_id = ? AND subtype = 'critical_issue_escalation' AND substr(generated_at, 1, 10) = ?
                """,
                (issue["id"], today_str),
            ).fetchone()[0]

            if already_escalated == 0:
                conn.execute(
                    """
                    INSERT INTO reminders_and_reports (
                        id, record_type, subtype, target_entity_type, target_entity_id,
                        title, status, generated_at, sent_at
                    ) VALUES (?, 'escalation', 'critical_issue_escalation', 'issue', ?, ?, 'sent', ?, ?)
                    """,
                    (
                        new_uuid(),
                        issue["id"],
                        f"[ESCALATION] Unresolved {issue['severity'].upper()} issue: {issue['title']}",
                        now,
                        now,
                    ),
                )
                escalations_created += 1

        return {
            "overdue_sites_checked": len(overdue_sites),
            "reminders_created": reminders_created,
            "escalations_created": escalations_created,
            "cycle_timestamp": now,
        }
