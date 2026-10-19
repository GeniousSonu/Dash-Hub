import os
from typing import Any
import httpx
from fastapi.testclient import TestClient

from backend.app.main import app


class OpsHubDesktopClient:
    def __init__(self, base_url: str | None = None, user_id: str | None = None):
        self.base_url = (base_url or os.getenv("OPSHUB_API_URL", "")).rstrip("/")
        self.user_id = user_id
        if self.base_url:
            self.http_client = httpx.Client(base_url=self.base_url, timeout=15.0)
            self.test_client = None
            try:
                # Fast probe to see if standalone server is running
                resp = self.http_client.get("/api/v1/health", timeout=1.5)
                if resp.status_code != 200:
                    self.test_client = TestClient(app)
            except Exception:
                # Fallback directly to in-process FastAPI engine
                self.test_client = TestClient(app)
        else:
            self.http_client = None
            self.test_client = TestClient(app)

    def set_active_user(self, user_id: str | None) -> None:
        self.user_id = user_id

    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        hdrs = headers.copy() if headers else {}
        if self.user_id and "x-user-id" not in hdrs:
            hdrs["x-user-id"] = self.user_id

        resp = None
        if self.http_client and self.test_client is None:
            try:
                resp = self.http_client.request(
                    method, path, params=params, json=json_body, headers=hdrs
                )
            except (httpx.ConnectError, httpx.ConnectTimeout):
                # Fallback to in-process app on connection failure
                self.test_client = TestClient(app)
                resp = self.test_client.request(
                    method, path, params=params, json=json_body, headers=hdrs
                )
        else:
            if self.test_client is None:
                self.test_client = TestClient(app)
            resp = self.test_client.request(
                method, path, params=params, json=json_body, headers=hdrs
            )

        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise RuntimeError(f"HTTP {resp.status_code}: {detail}")

        return resp.json()

    def get_bootstrap(self) -> dict[str, Any]:
        return self.request("GET", "/api/v1/bootstrap")

    def get_dashboard_summary(self) -> dict[str, Any]:
        return self.request("GET", "/api/v1/dashboard/summary")

    def get_drilldown(self, metric_key: str) -> list[dict[str, Any]]:
        return self.request("GET", f"/api/v1/dashboard/drilldown/{metric_key}")

    def list_projects(self) -> list[dict[str, Any]]:
        return self.request("GET", "/api/v1/projects")

    def list_websites(self, environment: str | None = None) -> list[dict[str, Any]]:
        params = {"environment": environment} if environment else None
        return self.request("GET", "/api/v1/websites", params=params)

    def list_tasks(self, owner_id: str | None = None) -> list[dict[str, Any]]:
        params = {"owner_id": owner_id} if owner_id else None
        return self.request("GET", "/api/v1/tasks", params=params)

    def list_issues(self) -> list[dict[str, Any]]:
        return self.request("GET", "/api/v1/issues")

    def list_approvals(self) -> list[dict[str, Any]]:
        return self.request("GET", "/api/v1/approvals")

    def list_backups(self) -> list[dict[str, Any]]:
        return self.request("GET", "/api/v1/backups")

    def list_reports(self) -> list[dict[str, Any]]:
        return self.request("GET", "/api/v1/reports")

    def list_sessions(self) -> list[dict[str, Any]]:
        return self.request("GET", "/api/v1/sessions")

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self.request("GET", f"/api/v1/sessions/{session_id}")

    def start_session(self, website_id: str, maintainer_id: str) -> dict[str, Any]:
        return self.request(
            "POST",
            "/api/v1/sessions",
            json_body={"website_id": website_id, "maintainer_id": maintainer_id},
        )

    def update_step(
        self,
        session_id: str,
        step_number: int,
        status: str,
        observation: str | None = None,
        na_reason: str | None = None,
        blocked_reason: str | None = None,
        linked_issue_id: str | None = None,
        linked_approval_id: str | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "PATCH",
            f"/api/v1/sessions/{session_id}/items/{step_number}",
            json_body={
                "status": status,
                "observation": observation,
                "na_reason": na_reason,
                "blocked_reason": blocked_reason,
                "linked_issue_id": linked_issue_id,
                "linked_approval_id": linked_approval_id,
            },
        )

    def run_readonly_checks(self, session_id: str) -> dict[str, Any]:
        return self.request("POST", f"/api/v1/sessions/{session_id}/run-readonly-checks")

    def close_session(
        self, session_id: str, target_status: str = "completed", closure_summary: str = ""
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            f"/api/v1/sessions/{session_id}/close",
            json_body={"target_status": target_status, "closure_summary": closure_summary},
        )

    def generate_pdf(self, session_id: str) -> dict[str, Any]:
        return self.request("POST", f"/api/v1/reports/sessions/{session_id}/pdf")

    def global_search(self, q: str) -> dict[str, Any]:
        return self.request("GET", "/api/v1/search", params={"q": q})

    def create_task(
        self,
        project_id: str,
        title: str,
        owner_id: str,
        description: str = "",
        priority: str = "normal",
        status: str = "ready",
        due_at: str | None = None,
        estimated_hours: float = 0.0,
        acceptance_criteria: str = "",
        depends_on: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            "/api/v1/tasks",
            json_body={
                "project_id": project_id,
                "title": title,
                "owner_id": owner_id,
                "description": description,
                "priority": priority,
                "status": status,
                "due_at": due_at,
                "estimated_hours": estimated_hours,
                "acceptance_criteria": acceptance_criteria,
                "depends_on": depends_on or [],
            },
        )

    def update_task_status(
        self,
        task_id: str,
        new_status: str,
        cancellation_reason: str = "",
        new_owner_id: str | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "PATCH",
            f"/api/v1/tasks/{task_id}/status",
            json_body={
                "new_status": new_status,
                "cancellation_reason": cancellation_reason,
                "new_owner_id": new_owner_id,
            },
        )

    def add_work_log(
        self,
        task_id: str,
        what_was_done: str,
        what_remains: str = "",
        blockers: str = "",
        next_action: str = "",
        hours_logged: float = 0.0,
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            f"/api/v1/tasks/{task_id}/work-logs",
            json_body={
                "what_was_done": what_was_done,
                "what_remains": what_remains,
                "blockers": blockers,
                "next_action": next_action,
                "hours_logged": hours_logged,
            },
        )

    def get_task_work_logs(self, task_id: str) -> list[dict[str, Any]]:
        return self.request("GET", f"/api/v1/tasks/{task_id}/work-logs")

