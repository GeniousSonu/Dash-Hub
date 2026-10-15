from pathlib import Path
from typing import Any

from desktop.services.api_client import OpsHubDesktopClient
from desktop.ui.widgets.status_badge import format_status_badge

try:
    from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
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

    class WorkerSignals(QObject):
        finished = Signal(object)
        error = Signal(str)

    class ApiTaskRunnable(QRunnable):
        """Runs API / long-running tasks in QThreadPool so the desktop UI never freezes."""

        def __init__(self, fn, *args, **kwargs):
            super().__init__()
            self.fn = fn
            self.args = args
            self.kwargs = kwargs
            self.signals = WorkerSignals()

        @Slot()
        def run(self) -> None:
            try:
                res = self.fn(*self.args, **self.kwargs)
                self.signals.finished.emit(res)
            except Exception as exc:
                self.signals.error.emit(str(exc))

    class OpsHubMainWindow(QMainWindow):
        """
        Main PySide6 Command Center Window implementing the 13 primary navigation modules,
        clickable dashboard KPI cards, global search, and the 23-step SOP checklist workbench.
        """

        def __init__(self, client: OpsHubDesktopClient):
            super().__init__()
            self.client = client
            self.thread_pool = QThreadPool.globalInstance()
            self.setWindowTitle("OpsHub — Maintenance & Project Operations Command Center")
            self.resize(1440, 900)

            qss_path = Path(__file__).resolve().parent / "styles/theme.qss"
            if qss_path.exists():
                self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

            self.bootstrap_data = self.client.get_bootstrap()
            self.current_session_id: str | None = None
            self._build_shell()
            self.refresh_overview()

        def _build_shell(self) -> None:
            root = QWidget()
            root_layout = QHBoxLayout(root)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(0)

            # Left Sidebar (13 Primary Navigation Views)
            sidebar = QFrame()
            sidebar.setObjectName("SidebarShell")
            sidebar.setFixedWidth(240)
            sb_layout = QVBoxLayout(sidebar)
            sb_layout.setContentsMargins(8, 12, 8, 12)
            sb_layout.setSpacing(4)

            title = QLabel("OpsHub")
            title.setObjectName("BrandTitle")
            subtitle = QLabel("Operations Command Center")
            subtitle.setObjectName("BrandSubtitle")
            sb_layout.addWidget(title)
            sb_layout.addWidget(subtitle)

            self.nav_buttons: dict[str, QPushButton] = {}
            self.stack = QStackedWidget()
            self.module_pages: dict[str, QWidget] = {}

            for mod_key, mod_label in OpsHubDesktopClient.NAVIGATION_MODULES:
                btn = QPushButton(mod_label)
                btn.setProperty("class", "NavButton")
                btn.clicked.connect(lambda checked=False, k=mod_key: self.switch_module(k))
                sb_layout.addWidget(btn)
                self.nav_buttons[mod_key] = btn

                page = self._create_module_page(mod_key, mod_label)
                self.stack.addWidget(page)
                self.module_pages[mod_key] = page

            sb_layout.addStretch()
            root_layout.addWidget(sidebar)

            # Right Main Area (Header + Stacked Module Pages)
            right_area = QWidget()
            right_area.setObjectName("CentralWorkArea")
            right_layout = QVBoxLayout(right_area)
            right_layout.setContentsMargins(20, 16, 20, 16)
            right_layout.setSpacing(14)

            header = QHBoxLayout()
            self.search_input = QLineEdit()
            self.search_input.setPlaceholderText("Global Search across Projects, Websites, Tasks, and Issue IDs...")
            self.search_input.returnPressed.connect(self.execute_global_search)
            header.addWidget(self.search_input, stretch=1)

            self.role_combo = QComboBox()
            for role_key, u in self.bootstrap_data["users_by_role"].items():
                self.role_combo.addItem(f"{u['full_name']} [{role_key}]", u["id"])
            self.role_combo.currentIndexChanged.connect(self._on_role_switched)
            header.addWidget(QLabel("Active Operator:"))
            header.addWidget(self.role_combo)

            right_layout.addLayout(header)
            right_layout.addWidget(self.stack, stretch=1)
            root_layout.addWidget(right_area, stretch=1)
            self.setCentralWidget(root)

        def _create_module_page(self, mod_key: str, mod_label: str) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)
            heading = QLabel(mod_label)
            heading.setStyleSheet("font-size: 18px; font-weight: 700; color: #0F172A;")
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
            elif mod_key == "maintenance_queue":
                top_bar = QHBoxLayout()
                self.site_selector = QComboBox()
                for w in self.bootstrap_data["websites"]:
                    self.site_selector.addItem(f"{w['name']} ({w['domain']}) [{w['environment'].upper()}]", w["id"])
                start_btn = QPushButton("Start 23-Step SOP Session")
                start_btn.setProperty("class", "PrimaryButton")
                start_btn.clicked.connect(self.launch_sop_session)
                top_bar.addWidget(QLabel("Select Website:"))
                top_bar.addWidget(self.site_selector, stretch=1)
                top_bar.addWidget(start_btn)
                layout.addLayout(top_bar)

                self.gate_banner = QLabel("Live Pre-Update Backup Gate: Select or start a session to inspect.")
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
                self.step_title_lbl.setStyleSheet("font-size: 15px; font-weight: 700;")
                self.step_process_lbl = QLabel("")
                self.step_process_lbl.setWordWrap(True)
                self.step_rule_box = QPlainTextEdit()
                self.step_rule_box.setReadOnly(True)
                self.step_rule_box.setPlaceholderText("Approved SOP Rule Reference snippet appears here when applicable...")
                self.step_obs_input = QPlainTextEdit()
                self.step_obs_input.setPlaceholderText("Record maintainer observation, metrics, or N/A reason...")

                btn_row = QHBoxLayout()
                for st_code, btn_txt in [
                    ("passed", "Mark Passed"),
                    ("failed", "Mark Failed"),
                    ("blocked", "Mark Blocked"),
                    ("not_verified", "Mark Not Verified"),
                    ("not_applicable", "Mark N/A"),
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
                splitter.setSizes([460, 640])
                layout.addWidget(splitter, stretch=1)
            else:
                info = QLabel(f"Live operational view for {mod_label} backed by OpsHub FastAPI service.")
                layout.addWidget(info)
                table = QTableWidget(0, 5)
                table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                layout.addWidget(table, stretch=1)
            return page

        def _on_role_switched(self) -> None:
            uid = self.role_combo.currentData()
            if uid:
                self.client.set_active_user(uid)
                self.refresh_overview()

        def switch_module(self, mod_key: str) -> None:
            for k, btn in self.nav_buttons.items():
                btn.setProperty("active", "true" if k == mod_key else "false")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
            if mod_key in self.module_pages:
                self.stack.setCurrentWidget(self.module_pages[mod_key])

        def refresh_overview(self) -> None:
            summary = self.client.get_dashboard_summary()
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
                    f"border: 1px solid {badge['border']}; border-radius: 8px; padding: 12px; font-weight: 700; text-align: left;"
                )
                btn.clicked.connect(lambda checked=False, mk=m_key: self.load_drilldown(mk))
                self.kpi_grid.addWidget(btn, idx // 4, idx % 4)

        def load_drilldown(self, metric_key: str) -> None:
            rows = self.client.get_dashboard_drilldown(metric_key)
            self.drilldown_table.setRowCount(len(rows))
            for r_idx, row in enumerate(rows):
                name = str(row.get("name") or row.get("title") or row.get("summary") or row.get("id"))
                cat = str(row.get("environment") or row.get("category") or row.get("action_type") or "—")
                st_raw = str(row.get("workflow_status") or row.get("status") or "unknown")
                badge = format_status_badge(st_raw)
                owner = str(row.get("maintainer_name") or row.get("owner_name") or row.get("next_due_at") or "—")
                self.drilldown_table.setItem(r_idx, 0, QTableWidgetItem(name))
                self.drilldown_table.setItem(r_idx, 1, QTableWidgetItem(cat.upper()))
                self.drilldown_table.setItem(r_idx, 2, QTableWidgetItem(badge["label"]))
                self.drilldown_table.setItem(r_idx, 3, QTableWidgetItem(owner))

        def launch_sop_session(self) -> None:
            website_id = self.site_selector.currentData()
            maintainer_id = self.bootstrap_data["users_by_role"]["maintenance_engineer"]["id"]
            session = self.client.start_session(website_id, maintainer_id)
            self.current_session_id = session["id"]
            self._render_session_steps(session)

        def _render_session_steps(self, session: dict[str, Any]) -> None:
            self._current_session_data = session
            gate = session["backup_gate"]
            self.gate_banner.setText(gate["message"])
            self.sop_step_list.clear()
            for item in session["items"]:
                badge = format_status_badge(item["status"])
                list_item = QListWidgetItem(
                    f"Step {item['step_number']:02d}: {item['title']}   [{badge['label']}]"
                )
                self.sop_step_list.addItem(list_item)
            if session["items"]:
                self.sop_step_list.setCurrentRow(0)

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