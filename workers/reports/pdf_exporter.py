from pathlib import Path
import re
import sqlite3
from typing import Any
import openpyxl
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.app.core.config import settings
from backend.app.core.database import new_uuid, utc_now_iso
from backend.app.services.audit_service import AuditService
from backend.app.services.sop_gate_service import SOPGateService


def redact_secrets(text: str) -> str:
    if not text:
        return ""
    patterns = [
        (r"(?i)password\s*[:=]\s*\S+", "password: [REDACTED]"),
        (r"(?i)secret\s*[:=]\s*\S+", "secret: [REDACTED]"),
        (r"(?i)token\s*[:=]\s*\S+", "token: [REDACTED]"),
        (r"(?i)key\s*[:=]\s*([a-zA-Z0-9_\-]{16,})", "key: [REDACTED]"),
    ]
    result = text
    for pat, repl in patterns:
        result = re.sub(pat, repl, result)
    return result


class ReportAndExportService:
    @classmethod
    def generate_session_pdf_report(
        cls,
        conn: sqlite3.Connection,
        *,
        session_id: str,
        actor_user_id: str,
    ) -> dict[str, Any]:
        detail = SOPGateService.get_session_detail(conn, session_id)
        settings.reports_dir.mkdir(parents=True, exist_ok=True)
        settings.mail_sink_dir.mkdir(parents=True, exist_ok=True)

        prior = conn.execute(
            "SELECT COUNT(*) FROM reminders_and_reports WHERE target_entity_id = ? AND subtype = 'maintenance_completion'",
            (session_id,),
        ).fetchone()[0]
        is_rev = prior > 0

        rev_tag = "[UPDATED REVISION REPORT] " if is_rev else ""
        pdf_path = settings.reports_dir / f"OpsHub_Session_{session_id[:8]}{'_REV' if is_rev else ''}.pdf"

        doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(
                f"{rev_tag}OpsHub Maintenance Report — {detail['website_name']}",
                styles["Heading1"],
            ),
            Spacer(1, 10),
            Paragraph(
                f"<b>Domain:</b> {detail['website_domain']} | <b>Environment:</b> {detail['environment_snapshot'].upper()} | "
                f"<b>Maintainer:</b> {detail['maintainer_name']} | <b>Status:</b> {detail['status'].upper()}",
                styles["Normal"],
            ),
            Spacer(1, 12),
        ]

        table_data = [["#", "SOP Task Title", "Status", "Observation / Finding"]]
        for item in detail["items"]:
            raw_obs = item.get("observation") or item.get("na_reason") or "—"
            clean_obs = redact_secrets(raw_obs)[:100]
            table_data.append([
                str(item["step_number"]),
                item["title"],
                item["status"].upper(),
                clean_obs,
            ])

        t = Table(table_data, colWidths=[28, 160, 95, 235])
        t.setStyle(
            TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172B4D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ])
        )
        story.append(t)
        doc.build(story)

        subj = f"{rev_tag}[OpsHub] Maintenance Report: {detail['website_name']}"
        email_path = settings.mail_sink_dir / f"email_{session_id[:8]}_{prior + 1}.txt"
        email_content = (
            f"Subject: {subj}\n"
            f"Website: {detail['website_domain']}\n"
            f"Environment: {detail['environment_snapshot']}\n"
            f"Status: {detail['status']}\n"
            f"PDF Attachment: {pdf_path}\n"
            f"Revision: {is_rev}\n"
        )
        email_path.write_text(email_content, encoding="utf-8")

        now = utc_now_iso()
        report_id = new_uuid()
        conn.execute(
            """
            INSERT INTO reminders_and_reports (
                id, record_type, subtype, target_entity_type, target_entity_id,
                title, status, is_revised_report, artifact_path, generated_at, sent_at
            ) VALUES (?, 'report', 'maintenance_completion', 'maintenance_session', ?, ?, 'sent', ?, ?, ?, ?)
            """,
            (
                report_id,
                session_id,
                subj,
                1 if is_rev else 0,
                str(pdf_path),
                now,
                now,
            ),
        )
        AuditService.log_event(
            conn,
            actor_user_id=actor_user_id,
            entity_type="reminder_and_report",
            entity_id=report_id,
            action="report_generated",
            summary=f"Generated {subj} (revision={is_rev})",
        )
        return {
            "id": report_id,
            "subject": subj,
            "pdf_path": str(pdf_path),
            "email_sink_path": str(email_path),
            "is_revised_report": is_rev,
        }

    @classmethod
    def export_inventory_and_issues_xlsx(
        cls,
        conn: sqlite3.Connection,
        *,
        actor_user_id: str,
    ) -> Path:
        settings.reports_dir.mkdir(parents=True, exist_ok=True)
        xlsx_path = settings.reports_dir / "OpsHub_Compliance_Workbook.xlsx"

        wb = openpyxl.Workbook()
        ws_sites = wb.active
        ws_sites.title = "Websites Fleet"
        ws_sites.append([
            "ID", "Name", "Domain", "Environment", "Builder", "Health Status",
            "Workflow Status", "Next Due Date", "WP Version", "PHP Version"
        ])

        for r in conn.execute("SELECT * FROM websites ORDER BY name ASC").fetchall():
            ws_sites.append([
                r["id"], r["name"], r["domain"], r["environment"], r["builder"],
                r["health_status"], r["workflow_status"], r["next_due_at"],
                r["wp_version"], r["php_version"],
            ])

        ws_issues = wb.create_sheet(title="Issues Register")
        ws_issues.append([
            "ID", "Title", "Severity", "Priority", "Status", "Category", "Due Date", "Created At"
        ])
        for r in conn.execute("SELECT * FROM issues ORDER BY created_at DESC").fetchall():
            ws_issues.append([
                r["id"], redact_secrets(r["title"]), r["severity"], r["priority"],
                r["status"], r["category"], r["due_at"], r["created_at"],
            ])

        wb.save(str(xlsx_path))
        AuditService.log_event(
            conn,
            actor_user_id=actor_user_id,
            entity_type="report",
            entity_id=str(xlsx_path),
            action="xlsx_exported",
            summary="Exported compliance XLSX workbook",
        )
        return xlsx_path
