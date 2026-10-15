# OpsHub — Post-v1.0 Feature Roadmap (`FEATURE_ROADMAP.md`)

**Product:** OpsHub — Maintenance & Project Operations Command Center  
**Current Baseline:** v1.0 Production Release (23-Step WordPress SOP Engine, 16-Table Audit Schema, 7-Role RBAC, Safe Read-Only Checks, PDF/Excel Reporting, Argon Design System PySide6 Desktop Client + FastAPI Backend)  

## 1. Prioritized Feature Backlog with Effort Estimates

| Priority | Feature ID & Name | Operational Value & Scope | Effort Estimate | Architectural Dependencies |
| :--- | :--- | :--- | :--- | :--- |
| **P0 (Next)** | **`FEAT-101` Authorized WordPress REST & Application-Password Connector** | Fetches live plugin/theme/core inventories, active child-theme flags, auto-update settings, and `Tools -> Site Health` status via read-only WP Application Passwords without requiring manual entry on Steps 10, 11, 12, 15, and 18. | **M (5–7 days)** | `integration_configurations`, OS `keyring` / Vault secret resolver. |
| **P0 (Next)** | **`FEAT-102` Vulnerability Feed Correlation (WPScan / CVE / Patchstack)** | Cross-references verified plugin, theme, and core versions from Step 12 against known CVE feeds and automatically spawns `Critical` or `High` severity `Issue` records with remediation version targets. | **M (5 days)** | `FEAT-101` plugin inventory, `issues` table, `APScheduler` daily feed sync. |
| **P1** | **`FEAT-103` Headless Playwright Frontend Smoke Test Runner** | Automates visual regression snapshots, contact form dry-runs, and WooCommerce cart/checkout smoke verification for Step 1 (`Website overview`), Step 13 (`Post-update re-check`), and Step 22 (`Final frontend check`). | **L (8–10 days)** | `workers/checks/`, `Playwright` headless Chromium worker container, `evidences` screenshot storage. |
| **P1** | **`FEAT-104` Authorized Read-Only SSH Diagnostics (`Paramiko`)** | Inspects actual server file permissions (`444` / `644` / `755` on Step 5), `wp-config.php` debug constants (Step 6), and WordPress core checksums (`wp core verify-checksums` on Step 3) over read-only SSH keys. | **M (6 days)** | `Paramiko`, strict read-only command allowlist, host key pinning. |
| **P1** | **`FEAT-105` Cloud Backup Storage Verifier (S3 / Google Drive / SFTP)** | Automatically verifies backup archive existence, file size, SHA-256 checksum, and timestamp freshness in S3/Drive buckets to satisfy the Step 9 Live Pre-Update Gate without manual file inspection. | **M (5 days)** | `backup_records`, read-only storage bucket credentials in secret store. |
| **P1** | **`FEAT-106` Real-Time WebSocket / SSE Desktop Event Stream** | Pushes live toast notifications and table refreshes to all connected PySide6 desktop clients when a Developer approves a Step 10 core upgrade or QA verifies an issue. | **S (3–4 days)** | FastAPI WebSocket endpoint `/api/v1/ws/events`, PySide6 `QWebSocket` listener. |
| **P2** | **`FEAT-107` Slack & Microsoft Teams Escalation Webhooks** | Dispatches interactive channel alerts for overdue maintenance sessions, pending developer approvals, and unresolved Critical/High issues alongside SMTP email reports. | **S (3 days)** | `workers/scheduler.py`, `reminders_and_reports` deduplication log. |
| **P2** | **`FEAT-108` Wordfence CLI / Central Scan Integration** | Pulls structured scan warnings and malware signature results directly into Step 21 (`Wordfence scan`) and tracks post-remediation re-scan diffs. | **M (6 days)** | Wordfence Central API / WP-CLI read-only bridge. |
| **P2** | **`FEAT-109` SLA Policy Engine & MTTR Compliance Analytics** | Tracks Mean Time to Detect (MTTD), Mean Time to Remediate (MTTR), and per-client SLA breach countdowns with `PyQtGraph` trend charts on the Overview dashboard. | **M (5 days)** | `issues`, `maintenance_sessions`, `PyQtGraph` analytics module. |
| **P3** | **`FEAT-110` Offline-Capable Desktop Queue & Sync Conflict Resolver** | Allows Maintenance Engineers to record checklist observations offline in a local encrypted SQLite cache and synchronize with conflict detection upon reconnecting to the FastAPI server. | **XL (12–15 days)** | Local sync journal table, optimistic concurrency version counters. |
| **P3** | **`FEAT-111` Multi-Template Workflow Designer (Non-WordPress SOPs)** | Drag-and-drop template builder in the Administration module to author versioned SOPs for SSL renewals, Linux server patching, database restore drills, and CI/CD release checklists. | **L (9 days)** | `workflow_templates` version engine. |

## 2. Effort Scale Legend

* **S (Small):** 2–4 engineering days; isolated to a single worker or API endpoint with no schema changes.
* **M (Medium):** 5–7 engineering days; touches backend service layer, external integration adapter, and PySide6 view.
* **L (Large):** 8–11 engineering days; requires new background worker infrastructure and multi-screen UI workflows.
* **XL (Extra Large):** 12+ engineering days; requires distributed state synchronization and conflict resolution testing.
