from datetime import datetime, timezone
import sqlite3
from typing import Any


class DashboardService:
    @staticmethod
    def get_summary(conn: sqlite3.Connection) -> dict[str, Any]:
        today_str = datetime.now(timezone.utc).date().isoformat()
        kpis = {
            "active_projects": conn.execute("SELECT COUNT(*) FROM projects WHERE status='active'").fetchone()[0],
            "total_websites": conn.execute("SELECT COUNT(*) FROM websites").fetchone()[0],
            "websites_due_today": conn.execute(
                "SELECT COUNT(*) FROM websites WHERE workflow_status='due' OR substr(next_due_at,1,10)=?",
                (today_str,),
            ).fetchone()[0],
            "websites_overdue": conn.execute("SELECT COUNT(*) FROM websites WHERE workflow_status='overdue'").fetchone()[0],
            "sessions_in_progress": conn.execute("SELECT COUNT(*) FROM maintenance_sessions WHERE status='in_progress'").fetchone()[0],
            "open_critical_high_issues": conn.execute(
                "SELECT COUNT(*) FROM issues WHERE severity IN ('critical','high') AND status NOT IN ('resolved','closed')"
            ).fetchone()[0],
            "pending_approvals": conn.execute("SELECT COUNT(*) FROM approvals WHERE status='pending'").fetchone()[0],
            "backups_awaiting_verification": conn.execute("SELECT COUNT(*) FROM backup_records WHERE is_verified=0").fetchone()[0],
            "completed_tasks": conn.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'").fetchone()[0],
            "total_tasks": conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
            "ssl_alerts": conn.execute("SELECT COUNT(*) FROM websites WHERE health_status='degraded'").fetchone()[0],
        }
        return {"kpis": kpis}

    @staticmethod
    def get_drilldown(conn: sqlite3.Connection, metric_key: str) -> list[dict[str, Any]]:
        today_str = datetime.now(timezone.utc).date().isoformat()
        if metric_key == "active_projects":
            rows = conn.execute("SELECT * FROM projects WHERE status='active' ORDER BY name ASC").fetchall()
        elif metric_key == "websites_due_today":
            rows = conn.execute(
                "SELECT * FROM websites WHERE workflow_status='due' OR substr(next_due_at,1,10)=? ORDER BY name ASC",
                (today_str,),
            ).fetchall()
        elif metric_key == "websites_overdue":
            rows = conn.execute("SELECT * FROM websites WHERE workflow_status='overdue' ORDER BY name ASC").fetchall()
        elif metric_key == "open_critical_high_issues":
            rows = conn.execute(
                "SELECT * FROM issues WHERE severity IN ('critical','high') AND status NOT IN ('resolved','closed') ORDER BY created_at DESC"
            ).fetchall()
        elif metric_key == "pending_approvals":
            rows = conn.execute("SELECT * FROM approvals WHERE status='pending' ORDER BY requested_at DESC").fetchall()
        elif metric_key == "backups_awaiting_verification":
            rows = conn.execute("SELECT * FROM backup_records WHERE is_verified=0 ORDER BY created_at DESC").fetchall()
        elif metric_key == "sessions_in_progress":
            rows = conn.execute("SELECT * FROM maintenance_sessions WHERE status='in_progress' ORDER BY started_at DESC").fetchall()
        elif metric_key == "completed_tasks":
            rows = conn.execute("SELECT * FROM tasks WHERE status='completed' ORDER BY updated_at DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM websites ORDER BY name ASC").fetchall()
        return [dict(r) for r in rows]
