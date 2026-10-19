import json
import sqlite3
import unittest

from backend.app.core.database import SCHEMA_SQL
from backend.app.models.enums import ChecklistItemStatus, SessionStatus, WorkflowStatus
from backend.app.services.approval_service import ApprovalService, BackupService
from backend.app.services.issue_service import IssueService
from backend.app.services.seed_demo import BootstrapSeedService
from backend.app.services.sop_gate_service import SOPGateService, SOPGateViolationError


class TestSOPGates(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.seed = BootstrapSeedService.ensure_baseline_seed(self.conn)
        self.maintainer = self.seed["users_by_role"]["maintenance_engineer"]
        self.developer = self.seed["users_by_role"]["developer"]
        self.manager = self.seed["users_by_role"]["manager"]
        self.qa = self.seed["users_by_role"]["reviewer_qa"]

    def tearDown(self):
        self.conn.close()

    def test_01_step_instantiation_and_conditional_rules(self):
        """Verify 23 steps instantiation, Staging Step 7 rule, and Divi Step 19 conditional rule."""
        sites = {s["name"]: s for s in self.seed["websites"]}
        staging_site = sites["Acme Commerce Staging"]
        live_gutenberg_site = sites["Apex Corporate Portal"]

        # 1. Staging + Divi site
        session_staging = SOPGateService.start_session(
            self.conn,
            website_id=staging_site["id"],
            maintainer_id=self.maintainer["id"],
        )
        self.assertEqual(len(session_staging["items"]), 23)
        items_by_num_staging = {i["step_number"]: i for i in session_staging["items"]}

        # Step 7 on staging must be pending & applicable
        self.assertEqual(items_by_num_staging[7]["status"], ChecklistItemStatus.PENDING.value)
        self.assertEqual(items_by_num_staging[7]["is_applicable"], 1)

        # Step 19 on Divi must be pending & applicable
        self.assertEqual(items_by_num_staging[19]["status"], ChecklistItemStatus.PENDING.value)
        self.assertEqual(items_by_num_staging[19]["is_applicable"], 1)

        # 2. Live + Gutenberg site
        session_live = SOPGateService.start_session(
            self.conn,
            website_id=live_gutenberg_site["id"],
            maintainer_id=self.maintainer["id"],
        )
        self.assertEqual(len(session_live["items"]), 23)
        items_by_num_live = {i["step_number"]: i for i in session_live["items"]}

        # Step 7 on live must be not_applicable & is_applicable=0
        self.assertEqual(items_by_num_live[7]["status"], ChecklistItemStatus.NOT_APPLICABLE.value)
        self.assertEqual(items_by_num_live[7]["is_applicable"], 0)
        self.assertIn("staging environments only", items_by_num_live[7]["na_reason"])

        # Step 19 on non-Divi must be not_applicable & is_applicable=0
        self.assertEqual(items_by_num_live[19]["status"], ChecklistItemStatus.NOT_APPLICABLE.value)
        self.assertEqual(items_by_num_live[19]["is_applicable"], 0)
        self.assertIn("Divi Builder", items_by_num_live[19]["na_reason"])

    def test_02_template_immutability_and_live_backup_gate(self):
        """Verify immutable template snapshots (INV-04) and Live Site Pre-Update Backup Gates (INV-05)."""
        sites = {s["name"]: s for s in self.seed["websites"]}
        live_site = sites["Acme Commerce Live"]

        session = SOPGateService.start_session(
            self.conn,
            website_id=live_site["id"],
            maintainer_id=self.maintainer["id"],
        )
        session_id = session["id"]

        # Verify INV-04: Snapshot saved
        row = self.conn.execute("SELECT template_snapshot_json FROM maintenance_sessions WHERE id = ?", (session_id,)).fetchone()
        snapshot = json.loads(row["template_snapshot_json"])
        self.assertEqual(snapshot["version"], 1)
        self.assertEqual(len(snapshot["tasks"]), 23)

        # Publish template v2
        SOPGateService.publish_new_template_version(
            self.conn,
            actor_user_id=self.seed["users_by_role"]["system_admin"]["id"],
            name="WordPress SOP v2",
        )
        # Session snapshot is immutable
        row_after = self.conn.execute("SELECT template_version, template_snapshot_json FROM maintenance_sessions WHERE id = ?", (session_id,)).fetchone()
        self.assertEqual(row_after["template_version"], 1)

        # Verify INV-05: Live backup gate blocks Step 10, 11, 12 on live site without verified backup
        with self.assertRaises(SOPGateViolationError) as ctx:
            SOPGateService.update_checklist_item(
                self.conn,
                session_id=session_id,
                step_number=10,
                actor_user_id=self.maintainer["id"],
                status=ChecklistItemStatus.IN_PROGRESS.value,
            )
        self.assertIn("LIVE SITE PRE-UPDATE GATE", str(ctx.exception))

        # Record and verify backup (Step 9)
        bkp = BackupService.record_backup(
            self.conn,
            website_id=live_site["id"],
            session_id=session_id,
            storage_location="s3://opshub-backups/acme-live-snap.tar.gz",
            created_by=self.maintainer["id"],
            is_verified=False,
        )
        BackupService.verify_backup(
            self.conn,
            backup_id=bkp["id"],
            verifier_user_id=self.maintainer["id"],
        )

        # Now Step 10 can be started
        updated_step10 = SOPGateService.update_checklist_item(
            self.conn,
            session_id=session_id,
            step_number=10,
            actor_user_id=self.maintainer["id"],
            status=ChecklistItemStatus.IN_PROGRESS.value,
        )
        self.assertEqual(updated_step10["status"], ChecklistItemStatus.IN_PROGRESS.value)

    def test_03_developer_approval_gate_and_closure_gates(self):
        """Verify developer approval for core upgrade, closure gate steps 22 & 23, and Step 13 failure handling."""
        sites = {s["name"]: s for s in self.seed["websites"]}
        live_site = sites["Acme Commerce Live"]

        session = SOPGateService.start_session(
            self.conn,
            website_id=live_site["id"],
            maintainer_id=self.maintainer["id"],
        )
        session_id = session["id"]

        # Satisfy backup gate
        bkp = BackupService.record_backup(
            self.conn,
            website_id=live_site["id"],
            session_id=session_id,
            storage_location="s3://opshub-backups/acme-live-core.tar.gz",
            created_by=self.maintainer["id"],
            is_verified=True,
        )
        SOPGateService.update_checklist_item(
            self.conn,
            session_id=session_id,
            step_number=9,
            actor_user_id=self.maintainer["id"],
            status=ChecklistItemStatus.PASSED.value,
        )

        # Step 10 core upgrade requires linked developer approval if upgraded
        with self.assertRaises(SOPGateViolationError):
            SOPGateService.update_checklist_item(
                self.conn,
                session_id=session_id,
                step_number=10,
                actor_user_id=self.maintainer["id"],
                status=ChecklistItemStatus.PASSED.value,
                action_taken="Upgraded core from 6.6.1 to 6.6.2",
            )

        # Request and approve developer approval
        app = ApprovalService.request_approval(
            self.conn,
            project_id=live_site["project_id"],
            website_id=live_site["id"],
            session_id=session_id,
            action_type="wp_core_upgrade",
            summary="Upgrade WP Core to 6.6.2",
            requester_id=self.maintainer["id"],
        )
        ApprovalService.decide_approval(
            self.conn,
            approval_id=app["id"],
            approver_user_id=self.developer["id"],
            decision="approved",
            rationale="Tested in staging; safe to apply.",
        )
        SOPGateService.update_checklist_item(
            self.conn,
            session_id=session_id,
            step_number=10,
            actor_user_id=self.maintainer["id"],
            status=ChecklistItemStatus.PASSED.value,
            action_taken="Upgraded core to 6.6.2",
            linked_approval_id=app["id"],
        )

        # Mark all other steps (except 13, 22, 23) passed or not_applicable
        for s_num in range(1, 24):
            if s_num in (9, 10):
                continue
            item = self.conn.execute(
                "SELECT * FROM session_checklist_items WHERE session_id = ? AND step_number = ?",
                (session_id, s_num),
            ).fetchone()
            if item["status"] != ChecklistItemStatus.NOT_APPLICABLE.value:
                SOPGateService.update_checklist_item(
                    self.conn,
                    session_id=session_id,
                    step_number=s_num,
                    actor_user_id=self.maintainer["id"],
                    status=ChecklistItemStatus.PASSED.value,
                )

        # Closing without Step 22 & 23 passed is blocked
        SOPGateService.update_checklist_item(
            self.conn,
            session_id=session_id,
            step_number=22,
            actor_user_id=self.maintainer["id"],
            status=ChecklistItemStatus.PENDING.value,
        )
        with self.assertRaises(SOPGateViolationError):
            SOPGateService.close_session(
                self.conn,
                session_id=session_id,
                actor_user_id=self.maintainer["id"],
                target_status=SessionStatus.COMPLETED.value,
            )

        # Mark Step 13 as failed -> blocks closure unless linked resolved issue or exception exists
        SOPGateService.update_checklist_item(
            self.conn,
            session_id=session_id,
            step_number=13,
            actor_user_id=self.maintainer["id"],
            status=ChecklistItemStatus.FAILED.value,
            observation="WooCommerce cart broken post-update",
        )
        SOPGateService.update_checklist_item(
            self.conn,
            session_id=session_id,
            step_number=22,
            actor_user_id=self.maintainer["id"],
            status=ChecklistItemStatus.PASSED.value,
        )
        SOPGateService.update_checklist_item(
            self.conn,
            session_id=session_id,
            step_number=23,
            actor_user_id=self.maintainer["id"],
            status=ChecklistItemStatus.PASSED.value,
        )
        with self.assertRaises(SOPGateViolationError):
            SOPGateService.close_session(
                self.conn,
                session_id=session_id,
                actor_user_id=self.maintainer["id"],
                target_status=SessionStatus.COMPLETED.value,
            )

        # Resolve issue and close session
        issue = IssueService.create_issue(
            self.conn,
            project_id=live_site["project_id"],
            category="functional_defect",
            severity="high",
            priority="high",
            title="Cart broken post-update",
            description="Cart page fatal error",
            actor_user_id=self.maintainer["id"],
            session_id=session_id,
        )
        IssueService.record_remediation(
            self.conn,
            issue_id=issue["id"],
            actor_user_id=self.developer["id"],
            remediation_notes="Updated cart template compatibility",
        )
        IssueService.verify_issue(
            self.conn,
            issue_id=issue["id"],
            verifier_user_id=self.qa["id"],
            passed=True,
            verification_notes="Cart checkout verified working.",
        )
        SOPGateService.update_checklist_item(
            self.conn,
            session_id=session_id,
            step_number=13,
            actor_user_id=self.maintainer["id"],
            status=ChecklistItemStatus.FAILED.value,
            linked_issue_id=issue["id"],
        )

        closed = SOPGateService.close_session(
            self.conn,
            session_id=session_id,
            actor_user_id=self.maintainer["id"],
            target_status=SessionStatus.COMPLETED.value,
        )
        self.assertEqual(closed["status"], SessionStatus.COMPLETED_WITH_FINDINGS.value)
        site_after = self.conn.execute("SELECT workflow_status FROM websites WHERE id = ?", (live_site["id"],)).fetchone()
        self.assertEqual(site_after["workflow_status"], WorkflowStatus.UP_TO_DATE.value)


if __name__ == "__main__":
    unittest.main()
