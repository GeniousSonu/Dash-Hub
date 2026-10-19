import sqlite3
import unittest

from backend.app.core.database import SCHEMA_SQL
from backend.app.models.enums import TaskStatus
from backend.app.services.seed_demo import BootstrapSeedService
from backend.app.services.task_service import TaskService, TaskValidationError
from desktop.services.api_client import OpsHubDesktopClient
from desktop.ui.main_window import NAVIGATION_MODULES
from desktop.ui.widgets.status_badge import format_status_badge
from workers.scheduler import MaintenanceSchedulerWorker


class TestDesktopClientAndTasks(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.seed = BootstrapSeedService.ensure_baseline_seed(self.conn)
        self.maintainer = self.seed["users_by_role"]["maintenance_engineer"]
        self.proj_id = self.seed["projects"][0]["id"]

    def tearDown(self):
        self.conn.close()

    def test_01_desktop_client_navigation_and_status_badges(self):
        """Verify 13 navigation modules and accessible high-contrast status badge labels."""
        self.assertEqual(len(NAVIGATION_MODULES), 13)
        expected_keys = [
            "overview",
            "projects",
            "my_tasks",
            "all_tasks",
            "websites",
            "maintenance_queue",
            "issues",
            "approvals",
            "backups",
            "reports",
            "notifications",
            "activity_history",
            "admin_settings",
        ]
        self.assertEqual([k for k, _ in NAVIGATION_MODULES], expected_keys)

        # Status badge accessibility check
        badge_nv = format_status_badge("not_verified")
        self.assertEqual(badge_nv["label"], "? NOT VERIFIED / ACCESS REQ")
        self.assertTrue(badge_nv["fg"].startswith("#"))

        badge_p = format_status_badge("passed")
        self.assertEqual(badge_p["label"], "✓ PASSED")

        badge_f = format_status_badge("failed")
        self.assertEqual(badge_f["label"], "✕ FAILED")

        badge_b = format_status_badge("blocked")
        self.assertEqual(badge_b["label"], "⊘ BLOCKED")

        # Desktop client embedded API verification
        client = OpsHubDesktopClient()
        bootstrap = client.get_bootstrap()
        self.assertIn("organization", bootstrap)
        self.assertIn("websites", bootstrap)

    def test_02_task_dependencies_worklogs_and_scheduler_dedup(self):
        """Verify task dependency blocking, work-log hour rollups, and scheduler daily deduplication."""
        # 1. Create Task A
        task_a = TaskService.create_task(
            self.conn,
            project_id=self.proj_id,
            title="Database Backup Pre-requisite",
            owner_id=self.maintainer["id"],
            actor_user_id=self.maintainer["id"],
        )

        # 2. Create Task B depending on Task A
        task_b = TaskService.create_task(
            self.conn,
            project_id=self.proj_id,
            title="WordPress Minor Update",
            owner_id=self.maintainer["id"],
            actor_user_id=self.maintainer["id"],
            depends_on=[task_a["id"]],
        )

        # Completing Task B while Task A is not completed MUST raise TaskValidationError
        with self.assertRaises(TaskValidationError) as ctx:
            TaskService.update_task_status(
                self.conn,
                task_id=task_b["id"],
                new_status=TaskStatus.COMPLETED.value,
                actor_user_id=self.maintainer["id"],
            )
        self.assertIn("Cannot complete task while dependency", str(ctx.exception))

        # Cancelling Task A without cancellation reason MUST raise TaskValidationError
        with self.assertRaises(TaskValidationError):
            TaskService.update_task_status(
                self.conn,
                task_id=task_a["id"],
                new_status=TaskStatus.CANCELLED.value,
                actor_user_id=self.maintainer["id"],
                cancellation_reason="",
            )

        # Complete Task A first
        TaskService.update_task_status(
            self.conn,
            task_id=task_a["id"],
            new_status=TaskStatus.COMPLETED.value,
            actor_user_id=self.maintainer["id"],
        )

        # Now Task B can be completed
        completed_b = TaskService.update_task_status(
            self.conn,
            task_id=task_b["id"],
            new_status=TaskStatus.COMPLETED.value,
            actor_user_id=self.maintainer["id"],
        )
        self.assertEqual(completed_b["status"], TaskStatus.COMPLETED.value)

        # Add work logs and verify hours rollup
        TaskService.add_work_log(
            self.conn,
            task_id=task_b["id"],
            author_id=self.maintainer["id"],
            what_was_done="Ran update script",
            hours_logged=1.5,
        )
        log2 = TaskService.add_work_log(
            self.conn,
            task_id=task_b["id"],
            author_id=self.maintainer["id"],
            what_was_done="Verified frontend",
            hours_logged=2.0,
        )
        self.assertEqual(log2["total_task_hours"], 3.5)

        # Scheduler daily deduplication check
        res1 = MaintenanceSchedulerWorker.run_cycle(self.conn)
        self.assertGreaterEqual(res1["overdue_sites_checked"], 1)

        # Second immediate run on the same day must NOT duplicate reminders
        res2 = MaintenanceSchedulerWorker.run_cycle(self.conn)
        self.assertEqual(res2["reminders_created"], 0)
        self.assertEqual(res2["escalations_created"], 0)

    def test_03_desktop_client_task_worklog_api_and_fallback(self):
        """Verify Task work log retrieval, desktop client API helpers, and graceful connection fallback."""
        # 1. Verify TaskService.list_work_logs directly
        task = TaskService.create_task(
            self.conn,
            project_id=self.proj_id,
            title="Database Optimization",
            owner_id=self.maintainer["id"],
            actor_user_id=self.maintainer["id"],
            estimated_hours=4.0,
        )
        TaskService.add_work_log(
            self.conn,
            task_id=task["id"],
            author_id=self.maintainer["id"],
            what_was_done="Analyzed query execution plans and added composite index",
            hours_logged=1.5,
        )
        logs = TaskService.list_work_logs(self.conn, task["id"])
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["author_name"], self.maintainer["full_name"])
        self.assertEqual(logs[0]["hours_logged"], 1.5)

        # 2. Verify OpsHubDesktopClient connection fallback
        # Even if pointing to an unreachable port, client should fallback without throwing ConnectError
        resilient_client = OpsHubDesktopClient(base_url="http://127.0.0.1:59999")
        health = resilient_client.request("GET", "/api/v1/health")
        self.assertEqual(health["status"], "ok")
        self.assertIn("PulseOps", health["app"])

        # 3. Verify task & work-log client methods
        bs = resilient_client.get_bootstrap()
        app_proj_id = bs["projects"][0]["id"]
        app_user_id = bs["users"][0]["id"]
        resilient_client.set_active_user(app_user_id)

        created = resilient_client.create_task(
            project_id=app_proj_id,
            title="PulseOps UI Verification",
            owner_id=app_user_id,
            priority="high",
            estimated_hours=3.0,
            description="Verify executive obsidian theme and work logs",
        )
        self.assertIn("id", created)
        self.assertEqual(created["title"], "PulseOps UI Verification")

        # Log work via client
        logged = resilient_client.add_work_log(
            task_id=created["id"],
            what_was_done="Validated QSS stylesheet and status badges",
            hours_logged=2.0,
        )
        self.assertEqual(logged["hours_logged"], 2.0)
        self.assertEqual(logged["total_task_hours"], 2.0)

        # Retrieve logs via client
        fetched_logs = resilient_client.get_task_work_logs(created["id"])
        self.assertEqual(len(fetched_logs), 1)
        self.assertEqual(fetched_logs[0]["what_was_done"], "Validated QSS stylesheet and status badges")


if __name__ == "__main__":
    unittest.main()


