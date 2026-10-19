import sqlite3
import unittest

from backend.app.core.database import SCHEMA_SQL
from backend.app.models.enums import IssueStatus
from backend.app.services.approval_service import ApprovalPolicyError, ApprovalService
from backend.app.services.audit_service import AuditService
from backend.app.services.issue_service import IssueService, IssueVerificationError
from backend.app.services.seed_demo import BootstrapSeedService


class TestIssueAndApprovals(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.seed = BootstrapSeedService.ensure_baseline_seed(self.conn)
        self.maintainer = self.seed["users_by_role"]["maintenance_engineer"]
        self.developer = self.seed["users_by_role"]["developer"]
        self.manager = self.seed["users_by_role"]["manager"]
        self.qa = self.seed["users_by_role"]["reviewer_qa"]
        self.proj_id = self.seed["projects"][0]["id"]

    def tearDown(self):
        self.conn.close()

    def test_01_issue_verification_lifecycle_and_reopen(self):
        """Enforce INV-01: Completion != Verification, direct closure blocked, and failed QA reopens."""
        issue = IssueService.create_issue(
            self.conn,
            project_id=self.proj_id,
            category="security_vulnerability",
            severity="high",
            priority="high",
            title="Outdated WP Plugin with CVE",
            description="Plugin version has known RCE",
            actor_user_id=self.maintainer["id"],
        )

        IssueService.record_remediation(
            self.conn,
            issue_id=issue["id"],
            actor_user_id=self.developer["id"],
            remediation_notes="Patched plugin to latest non-vulnerable release.",
            request_verification=True,
        )

        # Direct closure without passed QA verification MUST be blocked
        with self.assertRaises(IssueVerificationError) as ctx:
            IssueService.close_issue_directly(
                self.conn,
                issue_id=issue["id"],
                actor_user_id=self.developer["id"],
                target_status=IssueStatus.CLOSED.value,
                closure_reason="Dev believes it is fixed",
            )
        self.assertIn("INV-01: Direct closure blocked without passed QA verification", str(ctx.exception))

        # Failed QA verification MUST automatically reopen issue (INV-01)
        reopened = IssueService.verify_issue(
            self.conn,
            issue_id=issue["id"],
            verifier_user_id=self.qa["id"],
            passed=False,
            verification_notes="Tested on staging; regression observed in user checkout.",
        )
        self.assertEqual(reopened["status"], IssueStatus.REOPENED.value)
        self.assertEqual(reopened["verification_outcome"], "failed")

        # Second remediation + Passed verification -> cleanly closed
        IssueService.record_remediation(
            self.conn,
            issue_id=issue["id"],
            actor_user_id=self.developer["id"],
            remediation_notes="Fixed checkout regression with updated hook.",
        )
        closed = IssueService.verify_issue(
            self.conn,
            issue_id=issue["id"],
            verifier_user_id=self.qa["id"],
            passed=True,
            verification_notes="Retested. Checkout works cleanly.",
            close_on_pass=True,
        )
        self.assertEqual(closed["status"], IssueStatus.CLOSED.value)
        self.assertEqual(closed["verification_outcome"], "passed")

    def test_02_rbac_separation_of_duties_and_append_only_audit_trigger(self):
        """Verify RBAC separation of duties (no self-approval) and SQLite append-only trigger (INV-06)."""
        app = ApprovalService.request_approval(
            self.conn,
            project_id=self.proj_id,
            action_type="backup_exception",
            summary="Bypass backup gate for urgent zero-day patch",
            requester_id=self.maintainer["id"],
        )

        # 1. Self-approval blocked
        with self.assertRaises(ApprovalPolicyError) as ctx:
            ApprovalService.decide_approval(
                self.conn,
                approval_id=app["id"],
                approver_user_id=self.maintainer["id"],
                decision="approved",
                rationale="Self-approving my own request",
            )
        self.assertIn("Separation of Duties Violation", str(ctx.exception))

        # 2. Unauthorized role blocked for manager exception
        with self.assertRaises(ApprovalPolicyError):
            ApprovalService.decide_approval(
                self.conn,
                approval_id=app["id"],
                approver_user_id=self.developer["id"],
                decision="approved",
                rationale="Developer trying to approve manager exception",
            )

        # 3. Manager successfully approves
        approved = ApprovalService.decide_approval(
            self.conn,
            approval_id=app["id"],
            approver_user_id=self.manager["id"],
            decision="approved",
            rationale="Manager emergency authorization granted.",
        )
        self.assertEqual(approved["status"], "approved")

        # 4. INV-06: Database trigger blocks UPDATE and DELETE on activity_events
        event_id = AuditService.log_event(
            self.conn,
            actor_user_id=self.maintainer["id"],
            entity_type="test",
            entity_id="123",
            action="test_action",
            summary="Original event text",
        )

        with self.assertRaises(sqlite3.DatabaseError) as ctx_upd:
            self.conn.execute("UPDATE activity_events SET summary = 'tampered' WHERE id = ?", (event_id,))
        self.assertIn("activity_events is append-only and cannot be updated", str(ctx_upd.exception))

        with self.assertRaises(sqlite3.DatabaseError) as ctx_del:
            self.conn.execute("DELETE FROM activity_events WHERE id = ?", (event_id,))
        self.assertIn("activity_events is append-only and cannot be deleted", str(ctx_del.exception))


if __name__ == "__main__":
    unittest.main()
