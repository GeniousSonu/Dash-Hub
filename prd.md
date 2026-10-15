# OpsHub Product Requirements Document (PRD)

**Product Name:** OpsHub — Maintenance & Project Operations Command Center  
**Document Version:** 1.0  
**Date:** 15 October 2026  
**Status:** Baseline Approved for Engineering Planning  

## 1. Product Vision and Core Principle Enforce Verifiable Operations

OpsHub replaces scattered Excel trackers, manual reminders, disconnected chat notes, and informal status updates with one auditable system of record for website maintenance and cross-project operations.

**Core Product Principle:** OpsHub strictly distinguishes a task being marked complete from the underlying work being verified. The system preserves an immutable audit history and never claims a check passed if the application lacked the access required to verify it.

### Primary Operational Questions Answered by OpsHub

| Operational Dimension | Question Answered in Real Time |
| :--- | :--- |
| **Workload & Execution** | What work is planned, in progress, blocked, overdue, or completed across all websites and projects? |
| **Accountability** | Which team member owns each task, and who is the designated reviewer or approver? |
| **SOP Compliance** | Was each required WordPress SOP check performed, skipped with an authorized reason, or independently verified? |
| **Risk Visibility** | Which website or project has unresolved security warnings, failed checks, or pending decisions? |
| **Audit Trail** | What changed, who changed it, when did it happen, and what evidence supports the outcome? |
| **Management Summary** | What was completed today or this week, and what requires immediate management escalation? |
| **Schedule Cadence** | When is the next maintenance cycle due, and have the assigned owners been reminded? |

## 2. Product Scope Separates Safe Workflow Automation from Unattended Live Changes

### In-Scope Capabilities for Initial Production Release (v1.0)

1. **Organization, User, and Role Management:** Role-based access control (RBAC) scoped by organization, team, project, and website.
2. **Project Register & Cross-Project Task Tracking:** Milestones, dependencies, work logs, effort tracking, blockers, and completion criteria across both website and non-website projects.
3. **WordPress Website Inventory:** Multi-environment registry (live, staging, development, custom) separating operational health from maintenance workflow status.
4. **Versioned SOP Workflow Engine:** Interactive 23-step WordPress Site Maintenance SOP with environment-aware and builder-aware (Divi) conditional rules.
5. **Backup & Pre-Update Gates:** Enforced verification of backups (or authorized exceptions) before live-site update tasks unlock.
6. **Issue & Finding Lifecycle:** End-to-end tracking from checklist discovery or scan to triage, assignment, remediation, independent verification, and closure.
7. **Approval Workflows:** Formal request, decision, execution, and verification tracking for core updates, plugin/theme deletions, and sensitive configuration changes.
8. **Centralized Scheduler, Reminders, and Email Reports:** Background worker service generating reminders, escalations, and HTML/PDF/CSV/XLSX reports with delivery tracking.
9. **Safe Read-Only Automation:** HTTP reachability, TLS/SSL expiry, HTTP security headers, response-time checks, and broken-link/missing-image discovery.

### Out-of-Scope Boundaries for Release 1.0

- Unattended modifications to live-site files, `.htaccess`, `wp-config.php`, file permissions, plugins, themes, or WordPress core.
- Automatic deletion of plugins or themes solely because they match the cleanup review list.
- Automatic remediation of scanner warnings without human approval.
- Plain-text storage of raw hosting passwords, SSH keys, or API secrets inside SQLite/PostgreSQL records, logs, or exported reports.

## 3. Role-Based Access Control Enforces Least Privilege Across Seven Roles

| Role | Primary Responsibilities | Restricted Actions |
| :--- | :--- | :--- |
| **System Administrator** | Manage global settings, users, roles, integration credentials, SMTP config, and workflow templates. | Must follow audit logging on all configuration changes. |
| **Manager / Operations Lead** | View cross-project workload, assign/reassign tasks, set priorities, review blockers, approve policy exceptions. | Does not execute raw server modifications directly in UI. |
| **Maintenance Engineer** | Execute assigned maintenance sessions, record observations, attach evidence, raise issues, request approvals. | Cannot self-approve restricted actions or bypass live backup gates. |
| **Developer** | Resolve assigned technical issues, review findings, approve developer-owned upgrades, request QA verification. | Cannot close verified issues without verification pass. |
| **Reviewer / QA** | Independently verify completed checks and issue fixes; accept or return work for correction. | Cannot alter historical audit logs. |
| **Read-Only Stakeholder** | View permitted projects, websites, dashboards, and reports. | Cannot create, edit, or approve operational records. |
| **Report Recipient** | Receive scheduled or on-demand email summaries. | Zero application login access granted by email subscription alone. |

## 4. WordPress Site Maintenance SOP Functional Specification (23 Tasks)

Every SOP task records: `status` (`Pending`, `In Progress`, `Passed`, `Failed`, `Blocked`, `Not Applicable`, `Not Verified`), `owner_id`, `observation`, `evidence_ids`, `action_taken`, `follow_up_issue_id`, `approval_id`, and `completed_at`.

| # | SOP Task | Environment Scope | Automation Mode | Gating & Verification Rules |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Website overview** | All | Assisted (Link/Image scan) + Manual visual check | Automated link check assists but never replaces human visual review of forms/checkout/layout. |
| **2** | **Slow website / performance** | All | Assisted timing + Manual | Record tool, date, URL, and metrics if slow; spawn separate remediation issue/task rather than stalling session. |
| **3** | **Default/core files** | All | Read-only checksum compare (if authorized) | Flag suspicious differences; require approval before any destructive file action. Mark `Not Verified` if no filesystem access. |
| **4** | **`.htaccess` security rules** | All (Apache) | Read-only header inspection | Check clickjacking, MIME-sniffing, HSTS, PHP disclosure. Validate HTTPS subdomain readiness before HSTS `includeSubDomains`. |
| **5** | **File permissions** | All | Read-only SSH/host check (if authorized) | Compare against configurable host policy (e.g., `444` sensitive PHP, `644` `.htaccess`). Never force chmod automatically. |
| **6** | **Debug logging** | All | Read-only config parse | Inspect `WP_DEBUG`, `WP_DEBUG_LOG`, `WP_DEBUG_DISPLAY`, `SCRIPT_DEBUG` and duplicate constants. No auto-edit of `wp-config.php`. |
| **7** | **Search-engine discouragement** | Staging only | Read-only `robots.txt` & meta check | Confirm `User-agent: * / Disallow: /` and WP indexing setting; warn that `robots.txt` is not access control and recommend auth. |
| **8** | **Directory indexing** | All | Read-only HTTP/config check | Verify directory listing is disabled (`Options -Indexes` where supported). Do not inject unsupported directives. |
| **9** | **Backup** | All (Hard gate on Live) | Manual record + Completeness check | **Mandatory Gate:** Live sites require a verified backup record (or Manager/Dev approved exception) before Tasks 10–12 unlock. |
| **10** | **WordPress core updates** | All | Read-only version check | Requires recorded Developer confirmation/approval before production upgrade. |
| **11** | **Theme updates** | All | Read-only inventory check | Confirm child theme active where expected; update parent theme only under defined approval policy. |
| **12** | **Plugin updates** | All | Read-only inventory check | Record selected, deferred, failed, and successful updates; route risky updates for approval. |
| **13** | **Post-update re-check** | All | Manual + Optional Playwright smoke test | Re-test frontend, admin, forms, checkout. Critical failure spawns High/Critical issue and blocks normal session closure. |
| **14** | **Plugin conflicts / duplicates** | All | Assisted category overlap flag | Flag overlapping cache/performance plugins for review; never auto-deactivate plugins. |
| **15** | **Disable auto-update policy** | All | Read-only setting check | Compare core/theme/plugin auto-update state against organizational policy; record deviations and approvals. |
| **16** | **Unused plugins/themes cleanup** | All | Assisted match against removal list | Flag matches (`WP File Manager`, `Hello Dolly`, `Akismet`, `String Locator`, `WP Rollback`, `WP Importer`, `All-in-One WP Migration`, `Better Search Replace`). Require developer verification & approval before deletion; keep one default theme. |
| **17** | **Administrator users** | All | Read-only role audit (if authorized) | Verify legitimacy of administrator accounts; log suspicious accounts as findings; require approval for user changes. |
| **18** | **Site Health** | All | Manual / WP REST check | Record WordPress `Tools -> Site Health` critical errors and warnings; close findings only after fix or formal risk acceptance. |
| **19** | **Divi Builder (conditional)** | Divi sites only | Conditional UI rule | Displayed only if `website.builder == 'Divi'` or maintainer enables it; review `Theme Options -> Integration`; require dev review before moving code to theme files. |
| **20** | **Security plugins** | All | Manual / Read-only check | Verify configuration of WPS Hide Login, Advanced reCAPTCHA, Limit Login Attempts, Stream, and Password Protected (staging). |
| **21** | **Wordfence scan** | Sites with Wordfence | Manual / Integration check | Verify settings against internal guide, run scan, log actionable warnings as issues, and record post-change re-scan. |
| **22** | **Final frontend check** | All | Manual + Optional smoke test | **Mandatory Completion Gate:** Revisit public frontend and key flows before closing session. |
| **23** | **Review notes** | All | System-enforced review check | **Mandatory Completion Gate:** Review persistent site notes, prior session notes, open issues, and dev instructions; carry forward open actions. |

## 5. Lifecycle State Machines Govern Tasks, Sessions, Issues, and Approvals

### Workflow State Definitions

| Entity | Allowed States | Terminal / Gating Rules |
| :--- | :--- | :--- |
| **General Task** | `Backlog`, `Ready`, `In Progress`, `Blocked`, `In Review`, `Changes Requested`, `Completed`, `Cancelled` | `Cancelled` requires a recorded reason; state transitions append to `ActivityEvent` and never overwrite history. |
| **Maintenance Session** | `Scheduled`, `Due`, `In Progress`, `Blocked`, `Awaiting Review`, `Completed`, `Completed with Findings`, `Incomplete` | Cannot transition to `Completed` or `Completed with Findings` unless Tasks 9 (or exception), 22, and 23 are satisfied and no unaddressed critical post-update failures remain. |
| **Issue / Finding** | `New`, `Triaged`, `Assigned`, `In Progress`, `Fixed / Mitigated`, `Verification`, `Resolved`, `Closed`, `Duplicate`, `Rejected`, `Accepted Risk`, `Reopened` | Failed verification automatically transitions the issue back to `In Progress` or `Reopened`; `Closed` requires verification outcome or formal risk acceptance. |
| **Approval Record** | `Requested`, `Pending`, `Approved`, `Rejected`, `More Information Required`, `Executed`, `Verified` | `Approved` authorizes action but never implies `Executed` or `Verified`. |

## 6. Acceptance Criteria for Release 1.0 Require End-to-End Traceability

1. **Zero-Loss Inventory Import:** Existing Excel/CSV website trackers import with schema validation and duplicate domain detection.
2. **Complete Site Registry:** Every website stores owner, environment type, schedule policy, health status, workflow status, and persistent notes.
3. **Immutable Template Versioning:** Starting a maintenance session snapshots the exact SOP template version so future template edits never alter historical session records.
4. **Full 23-Step SOP Execution:** All 23 SOP tasks operate with conditional rules for Live vs. Staging and Divi Builder sites.
5. **Strict Epistemic Statuses:** The UI and reports distinctly track `Passed`, `Failed`, `Blocked`, `Not Applicable`, and `Not Verified`.
6. **Enforced Pre-Update & Closure Gates:** Live updates block without a verified backup (or approved exception), and session closure blocks until Final Frontend Check (#22) and Review Notes (#23) are completed.
7. **Traceable Issue Lifecycle:** Checklist failures spawn linked issues that track assignment, remediation, independent QA verification, and closure.
8. **Real-Time Management Visibility:** Dashboard widgets dynamically query live database counts for overdue tasks, high-severity issues, pending approvals, and owner workload.
9. **Autonomous Backend Scheduling:** Reminders, escalations, and email reports execute via the backend scheduler independently of whether any desktop client is open.
10. **Auditable Report Integrity:** Reports reflect saved database state with generation timestamps, and post-report edits trigger clearly marked revision deliveries.
11. **Append-Only Activity History:** All status changes, assignments, approvals, and external checks record actor, timestamp, and before/after metadata.
12. **Protected Secrets & Permissions:** Role checks guard every endpoint, confirmation dialogs protect sensitive actions, and secrets live exclusively in OS keyring or server secret stores.
13. **Honest Automation Reporting:** Automated checks without required credentials or network reachability report `Not Verified / Access Required`, never `Passed`.
14. **Verified Disaster Recovery:** Database and evidence attachment backup and restoration scripts are tested and documented.
15. **Automated Test Coverage:** `pytest` suite validates SOP gating, recurrence calculation, RBAC enforcement, and issue verification state machines.
