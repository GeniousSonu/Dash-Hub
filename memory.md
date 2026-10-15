# OpsHub Project Memory, Domain Rules & Architecture Decisions

**Last Updated:** 15 October 2026  
**Purpose:** Persistent engineering memory, non-negotiable domain invariants, SOP reference constants, and Architecture Decision Records (ADRs).

## 1. Non-Negotiable Product Invariants Must Hold Across All Modules

1. **Completion vs. Verification Distinction (`INV-01`):**
   - Marking a task or approval as completed/approved is distinct from independent verification.
   - An `Approval` in `Approved` status only authorizes execution; it must transition through `Executed` and `Verified`.
   - An `Issue` in `Fixed / Mitigated` status cannot move to `Closed` without passing `Verification` (or having an authorized `Accepted Risk` decision).
2. **Epistemic Honesty in Automation (`INV-02`):**
   - Automated checks that lack network reachability, authentication, or filesystem access must record `Not Verified / Access Required` along with explicit `limitations` metadata.
   - No check may ever default to `Passed` when a condition could not be inspected.
3. **Separation of Website Health and Workflow Status (`INV-03`):**
   - `website.health_status` (`online`, `degraded`, `down`, `unknown`) tracks live site availability.
   - `website.workflow_status` (`up_to_date`, `due`, `in_progress`, `blocked`, `overdue`) tracks SOP schedule compliance.
4. **Immutable SOP Template Snapshots (`INV-04`):**
   - Editing a `WorkflowTemplate` creates a new version number.
   - Existing `MaintenanceSession` records retain the exact `template_version_snapshot_json` active when the session started so historical compliance reports never mutate retroactively.
5. **Read-Only First Production Boundary (`INV-05`):**
   - Release 1.0 never executes unattended file edits (`.htaccess`, `wp-config.php`, `chmod`), core/theme/plugin updates, or plugin deletions on live sites.
6. **Append-Only Audit Trail (`INV-06`):**
   - State changes, reassignments, cancellations, approvals, and report deliveries write immutable rows to `activity_events`. Cancelling a task or reopening an issue preserves all prior history.

## 2. Canonical WordPress SOP Reference Rules (Seeded in Database)

The system seeds the following versioned reference snippets into `workflow_templates.rules_reference_json` for maintainer guidance:

| Reference Key | SOP Step | Canonical Rule / Guidance Stored in OpsHub |
| :--- | :--- | :--- |
| `htaccess_security_headers` | Step 4 | Inspect for `X-Frame-Options` (clickjacking), `X-Content-Type-Options: nosniff` (MIME-sniffing), `Strict-Transport-Security` (HSTS — enable `includeSubDomains` **only** after verifying all subdomains support HTTPS), and PHP version disclosure (`Header unset X-Powered-By` / `expose_php = Off`). Never blindly append duplicate directives. |
| `file_permissions_policy` | Step 5 | Compare against environment policy inputs (e.g., `444` for sensitive PHP config files, `644` for `.htaccess`, `755` for directories, `644` for standard files). Treat as validation targets, never auto-forced `chmod` commands. |
| `wp_debug_constants` | Step 6 | Inspect `wp-config.php` for `WP_DEBUG`, `WP_DEBUG_LOG`, `WP_DEBUG_DISPLAY`, and `SCRIPT_DEBUG`. Flag duplicate constant definitions or enabled public debug display on live sites. |
| `staging_robots_policy` | Step 7 | Staging `robots.txt` reference: `User-agent: *` / `Disallow: /` plus WordPress "Discourage search engines from indexing this site". Display mandatory reminder: *"`robots.txt` is a crawler directive, not access control; enforce HTTP Basic Auth, IP allowlisting, or Password Protected plugin on private staging sites."* |
| `live_robots_guidance` | Step 7 | Require SEO/operations review before altering live `robots.txt`; blocking CSS/JS assets or admin paths in `robots.txt` is not a security control and can harm rendering/indexing. |
| `directory_indexing_rule` | Step 8 | Verify directory browsing is disabled at the web server level (`Options -Indexes` on compatible Apache environments). |
| `plugin_cleanup_review_list` | Step 16 | Flag presence of: `WP File Manager`, `Hello Dolly`, `Akismet Anti Spam`, `String Locator`, `WP Rollback`, `WordPress Importer`, `All-in-One WP Migration`, `Better Search Replace`. **Rule:** Matching this list is a review trigger, not automatic deletion authorization. Require developer confirmation and keep one default theme alongside the active/child theme. |
| `security_plugins_baseline` | Step 20 | Check site-appropriate configuration of `WPS Hide Login`, `Advanced reCAPTCHA`, `Limit Login Attempts`, `Stream`, and `Password Protected` (staging). |

## 3. Architecture Decision Log (ADR)

### ADR-001: Central FastAPI + PostgreSQL Backend with SQLite Prototype Mode
- **Context:** OpsHub requires multi-user task assignment, developer/manager approvals, and scheduled reminders/emails that run even when an engineer's laptop is closed.
- **Decision:** Build all domain logic inside a FastAPI service backed by SQLAlchemy 2.x and PostgreSQL in production, with a zero-config SQLite mode (`OPSHUB_DB_URL=sqlite:///./opshub.db`) for local development, testing, and single-machine demos.
- **Consequence:** The PySide6 desktop client communicates via clean service/API boundaries, preventing single-user database lock-in and allowing a web dashboard to be added later without rewriting business rules.

### ADR-002: Explicit Gate Evaluation Service Before Step Transitions
- **Context:** Excel checklists fail because maintainers can tick "Core Updated" without verifying a backup or obtaining developer approval.
- **Decision:** Centralize all step state transitions in `SOPGateService`, which deterministically checks `BackupRecord` verification, `Approval` status, and mandatory final steps (#22, #23) before committing state transitions.
- **Consequence:** Both the PySide6 UI and REST API enforce identical completion gates and return structured gate-blocker reasons.

### ADR-003: Secret Isolation via OS Keyring and Environment References
- **Context:** Storing SMTP passwords or WordPress/SSH credentials in database tables risks credential leakage through backups, logs, or exported reports.
- **Decision:** Store only non-secret `credential_ref` identifiers in `integration_configurations`, resolving actual secrets at runtime via `keyring` (desktop/local) or server environment/secret manager.
