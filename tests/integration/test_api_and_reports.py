from pathlib import Path
import unittest
import uuid
from fastapi.testclient import TestClient

from backend.app.core.database import db_manager
from backend.app.main import app
from backend.app.services.seed_demo import BootstrapSeedService


class TestApiAndReports(unittest.TestCase):
    def setUp(self):
        db_manager.init_schema()
        with db_manager.session() as conn:
            self.seed = BootstrapSeedService.ensure_baseline_seed(conn)
        self.client = TestClient(app)
        self.admin = self.seed["users_by_role"]["system_admin"]
        self.maintainer = self.seed["users_by_role"]["maintenance_engineer"]
        self.recipient = self.seed["users_by_role"]["report_recipient"]
        self.proj_id = self.seed["projects"][0]["id"]

    def test_end_to_end_api_import_readonly_and_reports(self):
        """Verify API import dedup, read-only INV-02 enforcement, PDF revision detection, and RBAC 403."""
        # 1. Bulk website import deduplication
        uid = uuid.uuid4().hex[:6]
        dom_alpha = f"alpha-{uid}.example.com"
        dom_beta = f"staging.beta-{uid}.example.org"

        import_payload = {
            "default_project_id": self.proj_id,
            "default_maintainer_id": self.maintainer["id"],
            "dry_run": False,
            "rows": [
                {"name": f"Site Alpha Live {uid}", "domain": dom_alpha, "environment": "live", "builder": "gutenberg"},
                {"name": f"Site Beta Staging {uid}", "domain": dom_beta, "environment": "staging", "builder": "divi"},
                # Duplicate entry
                {"name": f"Site Alpha Duplicate {uid}", "domain": dom_alpha, "environment": "live", "builder": "gutenberg"},
            ],
        }
        resp = self.client.post(
            "/api/v1/websites/import",
            json=import_payload,
            headers={"x-user-id": self.admin["id"]},
        )
        self.assertEqual(resp.status_code, 200)
        res_data = resp.json()
        self.assertEqual(res_data["imported"], 2)
        self.assertEqual(res_data["duplicates_skipped"], 1)

        # 2. Epistemic limitation check (INV-02)
        new_site_id = res_data["created_websites"][0]["id"]
        sess_resp = self.client.post(
            "/api/v1/sessions",
            json={"website_id": new_site_id, "maintainer_id": self.maintainer["id"]},
            headers={"x-user-id": self.maintainer["id"]},
        )
        self.assertEqual(sess_resp.status_code, 200)
        session_id = sess_resp.json()["id"]

        ro_resp = self.client.post(
            f"/api/v1/sessions/{session_id}/run-readonly-checks",
            headers={"x-user-id": self.maintainer["id"]},
        )
        self.assertEqual(ro_resp.status_code, 200)
        ro_items = {item["step_number"]: item for item in ro_resp.json()["items"]}

        # Step 3, 5, 6, 17 must be not_verified with limitations
        for step_num in (3, 5, 6, 17):
            self.assertEqual(
                ro_items[step_num]["status"],
                "not_verified",
                f"Step {step_num} must be not_verified per INV-02",
            )
            self.assertIn("NOT VERIFIED / ACCESS REQUIRED", ro_items[step_num]["observation"])

        # 3. PDF report generation and revision detection
        rep1 = self.client.post(
            f"/api/v1/reports/sessions/{session_id}/pdf",
            headers={"x-user-id": self.admin["id"]},
        )
        self.assertEqual(rep1.status_code, 200)
        rep1_data = rep1.json()
        self.assertFalse(rep1_data["is_revised_report"])
        self.assertTrue(Path(rep1_data["pdf_path"]).exists())
        self.assertNotIn("[UPDATED REVISION REPORT]", rep1_data["subject"])

        # Regenerate report -> must detect revision
        rep2 = self.client.post(
            f"/api/v1/reports/sessions/{session_id}/pdf",
            headers={"x-user-id": self.admin["id"]},
        )
        self.assertEqual(rep2.status_code, 200)
        rep2_data = rep2.json()
        self.assertTrue(rep2_data["is_revised_report"])
        self.assertIn("[UPDATED REVISION REPORT]", rep2_data["subject"])

        # 4. XLSX export
        xlsx_resp = self.client.post(
            "/api/v1/reports/export-xlsx",
            headers={"x-user-id": self.admin["id"]},
        )
        self.assertEqual(xlsx_resp.status_code, 200)
        xlsx_path = Path(xlsx_resp.json()["xlsx_path"])
        self.assertTrue(xlsx_path.exists())

        # 5. Report Recipient RBAC restriction (403 Forbidden)
        forbidden_resp = self.client.get(
            "/api/v1/tasks",
            headers={"x-user-id": self.recipient["id"]},
        )
        self.assertEqual(forbidden_resp.status_code, 403)


if __name__ == "__main__":
    unittest.main()
