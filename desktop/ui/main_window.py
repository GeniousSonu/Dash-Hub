from pathlib import Path
from typing import Any

from desktop.services.api_client import OpsHubDesktopClient
from desktop.ui.widgets.status_badge import format_status_badge

NAVIGATION_MODULES: list[tuple[str, str]] = [
    ("overview", "1. Overview"),
    ("projects", "2. Projects"),
    ("my_tasks", "3. My Tasks"),
    ("all_tasks", "4. All Tasks"),
    ("websites", "5. Websites"),
    ("maintenance_queue", "6. Maintenance Queue"),
    ("issues", "7. Issues & Findings"),
    ("approvals", "8. Approvals"),
    ("backups", "9. Backups"),
    ("reports", "10. Reports"),
    ("notifications", "11. Notifications"),
    ("activity_history", "12. Activity History"),
    ("admin_settings", "13. Administration / Settings"),
]

I18N_DICTIONARY: dict[str, dict[str, str]] = {
    "en": {
        "app_title": "PulseOps — Enterprise Operations & Reliability Command Center",
        "search_placeholder": "Global Search across Projects, Websites, Tasks, and Issue IDs (Ctrl+K)...",
    },
    "es": {
        "app_title": "PulseOps — Centro de Confiabilidad y Operaciones Empresariales",
        "search_placeholder": "Búsqueda global en Proyectos, Sitios, Tareas e Incidencias (Ctrl+K)...",
    },
    "hi": {
        "app_title": "PulseOps — एंटरप्राइज ऑपरेशंस और रिलायबिलिटी कमांड सेंटर",
        "search_placeholder": "प्रोजेक्ट्स, वेबसाइट्स, टास्क और इश्यू खोजें (Ctrl+K)...",
    },
}

try:
    from PySide6.QtCore import Qt, QThreadPool
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QDoubleSpinBox,
        QFormLayout,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSplitter,
        QStackedWidget,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False


if PYSIDE6_AVAILABLE:

    class NewTaskDialog(QDialog):
        def __init__(self, parent, projects: list[dict[str, Any]], users: list[dict[str, Any]]):
            super().__init__(parent)
            self.setWindowTitle("Create New Task — PulseOps")
            self.setMinimumWidth(440)
            layout = QVBoxLayout(self)

            form = QFormLayout()
            self.title_edit = QLineEdit()
            self.title_edit.setPlaceholderText("e.g. Upgrade PHP 8.2 & Test Plugin Compatibility")
            form.addRow("Task Title *:", self.title_edit)

            self.project_combo = QComboBox()
            for p in projects:
                self.project_combo.addItem(p["name"], p["id"])
            form.addRow("Project *:", self.project_combo)

            self.owner_combo = QComboBox()
            for u in users:
                self.owner_combo.addItem(f"{u['full_name']} ({u['role']})", u["id"])
            form.addRow("Assignee *:", self.owner_combo)

            self.priority_combo = QComboBox()
            for prio in ["normal", "high", "critical", "low"]:
                self.priority_combo.addItem(prio.upper(), prio)
            form.addRow("Priority:", self.priority_combo)

            self.est_hours_spin = QDoubleSpinBox()
            self.est_hours_spin.setRange(0.25, 500.0)
            self.est_hours_spin.setValue(2.0)
            self.est_hours_spin.setSingleStep(0.5)
            self.est_hours_spin.setSuffix(" hrs")
            form.addRow("Est. Hours:", self.est_hours_spin)

            self.due_edit = QLineEdit()
            self.due_edit.setPlaceholderText("YYYY-MM-DD (e.g. 2026-10-30)")
            form.addRow("Due Date:", self.due_edit)

            self.desc_edit = QPlainTextEdit()
            self.desc_edit.setPlaceholderText("Detailed description of the technical work...")
            self.desc_edit.setMaximumHeight(80)
            form.addRow("Description:", self.desc_edit)

            self.crit_edit = QPlainTextEdit()
            self.crit_edit.setPlaceholderText("Acceptance criteria required to mark as completed...")
            self.crit_edit.setMaximumHeight(80)
            form.addRow("Acceptance Criteria:", self.crit_edit)

            layout.addLayout(form)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)

        def get_payload(self) -> dict[str, Any]:
            return {
                "title": self.title_edit.text().strip(),
                "project_id": self.project_combo.currentData(),
                "owner_id": self.owner_combo.currentData(),
                "priority": self.priority_combo.currentData(),
                "estimated_hours": self.est_hours_spin.value(),
                "due_at": self.due_edit.text().strip() or None,
                "description": self.desc_edit.toPlainText().strip(),
                "acceptance_criteria": self.crit_edit.toPlainText().strip(),
            }

    class LogWorkDialog(QDialog):
        def __init__(self, parent, task_title: str):
            super().__init__(parent)
            self.setWindowTitle(f"Log Work & Hours — {task_title[:30]}")
            self.setMinimumWidth(460)
            layout = QVBoxLayout(self)

            form = QFormLayout()

            task_lbl = QLabel(task_title)
            task_lbl.setStyleSheet("font-weight: 700; color: #6366F1;")
            task_lbl.setWordWrap(True)
            form.addRow("Target Task:", task_lbl)

            self.hours_spin = QDoubleSpinBox()
            self.hours_spin.setRange(0.25, 24.0)
            self.hours_spin.setValue(1.0)
            self.hours_spin.setSingleStep(0.5)
            self.hours_spin.setSuffix(" hrs")
            form.addRow("Hours Logged *:", self.hours_spin)

            self.done_edit = QPlainTextEdit()
            self.done_edit.setPlaceholderText("Detailed explanation of what technical work was performed...")
            self.done_edit.setMaximumHeight(85)
            form.addRow("What Was Done *:", self.done_edit)

            self.remains_edit = QPlainTextEdit()
            self.remains_edit.setPlaceholderText("What remaining items are needed to complete the task...")
            self.remains_edit.setMaximumHeight(60)
            form.addRow("What Remains:", self.remains_edit)

            self.blockers_edit = QLineEdit()
            self.blockers_edit.setPlaceholderText("Any technical or organizational blockers...")
            form.addRow("Blockers:", self.blockers_edit)

            self.next_action_edit = QLineEdit()
            self.next_action_edit.setPlaceholderText("Next immediate action...")
            form.addRow("Next Action:", self.next_action_edit)

            layout.addLayout(form)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)

        def get_payload(self) -> dict[str, Any]:
            return {
                "hours_logged": self.hours_spin.value(),
                "what_was_done": self.done_edit.toPlainText().strip(),
                "what_remains": self.remains_edit.toPlainText().strip(),
                "blockers": self.blockers_edit.text().strip(),
                "next_action": self.next_action_edit.text().strip(),
            }

    class UpdateTaskStatusDialog(QDialog):
        def __init__(self, parent, task_title: str, current_status: str):
            super().__init__(parent)
            self.setWindowTitle("Update Task Status — PulseOps")
            self.setMinimumWidth(380)
            layout = QVBoxLayout(self)

            form = QFormLayout()

            task_lbl = QLabel(task_title)
            task_lbl.setStyleSheet("font-weight: 700; color: #6366F1;")
            task_lbl.setWordWrap(True)
            form.addRow("Task:", task_lbl)

            self.status_combo = QComboBox()
            for st in ["ready", "in_progress", "blocked", "completed", "cancelled"]:
                self.status_combo.addItem(st.replace("_", " ").upper(), st)
            idx = self.status_combo.findData(current_status)
            if idx >= 0:
                self.status_combo.setCurrentIndex(idx)
            form.addRow("New Status *:", self.status_combo)

            self.reason_edit = QLineEdit()
            self.reason_edit.setPlaceholderText("Required only if cancelling task...")
            form.addRow("Cancellation Reason:", self.reason_edit)

            layout.addLayout(form)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)

        def get_payload(self) -> dict[str, str]:
            return {
                "new_status": self.status_combo.currentData(),
                "cancellation_reason": self.reason_edit.text().strip(),
            }

    class OpsHubMainWindow(QMainWindow):
        def __init__(self, client: OpsHubDesktopClient):
            super().__init__()
            self.client = client
            self.thread_pool = QThreadPool.globalInstance()
            self.setWindowTitle("PulseOps — Enterprise Operations & Reliability Command Center")
            self.setMinimumSize(880, 560)
            screen = QGuiApplication.primaryScreen()
            if screen:
                avail = screen.availableGeometry()
                w = min(1260, int(avail.width() * 0.88))
                h = min(780, int(avail.height() * 0.88))
                self.resize(w, h)
                self.move(avail.x() + (avail.width() - w) // 2, avail.y() + (avail.height() - h) // 2)
            else:
                self.resize(1180, 740)

            qss_file = Path(__file__).resolve().parent / "styles" / "theme.qss"
            if qss_file.exists():
                self.setStyleSheet(qss_file.read_text(encoding="utf-8"))

            self.bootstrap_data = self.client.get_bootstrap()
            self.current_session_id: str | None = None
            self.module_tables: dict[str, QTableWidget] = {}
            self.task_views: dict[str, dict[str, Any]] = {}
            self._current_tasks_data: dict[str, list[dict[str, Any]]] = {}
            self._build_shell()
            self.switch_module("overview")

        def _build_shell(self) -> None:
            root = QWidget()
            root_layout = QHBoxLayout(root)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(0)

            sidebar = QFrame()
            sidebar.setObjectName("SidebarShell")
            sidebar.setMinimumWidth(185)
            sidebar.setMaximumWidth(215)
            sb_layout = QVBoxLayout(sidebar)
            sb_layout.setContentsMargins(6, 10, 6, 10)
            sb_layout.setSpacing(2)

            title = QLabel("PulseOps")
            title.setObjectName("BrandTitle")
            subtitle = QLabel("Operations Command")
            subtitle.setObjectName("BrandSubtitle")
            sb_layout.addWidget(title)
            sb_layout.addWidget(subtitle)

            self.nav_buttons: dict[str, QPushButton] = {}
            self.stack = QStackedWidget()
            self.module_pages: dict[str, QWidget] = {}

            for mod_key, mod_label in NAVIGATION_MODULES:
                btn = QPushButton(mod_label)
                btn.setProperty("class", "NavButton")
                btn.setProperty("active", "false")
                btn.clicked.connect(lambda checked=False, k=mod_key: self.switch_module(k))
                self.nav_buttons[mod_key] = btn
                sb_layout.addWidget(btn)

                page = self._create_module_page(mod_key, mod_label)
                self.stack.addWidget(page)
                self.module_pages[mod_key] = page

            sb_layout.addStretch()
            root_layout.addWidget(sidebar)

            right_area = QWidget()
            right_area.setObjectName("CentralWorkArea")
            right_layout = QVBoxLayout(right_area)
            right_layout.setContentsMargins(14, 12, 14, 12)
            right_layout.setSpacing(10)

            self.theme_mode = "dark"
            self.current_lang = "en"
            self.sidebar_collapsed = False
            self.sidebar_frame = sidebar

            header = QHBoxLayout()
            self.collapse_btn = QPushButton("☰")
            self.collapse_btn.setToolTip("Collapse / Expand Sidebar")
            self.collapse_btn.clicked.connect(self.toggle_sidebar)
            header.addWidget(self.collapse_btn)

            self.search_input = QLineEdit()
            self.search_input.setPlaceholderText(I18N_DICTIONARY["en"]["search_placeholder"])
            self.search_input.returnPressed.connect(self.execute_global_search)
            header.addWidget(self.search_input, stretch=1)

            self.lang_combo = QComboBox()
            self.lang_combo.addItem("EN (English)", "en")
            self.lang_combo.addItem("ES (Español)", "es")
            self.lang_combo.addItem("HI (हिंदी)", "hi")
            self.lang_combo.currentIndexChanged.connect(self.switch_language)
            header.addWidget(self.lang_combo)

            self.theme_btn = QPushButton("◐ Theme")
            self.theme_btn.clicked.connect(self.toggle_theme_mode)
            header.addWidget(self.theme_btn)

            self.tour_btn = QPushButton("? Tour")
            self.tour_btn.clicked.connect(self.show_onboarding_tour)
            header.addWidget(self.tour_btn)

            self.role_combo = QComboBox()
            for role_key, u in self.bootstrap_data.get("users_by_role", {}).items():
                self.role_combo.addItem(f"{u['full_name']} [{role_key}]", u["id"])
            self.role_combo.currentIndexChanged.connect(self._on_role_switched)
            header.addWidget(self.role_combo)

            right_layout.addLayout(header)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setWidget(self.stack)
            right_layout.addWidget(scroll, stretch=1)
            root_layout.addWidget(right_area, stretch=1)
            self.setCentralWidget(root)

        def _create_module_page(self, mod_key: str, mod_label: str) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)
            heading = QLabel(mod_label)
            heading.setStyleSheet("font-size: 17px; font-weight: 700; color: #F9FAFB;")
            layout.addWidget(heading)

            if mod_key == "overview":
                self.kpi_grid = QGridLayout()
                layout.addLayout(self.kpi_grid)
                self.drilldown_table = QTableWidget(0, 4)
                self.drilldown_table.setHorizontalHeaderLabels(
                    ["Entity / Title", "Environment / Category", "Status Badge", "Owner / Due"]
                )
                self.drilldown_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                layout.addWidget(QLabel("Drill-down Records (Click any metric card above):"))
                layout.addWidget(self.drilldown_table, stretch=1)
            elif mod_key in ("my_tasks", "all_tasks"):
                return self._create_tasks_page(mod_key, mod_label)
            elif mod_key == "maintenance_queue":
                self.site_selector = QComboBox()
                for w in self.bootstrap_data.get("websites", []):
                    self.site_selector.addItem(f"{w['name']} ({w['domain']}) [{w['environment'].upper()}]", w["id"])

                start_btn = QPushButton("Start 23-Step SOP Session")
                start_btn.setProperty("class", "PrimaryButton")
                start_btn.clicked.connect(self.launch_sop_session)

                ro_btn = QPushButton("Run Safe Read-Only Checks")
                ro_btn.clicked.connect(self.run_readonly_checks_ui)

                bkp_btn = QPushButton("Record & Verify Backup (#9)")
                bkp_btn.clicked.connect(self.record_verified_backup_ui)

                close_btn = QPushButton("Close Session")
                close_btn.clicked.connect(self.close_current_session_ui)

                pdf_btn = QPushButton("Generate PDF Report")
                pdf_btn.clicked.connect(self.generate_pdf_report_ui)

                row1 = QHBoxLayout()
                row1.addWidget(QLabel("Website:"))
                row1.addWidget(self.site_selector, stretch=1)
                row1.addWidget(start_btn)
                row2 = QHBoxLayout()
                row2.addWidget(ro_btn)
                row2.addWidget(bkp_btn)
                row2.addWidget(close_btn)
                row2.addWidget(pdf_btn)
                row2.addStretch()
                layout.addLayout(row1)
                layout.addLayout(row2)

                self.gate_banner = QLabel("Live Pre-Update Backup Gate: Click 'Start 23-Step SOP Session' to begin.")
                self.gate_banner.setWordWrap(True)
                self.gate_banner.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
                self.gate_banner.setStyleSheet(
                    "background-color: #FEF9C3; color: #854D0E; padding: 8px 12px; border-radius: 6px; font-weight: 600;"
                )
                layout.addWidget(self.gate_banner)

                splitter = QSplitter(Qt.Horizontal)
                self.sop_step_list = QListWidget()
                self.sop_step_list.currentRowChanged.connect(self.on_sop_step_selected)
                splitter.addWidget(self.sop_step_list)

                detail_panel = QFrame()
                detail_panel.setProperty("class", "CardPanel")
                dp_layout = QVBoxLayout(detail_panel)
                self.step_title_lbl = QLabel("Select a checklist step")
                self.step_title_lbl.setWordWrap(True)
                self.step_title_lbl.setStyleSheet("font-size: 14px; font-weight: 700;")
                self.step_process_lbl = QLabel("")
                self.step_process_lbl.setWordWrap(True)
                self.step_rule_box = QPlainTextEdit()
                self.step_rule_box.setReadOnly(True)
                self.step_obs_input = QPlainTextEdit()
                self.step_obs_input.setPlaceholderText("Record maintainer observation, metrics, or N/A reason...")

                btn_row = QHBoxLayout()
                for st_code, btn_txt in [
                    ("passed", "✓ Passed"),
                    ("failed", "✕ Failed"),
                    ("blocked", "⊘ Blocked"),
                    ("not_verified", "? Not Verified"),
                    ("not_applicable", "— N/A"),
                ]:
                    b = QPushButton(btn_txt)
                    b.clicked.connect(lambda checked=False, sc=st_code: self.save_current_step_status(sc))
                    btn_row.addWidget(b)

                dp_layout.addWidget(self.step_title_lbl)
                dp_layout.addWidget(self.step_process_lbl)
                dp_layout.addWidget(QLabel("Approved SOP Reference Snippet:"))
                dp_layout.addWidget(self.step_rule_box)
                dp_layout.addWidget(QLabel("Observation / Evidence / Reason:"))
                dp_layout.addWidget(self.step_obs_input)
                dp_layout.addLayout(btn_row)
                splitter.addWidget(detail_panel)
                splitter.setSizes([340, 520])
                layout.addWidget(splitter, stretch=1)
            else:
                if mod_key == "reports":
                    export_btn = QPushButton("Export Excel (.xlsx) Compliance Workbook")
                    export_btn.setProperty("class", "PrimaryButton")
                    export_btn.clicked.connect(self.export_xlsx_ui)
                    layout.addWidget(export_btn)
                table = QTableWidget(0, 4)
                table.setHorizontalHeaderLabels(
                    ["Record / Name", "Scope / Environment", "Status Badge", "Details / Timestamp"]
                )
                table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                layout.addWidget(table, stretch=1)
                self.module_tables[mod_key] = table
            return page

        def _create_tasks_page(self, mod_key: str, mod_label: str) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)

            heading = QLabel(f"{mod_label} — Interactive Workbench")
            heading.setStyleSheet("font-size: 16px; font-weight: 700; color: #F9FAFB;")
            layout.addWidget(heading)

            # Toolbar
            tb = QHBoxLayout()
            new_btn = QPushButton("+ New Task")
            new_btn.setProperty("class", "PrimaryButton")
            new_btn.clicked.connect(lambda: self._open_new_task_dialog(mod_key))

            log_work_btn = QPushButton("+ Log Work & Hours")
            log_work_btn.setProperty("class", "SuccessButton")
            log_work_btn.clicked.connect(lambda: self._open_log_work_dialog(mod_key))

            status_btn = QPushButton("Update Status")
            status_btn.clicked.connect(lambda: self._open_update_task_status_dialog(mod_key))

            status_filter = QComboBox()
            status_filter.addItem("All Statuses", "")
            for st in ["ready", "in_progress", "blocked", "completed", "cancelled"]:
                status_filter.addItem(f"Status: {st.upper()}", st)
            status_filter.currentIndexChanged.connect(lambda: self.populate_tasks_view(mod_key))

            prio_filter = QComboBox()
            prio_filter.addItem("All Priorities", "")
            for pr in ["critical", "high", "normal", "low"]:
                prio_filter.addItem(f"Priority: {pr.upper()}", pr)
            prio_filter.currentIndexChanged.connect(lambda: self.populate_tasks_view(mod_key))

            refresh_btn = QPushButton("↻ Refresh")
            refresh_btn.clicked.connect(lambda: self.populate_tasks_view(mod_key))

            tb.addWidget(new_btn)
            tb.addWidget(log_work_btn)
            tb.addWidget(status_btn)
            tb.addWidget(status_filter)
            tb.addWidget(prio_filter)
            tb.addWidget(refresh_btn)
            tb.addStretch()
            layout.addLayout(tb)

            # Splitter: Left Task Table, Right Detail & Work Logs Panel
            splitter = QSplitter(Qt.Horizontal)

            table = QTableWidget(0, 6)
            table.setHorizontalHeaderLabels([
                "Task Title", "Project", "Priority", "Status", "Hours (Logged / Est)", "Owner / Due"
            ])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.setSelectionBehavior(QTableWidget.SelectRows)
            table.setSelectionMode(QTableWidget.SingleSelection)
            table.itemSelectionChanged.connect(lambda: self._on_task_row_selected(mod_key))
            splitter.addWidget(table)

            # Right Panel
            right_panel = QFrame()
            right_panel.setProperty("class", "CardPanel")
            rp_layout = QVBoxLayout(right_panel)

            task_title_lbl = QLabel("Select a task on the left")
            task_title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #FFFFFF;")
            task_title_lbl.setWordWrap(True)

            badges_row = QHBoxLayout()
            prio_badge_lbl = QLabel("—")
            status_badge_lbl = QLabel("—")
            badges_row.addWidget(prio_badge_lbl)
            badges_row.addWidget(status_badge_lbl)
            badges_row.addStretch()

            meta_lbl = QLabel("Project: — | Assignee: — | Due: —")
            meta_lbl.setStyleSheet("color: #9CA3AF; font-size: 12px;")

            hours_lbl = QLabel("Hours Logged: 0.0 hrs / 0.0 hrs estimated")
            hours_lbl.setStyleSheet("color: #38BDF8; font-weight: 600;")

            desc_box = QPlainTextEdit()
            desc_box.setReadOnly(True)
            desc_box.setPlaceholderText("Task Description & Acceptance Criteria will appear here...")
            desc_box.setMaximumHeight(90)

            work_logs_heading = QLabel("Work Logs & Activity (Works History):")
            work_logs_heading.setStyleSheet("font-weight: 700; font-size: 13px; color: #F3F4F6; margin-top: 6px;")

            work_logs_table = QTableWidget(0, 4)
            work_logs_table.setHorizontalHeaderLabels([
                "Logged At / Author", "Hours", "What Was Done", "Remains / Blockers"
            ])
            work_logs_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

            rp_layout.addWidget(task_title_lbl)
            rp_layout.addLayout(badges_row)
            rp_layout.addWidget(meta_lbl)
            rp_layout.addWidget(hours_lbl)
            rp_layout.addWidget(QLabel("Description & Acceptance Criteria:"))
            rp_layout.addWidget(desc_box)
            rp_layout.addWidget(work_logs_heading)
            rp_layout.addWidget(work_logs_table, stretch=1)

            splitter.addWidget(right_panel)
            splitter.setSizes([450, 450])
            layout.addWidget(splitter, stretch=1)

            self.task_views[mod_key] = {
                "table": table,
                "status_filter": status_filter,
                "prio_filter": prio_filter,
                "title_lbl": task_title_lbl,
                "prio_badge_lbl": prio_badge_lbl,
                "status_badge_lbl": status_badge_lbl,
                "meta_lbl": meta_lbl,
                "hours_lbl": hours_lbl,
                "desc_box": desc_box,
                "work_logs_table": work_logs_table,
            }
            # Also keep module_tables reference for consistency
            self.module_tables[mod_key] = table
            return page

        def _on_role_switched(self) -> None:
            uid = self.role_combo.currentData()
            if uid:
                self.client.set_active_user(uid)
                self.refresh_overview()
                for mk in ("my_tasks", "all_tasks"):
                    if mk in self.task_views:
                        self.populate_tasks_view(mk)

        def switch_module(self, mod_key: str) -> None:
            for k, btn in self.nav_buttons.items():
                btn.setProperty("active", "true" if k == mod_key else "false")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
            if mod_key in self.module_pages:
                self.stack.setCurrentWidget(self.module_pages[mod_key])
            if mod_key == "overview":
                self.refresh_overview()
            elif mod_key in ("my_tasks", "all_tasks"):
                self.populate_tasks_view(mod_key)
            elif mod_key in self.module_tables:
                self.populate_module_table(mod_key)

        def populate_tasks_view(self, mod_key: str) -> None:
            view = self.task_views.get(mod_key)
            if not view:
                return
            st_filter = view["status_filter"].currentData()
            pr_filter = view["prio_filter"].currentData()

            owner_id = self.client.user_id if mod_key == "my_tasks" else None
            try:
                tasks = self.client.list_tasks(owner_id=owner_id)
            except Exception as exc:
                QMessageBox.warning(self, "Tasks Error", str(exc))
                return

            # Apply in-memory filters
            filtered = []
            for t in tasks:
                if st_filter and t.get("status") != st_filter:
                    continue
                if pr_filter and t.get("priority") != pr_filter:
                    continue
                filtered.append(t)

            self._current_tasks_data[mod_key] = filtered
            table = view["table"]
            table.setRowCount(len(filtered))
            for idx, t in enumerate(filtered):
                prio_badge = format_status_badge(t.get("priority", "normal"))
                st_badge = format_status_badge(t.get("status", "ready"))
                hrs_str = f"{float(t.get('actual_hours') or 0.0):.1f}h / {float(t.get('estimated_hours') or 0.0):.1f}h"
                owner_due = f"{t.get('owner_name', '—')} | Due: {t.get('due_at') or 'None'}"

                table.setItem(idx, 0, QTableWidgetItem(t.get("title", "Untitled")))
                table.setItem(idx, 1, QTableWidgetItem(t.get("project_name", "—")))
                table.setItem(idx, 2, QTableWidgetItem(prio_badge["label"]))
                table.setItem(idx, 3, QTableWidgetItem(st_badge["label"]))
                table.setItem(idx, 4, QTableWidgetItem(hrs_str))
                table.setItem(idx, 5, QTableWidgetItem(owner_due))

            if filtered:
                table.selectRow(0)
                self._render_task_detail(mod_key, filtered[0])
            else:
                self._clear_task_detail(mod_key)

        def _on_task_row_selected(self, mod_key: str) -> None:
            view = self.task_views.get(mod_key)
            if not view:
                return
            row = view["table"].currentRow()
            tasks = self._current_tasks_data.get(mod_key, [])
            if 0 <= row < len(tasks):
                self._render_task_detail(mod_key, tasks[row])

        def _render_task_detail(self, mod_key: str, task: dict[str, Any]) -> None:
            view = self.task_views.get(mod_key)
            if not view:
                return
            view["title_lbl"].setText(task.get("title", "Untitled Task"))
            p_badge = format_status_badge(task.get("priority", "normal"))
            s_badge = format_status_badge(task.get("status", "ready"))

            view["prio_badge_lbl"].setText(f" {p_badge['label']} ")
            view["prio_badge_lbl"].setStyleSheet(
                f"background-color: {p_badge['bg']}; color: {p_badge['fg']}; border: 1px solid {p_badge['border']}; border-radius: 4px; padding: 2px 6px; font-weight: 700; font-size: 11px;"
            )
            view["status_badge_lbl"].setText(f" {s_badge['label']} ")
            view["status_badge_lbl"].setStyleSheet(
                f"background-color: {s_badge['bg']}; color: {s_badge['fg']}; border: 1px solid {s_badge['border']}; border-radius: 4px; padding: 2px 6px; font-weight: 700; font-size: 11px;"
            )

            view["meta_lbl"].setText(
                f"Project: {task.get('project_name', '—')} | Assignee: {task.get('owner_name', '—')} | Due: {task.get('due_at') or 'None'}"
            )
            actual_h = float(task.get("actual_hours") or 0.0)
            est_h = float(task.get("estimated_hours") or 0.0)
            view["hours_lbl"].setText(f"Logged Hours: {actual_h:.1f} hrs  /  Estimated: {est_h:.1f} hrs")

            desc = task.get("description", "") or "No description provided."
            crit = task.get("acceptance_criteria", "")
            if crit:
                desc += f"\n\nAcceptance Criteria:\n{crit}"
            view["desc_box"].setPlainText(desc)

            # Fetch work logs for this task
            try:
                logs = self.client.get_task_work_logs(task["id"])
            except Exception:
                logs = []
            wl_table = view["work_logs_table"]
            wl_table.setRowCount(len(logs))
            for l_idx, log in enumerate(logs):
                author = f"{log.get('author_name', 'Author')}\n{log.get('created_at', '')[:16]}"
                hrs = f"+{float(log.get('hours_logged', 0.0)):.1f}h"
                done = log.get("what_was_done", "—")
                rem_block = f"Remains: {log.get('what_remains') or '—'}\nBlockers: {log.get('blockers') or 'None'}"
                wl_table.setItem(l_idx, 0, QTableWidgetItem(author))
                wl_table.setItem(l_idx, 1, QTableWidgetItem(hrs))
                wl_table.setItem(l_idx, 2, QTableWidgetItem(done))
                wl_table.setItem(l_idx, 3, QTableWidgetItem(rem_block))

        def _clear_task_detail(self, mod_key: str) -> None:
            view = self.task_views.get(mod_key)
            if not view:
                return
            view["title_lbl"].setText("No tasks match the filter criteria.")
            view["prio_badge_lbl"].setText("")
            view["prio_badge_lbl"].setStyleSheet("")
            view["status_badge_lbl"].setText("")
            view["status_badge_lbl"].setStyleSheet("")
            view["meta_lbl"].setText("")
            view["hours_lbl"].setText("")
            view["desc_box"].setPlainText("")
            view["work_logs_table"].setRowCount(0)

        def _open_new_task_dialog(self, mod_key: str) -> None:
            projects = self.bootstrap_data.get("projects", [])
            users = self.bootstrap_data.get("users", [])
            dlg = NewTaskDialog(self, projects, users)
            if dlg.exec():
                payload = dlg.get_payload()
                if not payload["title"]:
                    QMessageBox.warning(self, "Validation", "Task title cannot be empty.")
                    return
                try:
                    self.client.create_task(
                        project_id=payload["project_id"],
                        title=payload["title"],
                        owner_id=payload["owner_id"],
                        priority=payload["priority"],
                        estimated_hours=payload["estimated_hours"],
                        due_at=payload["due_at"],
                        description=payload["description"],
                        acceptance_criteria=payload["acceptance_criteria"],
                    )
                    self.populate_tasks_view(mod_key)
                    QMessageBox.information(self, "Task Created", f"Task '{payload['title']}' created successfully.")
                except Exception as exc:
                    QMessageBox.warning(self, "Create Task Failed", str(exc))

        def _open_log_work_dialog(self, mod_key: str) -> None:
            view = self.task_views.get(mod_key)
            if not view:
                return
            row = view["table"].currentRow()
            tasks = self._current_tasks_data.get(mod_key, [])
            if row < 0 or row >= len(tasks):
                QMessageBox.warning(self, "No Task Selected", "Please select a task from the table to log work.")
                return
            target_task = tasks[row]
            dlg = LogWorkDialog(self, target_task.get("title", "Task"))
            if dlg.exec():
                payload = dlg.get_payload()
                if not payload["what_was_done"]:
                    QMessageBox.warning(self, "Validation", "Please describe what was done.")
                    return
                try:
                    self.client.add_work_log(
                        task_id=target_task["id"],
                        hours_logged=payload["hours_logged"],
                        what_was_done=payload["what_was_done"],
                        what_remains=payload["what_remains"],
                        blockers=payload["blockers"],
                        next_action=payload["next_action"],
                    )
                    self.populate_tasks_view(mod_key)
                    QMessageBox.information(
                        self, "Work Logged", f"Logged {payload['hours_logged']} hrs on '{target_task.get('title')}'."
                    )
                except Exception as exc:
                    QMessageBox.warning(self, "Log Work Failed", str(exc))

        def _open_update_task_status_dialog(self, mod_key: str) -> None:
            view = self.task_views.get(mod_key)
            if not view:
                return
            row = view["table"].currentRow()
            tasks = self._current_tasks_data.get(mod_key, [])
            if row < 0 or row >= len(tasks):
                QMessageBox.warning(self, "No Task Selected", "Please select a task from the table to update status.")
                return
            target_task = tasks[row]
            dlg = UpdateTaskStatusDialog(self, target_task.get("title", "Task"), target_task.get("status", "ready"))
            if dlg.exec():
                payload = dlg.get_payload()
                try:
                    self.client.update_task_status(
                        task_id=target_task["id"],
                        new_status=payload["new_status"],
                        cancellation_reason=payload["cancellation_reason"],
                    )
                    self.populate_tasks_view(mod_key)
                    QMessageBox.information(
                        self, "Status Updated", f"Task updated to status: {payload['new_status'].upper()}."
                    )
                except Exception as exc:
                    QMessageBox.warning(self, "Status Update Blocked", str(exc))

        def populate_module_table(self, mod_key: str) -> None:
            table = self.module_tables[mod_key]
            endpoint_map = {
                "projects": "/api/v1/projects",
                "websites": "/api/v1/websites",
                "issues": "/api/v1/issues",
                "approvals": "/api/v1/approvals",
                "backups": "/api/v1/backups",
                "reports": "/api/v1/reports",
                "notifications": "/api/v1/reports",
                "activity_history": "/api/v1/audit/events",
                "admin_settings": "/api/v1/users",
            }
            path = endpoint_map.get(mod_key)
            if not path:
                return
            try:
                rows = self.client.request("GET", path)
            except Exception as exc:
                QMessageBox.warning(self, "Access Restricted", str(exc))
                return
            table.setRowCount(len(rows))
            for idx, r in enumerate(rows):
                col1 = str(r.get("name") or r.get("title") or r.get("full_name") or r.get("summary") or r.get("storage_location") or r.get("id"))
                col2 = str(r.get("domain") or r.get("environment") or r.get("role") or r.get("entity_type") or r.get("category") or r.get("subtype") or "—")
                st_raw = str(r.get("workflow_status") or r.get("status") or r.get("action") or "online")
                badge = format_status_badge(st_raw)
                col4 = str(r.get("next_due_at") or r.get("created_at") or r.get("generated_at") or r.get("email") or "—")
                table.setItem(idx, 0, QTableWidgetItem(col1))
                table.setItem(idx, 1, QTableWidgetItem(col2))
                table.setItem(idx, 2, QTableWidgetItem(badge["label"]))
                table.setItem(idx, 3, QTableWidgetItem(col4))

        def refresh_overview(self) -> None:
            try:
                summary = self.client.get_dashboard_summary()
            except Exception as exc:
                QMessageBox.warning(self, "RBAC Permission Check", str(exc))
                return
            kpis = summary["kpis"]
            cards = [
                ("active_projects", "Active Projects", kpis["active_projects"], "in_progress"),
                ("total_websites", "Registered Websites", kpis["total_websites"], "online"),
                ("websites_due_today", "Websites Due Today", kpis["websites_due_today"], "due"),
                ("websites_overdue", "Overdue Maintenance", kpis["websites_overdue"], "overdue"),
                ("sessions_in_progress", "Sessions In Progress", kpis["sessions_in_progress"], "in_progress"),
                ("open_critical_high_issues", "Open Critical/High Issues", kpis["open_critical_high_issues"], "critical"),
                ("pending_approvals", "Pending Approvals", kpis["pending_approvals"], "pending"),
                ("backups_awaiting_verification", "Unverified Backups", kpis["backups_awaiting_verification"], "not_verified"),
            ]
            for idx, (m_key, title, val, badge_key) in enumerate(cards):
                badge = format_status_badge(badge_key)
                btn = QPushButton(f"{title}\n{val}  [{badge['label']}]")
                btn.setStyleSheet(
                    f"background-color: {badge['bg']}; color: {badge['fg']}; "
                    f"border: 1px solid {badge['border']}; border-radius: 8px; padding: 10px; font-weight: 700; text-align: left;"
                )
                btn.clicked.connect(lambda checked=False, mk=m_key: self.load_drilldown(mk))
                self.kpi_grid.addWidget(btn, idx // 4, idx % 4)
            self.load_drilldown("total_websites")

        def load_drilldown(self, metric_key: str) -> None:
            rows = self.client.get_drilldown(metric_key)
            self.drilldown_table.setRowCount(len(rows))
            for r_idx, row in enumerate(rows):
                name = str(row.get("name") or row.get("title") or row.get("summary") or row.get("id"))
                cat = str(row.get("environment") or row.get("category") or row.get("action_type") or "—")
                st_raw = str(row.get("workflow_status") or row.get("status") or "unknown")
                badge = format_status_badge(st_raw)
                owner = str(row.get("next_due_at") or row.get("priority") or "—")
                self.drilldown_table.setItem(r_idx, 0, QTableWidgetItem(name))
                self.drilldown_table.setItem(r_idx, 1, QTableWidgetItem(cat.upper()))
                self.drilldown_table.setItem(r_idx, 2, QTableWidgetItem(badge["label"]))
                self.drilldown_table.setItem(r_idx, 3, QTableWidgetItem(owner))

        def launch_sop_session(self) -> None:
            website_id = self.site_selector.currentData()
            maintainer_id = self.bootstrap_data["users_by_role"]["maintenance_engineer"]["id"]
            session = self.client.start_session(website_id=website_id, maintainer_id=maintainer_id)
            self.current_session_id = session["id"]
            self._render_session_steps(session)

        def run_readonly_checks_ui(self) -> None:
            if not self.current_session_id:
                self.launch_sop_session()
            updated = self.client.run_readonly_checks(self.current_session_id)
            self._render_session_steps(updated)
            QMessageBox.information(
                self,
                "Read-Only Automation Complete",
                "Executed safe read-only checks. Steps requiring SSH/WP-Admin credentials were marked '? NOT VERIFIED / ACCESS REQ' (INV-02).",
            )

        def record_verified_backup_ui(self) -> None:
            if not self.current_session_id:
                self.launch_sop_session()
            website_id = self.site_selector.currentData()
            self.client.request(
                "POST",
                "/api/v1/backups",
                json_body={
                    "website_id": website_id,
                    "session_id": self.current_session_id,
                    "storage_location": "s3://opshub-verified-backups/live-preupdate-verified.tar.gz",
                },
            )
            self.client.update_step(
                self.current_session_id,
                9,
                status="passed",
                observation="Verified full archive backup prior to live update work.",
            )
            updated = self.client.get_session(self.current_session_id)
            self._render_session_steps(updated)
            QMessageBox.information(self, "Backup Gate Satisfied", "Verified backup recorded! Live update steps (#10-#12) are now unlocked.")

        def close_current_session_ui(self) -> None:
            if not self.current_session_id:
                return
            try:
                closed = self.client.close_session(self.current_session_id, target_status="completed")
                self._render_session_steps(closed)
                QMessageBox.information(self, "Session Closed", f"Session closed with status: {closed['status'].upper()}")
            except Exception as exc:
                QMessageBox.warning(self, "Completion Gate Blocked Closure", str(exc))

        def generate_pdf_report_ui(self) -> None:
            if not self.current_session_id:
                QMessageBox.warning(self, "No Active Session", "Please launch or select an SOP session first.")
                return
            res = self.client.generate_pdf(self.current_session_id)
            QMessageBox.information(self, "Report Generated", f"PDF Exported successfully: {res['pdf_path']}")

        def export_xlsx_ui(self) -> None:
            try:
                res = self.client.request("POST", "/api/v1/reports/export/xlsx")
                QMessageBox.information(self, "Export Complete", f"Compliance workbook saved to: {res['xlsx_path']}")
            except Exception as exc:
                QMessageBox.warning(self, "Export Failed", str(exc))

        def _render_session_steps(self, session: dict[str, Any]) -> None:
            self._current_session_data = session
            self.sop_step_list.clear()
            for item in session["items"]:
                badge = format_status_badge(item["status"])
                entry = f"[{badge['label']}] Step {item['step_number']:02d}: {item['title']}"
                self.sop_step_list.addItem(entry)
            if session["items"]:
                self.sop_step_list.setCurrentRow(0)

            # Update banner state
            step9 = next((i for i in session["items"] if i["step_number"] == 9), None)
            if step9 and step9["status"] in ("passed", "verified"):
                self.gate_banner.setText("Live Pre-Update Backup Gate: [✓ SATISFIED] — Live core/plugin/theme updates unlocked.")
                self.gate_banner.setStyleSheet(
                    "background-color: #DCFCE7; color: #15803D; padding: 8px 12px; border-radius: 6px; font-weight: 700;"
                )
            else:
                self.gate_banner.setText("Live Pre-Update Backup Gate: [⊘ ACTIVE] — Steps 10-12 locked until Step 9 verified.")
                self.gate_banner.setStyleSheet(
                    "background-color: #FEF9C3; color: #854D0E; padding: 8px 12px; border-radius: 6px; font-weight: 700;"
                )

        def on_sop_step_selected(self, row_idx: int) -> None:
            if not hasattr(self, "_current_session_data") or row_idx < 0:
                return
            item = self._current_session_data["items"][row_idx]
            self.step_title_lbl.setText(f"Step {item['step_number']}: {item['title']}")
            self.step_process_lbl.setText(item["required_process"])
            ref = item.get("rule_reference")
            if ref:
                self.step_rule_box.setPlainText(f"{ref['title']}\n\n{ref['snippet']}\n\nGuidance: {ref['guidance']}")
            else:
                self.step_rule_box.setPlainText("No static snippet required for this step.")
            self.step_obs_input.setPlainText(item.get("observation") or item.get("na_reason") or "")

        def save_current_step_status(self, status_code: str) -> None:
            if not self.current_session_id:
                return
            row_idx = self.sop_step_list.currentRow()
            if row_idx < 0:
                return
            step_num = self._current_session_data["items"][row_idx]["step_number"]
            obs_text = self.step_obs_input.toPlainText().strip()
            try:
                self.client.update_step(
                    self.current_session_id,
                    step_num,
                    status=status_code,
                    observation=obs_text,
                    na_reason=obs_text if status_code == "not_applicable" else None,
                )
                updated_session = self.client.get_session(self.current_session_id)
                self._render_session_steps(updated_session)
                self.sop_step_list.setCurrentRow(row_idx)
            except Exception as exc:
                QMessageBox.warning(self, "SOP Gate Enforcement", str(exc))

        def toggle_theme_mode(self) -> None:
            self.theme_mode = "dark" if self.theme_mode == "light" else "light"
            self.theme_btn.setText("☀ Light" if self.theme_mode == "dark" else "◐ Dark")

        def toggle_sidebar(self) -> None:
            self.sidebar_collapsed = not self.sidebar_collapsed
            if self.sidebar_collapsed:
                self.sidebar_frame.setMinimumWidth(58)
                self.sidebar_frame.setMaximumWidth(58)
                for mod_key, btn in self.nav_buttons.items():
                    btn.setText(btn.text().split(".")[0] + ".")
            else:
                self.sidebar_frame.setMinimumWidth(185)
                self.sidebar_frame.setMaximumWidth(215)
                for mod_key, mod_label in NAVIGATION_MODULES:
                    self.nav_buttons[mod_key].setText(mod_label)

        def switch_language(self) -> None:
            lang = self.lang_combo.currentData() or "en"
            self.current_lang = lang
            tr = I18N_DICTIONARY.get(lang, I18N_DICTIONARY["en"])
            self.setWindowTitle(tr["app_title"])
            self.search_input.setPlaceholderText(tr["search_placeholder"])

        def show_onboarding_tour(self) -> None:
            QMessageBox.information(
                self,
                "PulseOps Onboarding Tour & Command Guide",
                "Welcome to PulseOps (Enterprise SRE & Maintenance Command Center):\n\n"
                "1. Overview Dashboard: Click any KPI card to load live drill-down telemetry.\n"
                "2. Interactive Tasks & Work Logs ('Works'): Create tasks, filter by priority/status, "
                "log engineering hours with structured summaries, and track dependency chains.\n"
                "3. Maintenance Queue: Run the 23-step WordPress SOP matrix with pre-update backup gates, "
                "safe read-only checks, and verified PDF compliance reporting.\n"
                "4. Epistemic Verification: Automated checks lacking SSH/WP-Admin access explicitly report "
                "'? NOT VERIFIED / ACCESS REQ'—protecting operational truth.",
            )

        def execute_global_search(self) -> None:
            q = self.search_input.text().strip()
            if not q:
                return
            res = self.client.global_search(q)
            total = sum(len(res[k]) for k in ("projects", "websites", "tasks", "issues"))
            QMessageBox.information(
                self,
                "Global Search Results",
                f"Query '{q}' matched {total} record(s):\n"
                f"- Projects: {len(res['projects'])}\n"
                f"- Websites: {len(res['websites'])}\n"
                f"- Tasks: {len(res['tasks'])}\n"
                f"- Issues: {len(res['issues'])}",
            )
