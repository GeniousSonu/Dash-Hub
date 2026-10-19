from typing import Any

STATUS_BADGE_MAP: dict[str, dict[str, str]] = {
    "passed": {"label": "✓ PASSED", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "verified": {"label": "✓ VERIFIED", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "completed": {"label": "✓ COMPLETED", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "up_to_date": {"label": "✓ UP TO DATE", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "online": {"label": "● ONLINE", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "approved": {"label": "✓ APPROVED", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "resolved": {"label": "✓ RESOLVED", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "closed": {"label": "✓ CLOSED", "fg": "#15803D", "bg": "#DCFCE7", "border": "#2DCE89"},
    "failed": {"label": "✕ FAILED", "fg": "#B91C1C", "bg": "#FEE2E2", "border": "#F5365C"},
    "critical": {"label": "! CRITICAL", "fg": "#B91C1C", "bg": "#FEE2E2", "border": "#F5365C"},
    "overdue": {"label": "! OVERDUE", "fg": "#B91C1C", "bg": "#FEE2E2", "border": "#F5365C"},
    "blocked": {"label": "⊘ BLOCKED", "fg": "#9A3412", "bg": "#FFEDD5", "border": "#FB6340"},
    "completed_with_findings": {"label": "⚠ COMPLETED W/ FINDINGS", "fg": "#9A3412", "bg": "#FFEDD5", "border": "#FB6340"},
    "not_verified": {"label": "? NOT VERIFIED / ACCESS REQ", "fg": "#854D0E", "bg": "#FEF9C3", "border": "#FDE047"},
    "pending": {"label": "◷ PENDING", "fg": "#324CDD", "bg": "#EBF0FF", "border": "#5E72E4"},
    "in_progress": {"label": "↻ IN PROGRESS", "fg": "#324CDD", "bg": "#EBF0FF", "border": "#5E72E4"},
    "due": {"label": "◷ DUE", "fg": "#324CDD", "bg": "#EBF0FF", "border": "#5E72E4"},
    "not_applicable": {"label": "— N/A", "fg": "#525F7F", "bg": "#F6F9FC", "border": "#E9ECEF"},
    "urgent": {"label": "▲ URGENT", "fg": "#B91C1C", "bg": "#FEE2E2", "border": "#EF4444"},
    "high": {"label": "▲ HIGH", "fg": "#C2410C", "bg": "#FFEDD5", "border": "#F97316"},
    "normal": {"label": "◆ NORMAL", "fg": "#4338CA", "bg": "#EEF2FF", "border": "#6366F1"},
    "low": {"label": "▽ LOW", "fg": "#475569", "bg": "#F1F5F9", "border": "#94A3B8"},
    "ready": {"label": "● READY", "fg": "#0369A1", "bg": "#E0F2FE", "border": "#0EA5E9"},
    "cancelled": {"label": "✕ CANCELLED", "fg": "#64748B", "bg": "#F1F5F9", "border": "#94A3B8"},
}


def format_status_badge(status_key: str) -> dict[str, str]:
    norm = (status_key or "unknown").strip().lower()
    return STATUS_BADGE_MAP.get(
        norm,
        {"label": f"• {norm.upper()}", "fg": "#525F7F", "bg": "#F6F9FC", "border": "#E9ECEF"},
    )


try:
    from PySide6.QtWidgets import QLabel
    from PySide6.QtCore import Qt

    class StatusBadge(QLabel):
        def __init__(self, status_key: str, parent=None):
            super().__init__(parent)
            self.set_status(status_key)

        def set_status(self, status_key: str) -> None:
            spec = format_status_badge(status_key)
            self.setText(spec["label"])
            self.setStyleSheet(
                f"background-color: {spec['bg']}; color: {spec['fg']}; "
                f"border: 1px solid {spec['border']}; border-radius: 4px; "
                f"font-size: 11px; font-weight: bold; padding: 2px 6px;"
            )
            self.setAlignment(Qt.AlignCenter)
except ImportError:
    pass
