# OpsHub — Maintenance & Project Operations Command Center

**Project Blueprint and Product Requirements Document**  
**Version:** 1.0  
**Date:** 15 October 2026  
**Status:** Proposed plan for review

---

## 1. Executive Summary

OpsHub is a centralized maintenance and project-operations application designed to replace scattered Excel trackers, manual reminders, disconnected notes, and informal status updates with one reliable system of record.

The first major module will digitize the team's WordPress Site Maintenance SOP. It will guide an assigned maintainer through the required checks, record evidence and observations, track approvals, raise issues, enforce required completion gates, schedule recurring maintenance, and generate reports automatically. The same platform will also provide general project and task tracking so teams can monitor work across multiple projects—not only WordPress websites.

The product should make it possible to answer, at any time:

- What work is planned, in progress, blocked, overdue, or completed?
- Which person owns each task, and who is responsible for approval?
- Was each required SOP task performed, skipped with a valid reason, or verified?
- Which website or project has unresolved risks, security warnings, failed checks, or pending decisions?
- What changed, who changed it, when did it happen, and what evidence supports the result?
- What has been completed today or this week, and what needs management attention?
- When is the next maintenance cycle due, and have the relevant people been reminded?

**Product principle:** OpsHub must distinguish a task being marked complete from the underlying work being verified. It must preserve the audit history and must never claim a check passed if the application did not have access to verify it.

## 2. Vision and Objectives

### 2.1 Vision

Create one dependable command center for planning, assigning, carrying out, reviewing, and reporting maintenance and project work—with WordPress maintenance as the first detailed workflow and an extensible foundation for other operational work.

### 2.2 Primary objectives

1. Replace manual Excel-based maintenance tracking with searchable, structured records.
2. Convert the existing Site Maintenance SOP into an interactive, conditional checklist.
3. Assign work to maintainers, developers, reviewers, and approvers with clear ownership.
4. Track project tasks, deadlines, dependencies, work logs, blockers, and completion evidence.
5. Automate recurring schedules, reminders, overdue alerts, and email reports.
6. Capture issues and findings from discovery through assignment, remediation, verification, and closure.
7. Preserve the complete maintenance and project history for accountability and future reference.
8. Automate safe, read-only checks where practical while keeping risky production changes under human control.
9. Provide management dashboards and consistent reports based on live system records.
10. Support future team collaboration through a central backend, role-based access, and shared data.

### 2.3 Success indicators

The team should be able to measure:

- Percentage of websites with a named owner, schedule, and up-to-date record.
- Percentage of maintenance sessions completed with all required tasks addressed.
- Number of overdue maintenance sessions and overdue action items.
- Number of unresolved high-priority findings and their age.
- Percentage of live-site updates preceded by a verified backup or approved exception.
- Percentage of findings with an owner, next action, and due date.
- Timeliness and delivery status of scheduled reports.
- Reduction in duplicate data entry and manual report preparation.

Targets should be agreed after a baseline is measured; the application should not invent success thresholds.

## 3. Current Problem and Proposed Solution

### 3.1 Current challenges

- Website inventories, checklists, notes, issue lists, and reports may be spread across separate files.
- Excel cannot reliably enforce conditional SOP steps or prevent a session being closed while critical work remains.
- A completed checkbox does not necessarily prove a task was carried out or checked.
- Follow-up actions and developer approvals can be buried in chat messages or free-text notes.
- Recurring schedules and reminders require manual upkeep.
- Managers must manually combine information to understand team workload and maintenance status.
- Previous findings can be lost or overwritten when a new maintenance cycle begins.
- Results from automation tools are not consistently attached to the relevant website, session, or issue.

### 3.2 Proposed solution

OpsHub will maintain a single, linked record for each client or project, website, maintenance cycle, task, issue, approval, backup record, reminder, and report. Every record will have an owner or responsible party where appropriate, a status, timestamps, and a history of meaningful changes.

## 4. Product Scope

### 4.1 Core scope

- Organization, user, and role management.
- General project register and cross-project task tracking.
- WordPress website inventory for live, staging, development, and other environments.
- Configurable maintenance schedules and workflow templates.
- SOP-driven maintenance sessions with conditional tasks.
- Task assignment, due dates, priorities, dependencies, work logs, notes, and evidence.
- Issue and finding management with severity, ownership, remediation, and verification.
- Backup records and pre-update gates.
- Approval workflows for sensitive or developer-owned changes.
- Reminder and notification service.
- Scheduled and on-demand email reports.
- Dashboards, search, filters, exports, and audit trail.
- Safe automation for selected website and configuration checks.

### 4.2 Later enhancements

- Advanced WordPress REST API integration.
- Authorized SSH and hosting-panel integrations.
- Google Drive or approved backup-storage integration.
- Vulnerability-feed integration for plugin and theme inventory.
- Wordfence scan/result integration where a supported and authorized interface is available.
- Browser-based frontend checks using Playwright.
- Team-wide web dashboard in addition to the desktop client.
- Slack or Microsoft Teams notifications.
- SLA rules, escalation policies, recurring issue analytics, and maintenance trend analysis.
- Additional workflow templates for non-WordPress projects and other service operations.

### 4.3 Out of scope for the first production release

- Unattended changes to live-site files, permissions, plugins, themes, or WordPress core.
- Automatic plugin or theme deletion based only on a name appearing in a cleanup list.
- Automatically applying every suggested change from a scanner.
- A replacement for a full source-control, CI/CD, helpdesk, or security information and event management platform.
- Storing raw hosting passwords, API keys, or other secrets in plain text.

## 5. Users, Roles, and Permissions

Permissions should be assigned by role and can be narrowed by project, website, or team where required.

| Role | Responsibilities and typical permissions |
|---|---|
| System Administrator | Manage configuration, users, roles, integrations, notification settings, and global templates. Access sensitive configuration only where authorized. |
| Manager / Operations Lead | View overall workload and reports; assign or reassign work; set priorities; review blockers; approve exceptions where policy allows. |
| Maintenance Engineer | Execute assigned maintenance sessions, record results, attach evidence, create issues, and request approvals. Cannot self-approve restricted actions unless explicitly permitted. |
| Developer | Receive assigned fixes, review technical findings, approve developer-owned changes, record remediation, and request verification. |
| Reviewer / QA | Independently verify selected checks and fixes; return work for correction; record acceptance or rejection. |
| Read-only Stakeholder | View permitted projects, websites, status, and reports without changing operational records. |
| Report Recipient | Receive scheduled email summaries; does not automatically gain application access. |

All access should follow least privilege. A person receiving an email report should not gain access to the application merely because they receive that email.

## 6. Information Architecture and Main Modules

### 6.1 Global dashboard

The dashboard should summarize work across all projects and websites. It should show assigned work, upcoming and overdue deadlines, open critical/high issues, blocked tasks, pending approvals, maintenance sessions in progress, recent changes, and report delivery status.

Every metric should be clickable and open the filtered records behind it. Example metrics can include total active projects, websites due today, overdue tasks, unresolved high-severity issues, and backups awaiting verification. Counts must come from stored records—not hard-coded demo values.

### 6.2 Organization and people

Manage teams, users, roles, working status, notification preferences, and report recipients. Record task assignments and reassignment history. Avoid copying unnecessary personal information into operational records.

### 6.3 Project register

Each project should include a name, identifier, description, client or business unit if applicable, project lead, members, lifecycle status, priority, start and target dates, milestones, links to repositories or documents, and related websites or environments.

### 6.4 Website inventory

Each WordPress website should have a stable record with:

- Name, production domain, staging/development URLs, and environment classification.
- Project/client association, hosting type, responsible maintainer, developer, and reviewer.
- Maintenance frequency, last completed date, next due date, and scheduling policy.
- WordPress/PHP versions and theme/plugin inventory when actually verified.
- Active theme, child-theme details, relevant builder (including Divi, where applicable), and special constraints.
- Backup approach and approved storage location.
- Security tooling and other relevant integrations.
- Persistent notes, developer instructions, previous reports, and unresolved issues.

Website operational health and maintenance workflow status must be separate fields. A site may be online while maintenance is overdue, or maintenance may be running while the site is operating normally.

### 6.5 Maintenance queue

Show maintenance sessions that are due, upcoming, in progress, blocked, awaiting review, completed with findings, or overdue. Support filters by environment, project, owner, due date, priority, and issue severity.

### 6.6 Task and work tracking

The general task system should be usable for every project, not only maintenance. Each task can have a title, description, project, linked website or issue, owner, collaborators, reviewer, priority, status, start/due dates, estimated and actual effort, dependencies, checklist, comments, attachments, work log, and completion criteria.

### 6.7 Issues and findings

A finding can originate from a checklist task, a manual observation, an automated scan, a user report, a deployment, or a project task. It must link to its source record and affected project/site.

### 6.8 Backups

Track backup creation, type, timestamp, location, size when available, result, verification, restore-test status, retention policy, and related maintenance session. Initially this can be a controlled record of manual backup work; automation can be added through supported interfaces later.

### 6.9 Reports and audit history

Generate reports from system records. Preserve a searchable timeline of task status changes, ownership changes, approvals, findings, evidence references, maintenance session events, and report delivery attempts.

## 7. End-to-End Workflows

### 7.1 General project and task lifecycle

1. Create or import a project.
2. Define milestones and work items.
3. Assign a responsible person and set priority and due date.
4. Record work, comments, evidence, blockers, and time where required.
5. Request review or approval when the task requires it.
6. Verify completion against its acceptance criteria.
7. Close the task and preserve the history.
8. Include the outcome in project and team reports.

Suggested task statuses: **Backlog, Ready, In Progress, Blocked, In Review, Changes Requested, Completed, Cancelled**. The system should retain a reason for cancellation and should not allow status changes to erase previous events.

### 7.2 WordPress maintenance lifecycle

1. Scheduler creates a due maintenance item or a maintainer starts an authorized ad hoc session.
2. The maintainer reviews the website profile, last report, open issues, and persistent notes.
3. The system selects the correct workflow template based on environment and website configuration.
4. The maintainer executes the required checks and records results and evidence.
5. Automated read-only checks may run in the background and attach their results to the relevant tasks.
6. Findings create or link to issues; tasks needing approval are routed to the correct person.
7. Required backup and approval gates are evaluated before sensitive update or change work proceeds.
8. Updates or other approved actions are carried out, followed by verification.
9. The final frontend and workflow checks are recorded.
10. The system validates required tasks, unresolved blockers, and exception approvals.
11. The session is closed as **Completed**, **Completed with Findings**, **Blocked**, or **Incomplete** according to defined rules.
12. A report is generated and sent to the configured recipients; next maintenance is scheduled according to the website's policy.

### 7.3 Issue lifecycle

**New → Triaged → Assigned → In Progress → Fixed / Mitigated → Verification → Resolved → Closed**

Alternative states include **Duplicate, Rejected, Accepted Risk, and Reopened**. Closing an issue should preserve its resolution details and verification result. An issue that fails verification should return to the appropriate active state rather than being silently closed.

### 7.4 Approval lifecycle

**Requested → Pending → Approved / Rejected / More Information Required → Executed (if approved) → Verified**

Approval requests should identify the exact action, affected website/project, reason, risk, evidence, requester, approver, and timestamp. Approval must not imply that the action was successfully executed or verified.

## 8. WordPress Site Maintenance SOP — Functional Specification

The following converts the supplied maintenance SOP into a structured workflow. Every task should support a status, owner where needed, result/observation, timestamp, evidence reference, action taken, and follow-up. Tasks can be marked **Not Applicable** only when the template's rules allow it and a reason is recorded.

### 8.1 SOP task and automation matrix

| # | SOP task | Required process and expected application behavior |
|---:|---|---|
| 1 | Website overview | Review the public frontend and key functionality. Record broken/suspicious links, missing images, layout defects, form/checkout problems, or other observations. Automated link checks can assist but do not replace visual review. |
| 2 | Slow website / performance | If the site appears slow, run the approved performance check and record the tool, date, URL, score/metrics, and observations. This SOP calls for recording the result and moving to the next step; remediation should become a separate issue/task unless otherwise directed. |
| 3 | Default/core files | Review WordPress core files and their contents through authorized hosting or administration access. Where feasible, compare core files with trusted checksums for the verified WordPress version. Investigate suspicious differences; record the evidence and obtain approval before destructive action. |
| 4 | `.htaccess` security rules | Check for the team's required clickjacking, MIME-sniffing, HSTS, and PHP-version disclosure controls. Record current values and validation results. Do not blindly append duplicate directives. Validate Apache/module compatibility and domain/subdomain HTTPS readiness before changes. |
| 5 | File permissions | Inspect actual permissions and ownership where filesystem access is available. Compare against a configurable policy for the hosting environment. The SOP's live-site target values (for example, `444` for selected sensitive PHP files and `644` for `.htaccess`) are policy inputs to validate, not universal values that the application should force automatically. |
| 6 | Debug logging | Review `WP_DEBUG`, `WP_DEBUG_LOG`, `WP_DEBUG_DISPLAY`, `SCRIPT_DEBUG`, and related configuration where applicable. Detect duplicate definitions or conflicting configuration. Record the result; avoid editing `wp-config.php` automatically in the first release. |
| 7 | Search-engine discouragement for staging | Confirm that staging sites are configured to discourage indexing. Check the intended `robots.txt` policy and any available visibility of WordPress search-engine settings. Explain that robots directives do not provide access control; recommend authentication or access restrictions for private staging systems. |
| 8 | Directory indexing | Verify that directory listing is disabled at the server/configuration level. Where `.htaccess` is used, check whether `Options -Indexes` is supported. Do not apply unsupported directives automatically. |
| 9 | Backup | For live websites, require a backup before risky maintenance/update work, unless an authorized exception is recorded. Record backup type, result, storage location, timestamp, verification, and restore test if required. For staging, follow the configured staging policy. |
| 10 | WordPress core updates | Record current version and available update. Follow the SOP's developer-confirmation requirement for core upgrades. Track approval and decision. Do not update production core unattended in the initial release. |
| 11 | Theme updates | Record active/parent/child theme information and available updates. Confirm the child theme is active where expected; update the parent theme only under the defined approval policy. Record tests and outcomes. |
| 12 | Plugin updates | Inventory plugins and versions where access allows. Review compatibility and risk before updating. Record selected, deferred, failed, and successful updates. Changes requiring confirmation should be assigned for approval. |
| 13 | Post-update re-check | Re-test the frontend, admin access, forms, checkout, integrations, and other critical functions relevant to the site. If a problem appears, create/link an issue and record resolution or rollback. Do not mark as passed without an actual check. |
| 14 | Plugin conflicts / duplicate functionality | Review plugins that overlap in a function, especially cache/performance tools. Flag possible conflicts for review. Do not deactivate plugins automatically based solely on category; confirm the approved configuration. |
| 15 | Disable auto-update policy | Inspect core/theme/plugin auto-update settings and compare with the organization's policy. The supplied SOP specifies disabling auto-updates; record deviations and approvals. Policy should be reviewed periodically so the process does not unintentionally leave components unpatched. |
| 16 | Unused plugins/themes cleanup | Review the supplied removal list (WP File Manager, Hello Dolly, Akismet Anti Spam, String Locator, WP Rollback, WordPress Importer, All-in-One WP Migration, Better Search Replace). Verify current usage with the developer before deletion. Keep an appropriate default theme in addition to the active theme. Create an approval and action record before removal. A list match is a review trigger, not automatic authorization to delete. |
| 17 | Administrator users | Review users with administrator-level permissions and confirm legitimacy. Record suspicious or unknown accounts as findings, protect sensitive user data, and require approval for account changes. |
| 18 | Site Health | Review WordPress Tools → Site Health recommendations and critical errors. Record findings, impact, planned action, and ownership. Close each finding only after it is addressed or formally accepted with a reason. |
| 19 | Divi Builder (conditional) | Show this task only when the website uses Divi or the maintainer confirms it applies. Review Theme Options → Integration settings under the team's SOP. Any movement of custom code into theme files must be reviewed by a developer and tested against child-theme and update practices. |
| 20 | Security plugins | Verify the expected configuration and behavior of security-related plugins (for example, WPS Hide Login, Advanced reCAPTCHA, Limit Login Attempts, Stream, and Password Protected where appropriate). Applicability depends on the site's configuration; Password Protected may be staging-specific. Record what was checked. |
| 21 | Wordfence scan | Verify configured Wordfence settings according to the approved internal guide, run a scan, review warnings/errors, create issues for actionable findings, and record a re-scan after changes. A scan reporting no issues does not by itself certify the entire site as secure. |
| 22 | Final frontend check | Revisit the public frontend and relevant key functions before closing the session. Record the result and any new finding. This is a required final gate for applicable sites. |
| 23 | Review notes | Review the website's persistent notes, previous maintenance notes, open issues, and developer instructions. Record that the review occurred and carry forward unresolved actions. |

### 8.2 Rule references maintained in the system

The application should provide editable, versioned internal reference notes for:

- The required `.htaccess` security-header rules.
- The team's PHP-version disclosure mitigation and alternate header-based approach.
- The staging `robots.txt` directive: `User-agent: *` / `Disallow: /`.
- The team's live-site crawler guidance, subject to SEO review.
- The directory-indexing directive where supported.
- The intended WordPress debug constants and their approved configuration.
- The list of plugins/themes that should be reviewed for removal.
- The internal Wordfence configuration guide and related SOP links.

These snippets should be references for approved maintenance, not commands that are silently applied. The live-site robots rules should be reviewed with SEO/operations because blocking assets or administrative paths in `robots.txt` is not a security control and can have unintended crawler/rendering effects. HSTS with `includeSubDomains` should only be enabled after all affected subdomains are confirmed ready for HTTPS. The application's automated checks should flag uncertainty and request review rather than claim unsupported directives are correct.

### 8.3 Conditional rules and completion gates

- Live site: backup must be verified before update/change work, unless an authorized exception is recorded.
- Staging site: verify indexing policy and configured access protection; do not assume `robots.txt` makes it private.
- Divi site: show Divi-specific check; otherwise record Not Applicable according to the template.
- Core upgrade: require the configured developer/manager approval.
- Plugin/theme deletion: require recorded confirmation/approval.
- Critical post-update failure: create or link a high-priority issue and block normal closure until resolved or an authorized exception is recorded.
- Automated check without adequate access: mark **Not Verified / Access Required**, never Passed.
- Final frontend check and review of previous notes: required before a normal completed status.

## 9. General Project and Task Management

OpsHub should also track work across all projects—for example, deployment improvements, application features, security tasks, website fixes, SOP updates, and internal tooling.

### 9.1 Project capabilities

- Create projects with owners, team members, priority, status, objectives, milestones, start/target dates, and linked documents or repositories.
- Group tasks by milestone, feature, environment, sprint, workstream, or custom category.
- Associate a task with a website, maintenance session, issue, release, or external ticket.
- Track dependencies, blockers, review steps, and approvals.
- Keep comments, evidence, decisions, and work logs attached to the record.
- Show task distribution and overdue work by assignee and project.
- Search across projects and filter by date, person, status, priority, and label.
- Record progress based on completed work and milestone rules rather than manually typed percentages alone.

### 9.2 Task record

Minimum fields: task ID, title, description, project, owner, collaborators, reviewer/approver if needed, status, priority, creation date, start date, due date, completion date, estimate/actual effort where required, dependencies, acceptance criteria, attachments/evidence, comments, and change history.

### 9.3 Work logs and team accountability

Users should be able to record a concise work update against a task: what was done, what remains, any blocker, and the next action. The system should not silently infer time spent. Optional effort tracking should be explicit and configured for the team's policy.

## 10. Issue and Risk Management

### 10.1 Issue categories

- Security vulnerability or suspicious activity.
- Broken frontend function, link, image, form, or checkout.
- Performance concern.
- Update failure or plugin/theme conflict.
- Backup failure or unverified backup.
- Configuration or permission deviation.
- WordPress Site Health warning.
- Deployment/build failure.
- General project blocker or defect.

### 10.2 Issue fields

Issue ID, title, detailed description, project/site, source task/session, category, severity, priority, owner, reviewer, status, created/updated dates, due date, evidence, affected version/component, reproduction steps where relevant, remediation notes, verification outcome, and closure reason.

### 10.3 Severity and priority

Keep impact severity separate from scheduling priority. Suggested severity levels: **Critical, High, Medium, Low, Informational**. Suggested priority levels: **Urgent, High, Normal, Low**. Provide configurable definitions and response expectations. Avoid inventing a security severity from an unverified check.

### 10.4 Escalation

Critical/high issues can trigger immediate notifications to configured people. If the issue remains unresolved past its due time, the system may escalate to a manager. Escalation rules must be configurable and logged.

## 11. Automation, Reminders, and Notifications

### 11.1 Automation principles

Classify all automation as one of:

1. **Read-only check:** safe observation with no configuration change.
2. **Suggested action:** creates a recommendation/task for a person.
3. **Approved action:** can run only after an authorized approval.
4. **Restricted production action:** disabled in the initial release unless a separately reviewed automation design, backup, rollback, and authorization process exists.

### 11.2 First automation candidates

- HTTP reachability and response status.
- TLS/SSL certificate expiration checks.
- Required HTTP security-header inspection.
- Basic response-time checks.
- Broken-link and missing-image discovery on selected pages.
- Maintenance due-date calculation and reminders.
- Missing required task/evidence detection.
- Report generation from stored records.
- Plugin/theme/core inventory through authorized WordPress/server interfaces, when available.
- Backup-record completeness checks.

Some checks require authentication, filesystem or hosting access, JavaScript-capable browser tests, or a supported integration. Results must state which checks were performed, what access was used, the timestamp, and any limitations.

### 11.3 Scheduling

Support per-website and per-project frequency rules: weekly, monthly, quarterly, custom interval, or manually scheduled. Record the planned due date and actual completion date separately. The system should support a configurable next-due rule (for example, anchored to the planned calendar date or calculated from completion) rather than silently choosing one behavior.

### 11.4 Reminder rules

- Upcoming work: configurable lead time (for example, several days before due date).
- Due today: notify the owner and optionally the team channel.
- Overdue: notify the owner and escalate after configured thresholds.
- Approval pending: remind the approver and requester.
- Issue approaching/overdue: notify the issue owner.
- Backup not verified: prevent sensitive maintenance progression where configured and notify the owner.
- Maintenance session idle or blocked: configurable follow-up.
- Report failure: notify an administrator so delivery problems are not silent.

### 11.5 Reliability

Scheduled jobs and email reporting should run through a service that is available independently of a single user's desktop session. A desktop-only prototype may show local reminders, but team production reminders need a continuously running scheduler/backend and retry handling.

## 12. Email Reports and Notifications

### 12.1 Report types

- Daily team work summary.
- Weekly project progress report.
- Website maintenance completion report.
- Upcoming and overdue maintenance report.
- Open issue and risk report.
- Pending approval report.
- Backup status report.
- High-severity issue alert.
- Failed automation or failed email-delivery alert.

### 12.2 Maintenance completion email

Suggested contents:

- Website name, environment, maintenance date, maintainer, and reviewer.
- Final session status.
- Summary of passed, failed, blocked, skipped, and not-verified checks.
- Backup result and reference (without sensitive credentials or public links to protected files).
- Updates performed or deferred.
- Issues discovered, assigned owners, severity, and due dates.
- Approvals and exceptions recorded.
- Next maintenance due date.
- Link to the internal record/report where authorized.

### 12.3 Email configuration

Support configurable SMTP or an approved email service, sender identity, recipient groups, templates, test-send function, delivery history, retry policy, and failure alerts. Secrets must be kept in a protected secret store or deployment environment—not plain-text configuration files or logs. Recipient lists should be scoped by project and role; avoid sending sensitive findings to broad mailing lists.

### 12.4 Report integrity

Reports must be generated from saved application records and show generation time. If a session changes after a report has been sent, the system should retain the old delivery record and allow a clearly marked updated report to be sent. Email delivery is a communication event, not proof that a recipient read or acted on the report.

## 13. Dashboard, Search, and Reports

### 13.1 Global dashboard widgets

- Active projects and milestones.
- Total registered websites by environment.
- Maintenance due today / in the next 7 days / overdue.
- Sessions in progress, blocked, awaiting review, or completed with findings.
- Open critical/high issues.
- Issues by owner and age.
- Approvals waiting for a decision.
- Backups awaiting verification.
- Tasks completed today/this week.
- Upcoming SSL expirations or automated check failures, if those checks are enabled.
- Most recent activity and email-report status.

### 13.2 Reports and exports

Allow authorized users to export PDF, CSV, and Excel-compatible records. Report types should include per-site history, session checklist and evidence references, issue register, assignment/workload summary, maintenance compliance, overdue list, backup status, and project progress. Exports should respect access permissions and apply appropriate redaction to sensitive fields.

## 14. Recommended Technical Architecture

### 14.1 Production direction

Because the requested system includes team assignment, centralized tracking, scheduled emails, and cross-project reporting, the intended production architecture should use a central backend and shared database. The desktop app is a client—not the single source of truth.

```text
PySide6 Desktop Client
        |
        | HTTPS / authenticated API
        v
FastAPI Backend  <----> Scheduler / Background Workers
        |
        v
PostgreSQL Database
        |
        +---- File/evidence storage (controlled access)
        +---- Email service / SMTP
        +---- WordPress / SSH / monitoring integrations
```

A local SQLite prototype is acceptable for validating screens and workflow concepts, but multi-user production should move to the central API/database before team-wide reliance on shared records.

### 14.2 Recommended stack

| Layer | Recommended technology | Responsibility |
|---|---|---|
| Desktop GUI | PySide6 + Qt Widgets | Main application, forms, tables, workflows |
| Styling | Qt Style Sheets (QSS) | Consistent professional UI |
| Language | Python 3.12+ or a team-approved supported version | Application logic and integrations |
| Backend API | FastAPI | Centralized access, validation, authentication hooks, and integration endpoints |
| Database | PostgreSQL for team production; SQLite only for prototype/offline mode | Shared operational data |
| ORM and migrations | SQLAlchemy 2.x + Alembic | Data access and schema evolution |
| Background jobs | Dedicated worker/scheduler using APScheduler or an appropriate queue | Reminders, scans, reports, retries |
| HTTP checks | HTTPX | Website/API checks and headers |
| HTML parsing | Beautiful Soup | Link and image discovery |
| Browser tests | Playwright | Selected frontend smoke tests |
| SSH integration | Paramiko, only with authorized access | Remote diagnostics and selected read-only checks |
| Credentials | OS keyring for local mode; server-side secret management in deployment | Store sensitive credentials safely |
| Charts | PyQtGraph | Trends and operational metrics |
| Reports | ReportLab, CSV tooling, openpyxl for Excel compatibility | PDF and spreadsheet exports |
| Testing | pytest | Unit and integration tests |
| Packaging | PyInstaller or a team-approved installer method | Desktop distribution |
| Deployment | Linux server; Docker can be used where suitable | Host API, scheduler, and database services |
| Observability | Structured application logs, health endpoints, and alerting | Diagnose failures and monitor the service |

Versions should be pinned and reviewed for compatibility during implementation rather than assuming every library's newest release is automatically suitable.

### 14.3 Architectural boundaries

Separate UI, business rules, database access, notification delivery, workflow logic, and external integrations. An integration failure should not corrupt maintenance records. Long-running checks must run in background workers so the GUI remains responsive. Every automated result should be stored with timestamp, source, result, access limitations, and relevant evidence.

## 15. High-Level Data Model

Recommended core entities:

| Entity | Key purpose and relationships |
|---|---|
| Organization / Team | Groups users, projects, and configuration |
| User / Role | Identity, permissions, team membership, notification settings |
| Project | General project record with members, milestones, and dates |
| Website / Environment | Live, staging, development, or other site linked to a project |
| Workflow Template | Versioned reusable SOP and conditional rules |
| Maintenance Schedule | Frequency, due-date policy, owner, and active state |
| Maintenance Session | One execution of a template for a website and date/cycle |
| Task / Checklist Item | General task or session-specific SOP task |
| Evidence / Attachment | Protected file or reference linked to tasks/issues/sessions |
| Issue / Finding | Problem, risk, ownership, severity, remediation, and verification |
| Approval | Action request, decision, approver, rationale, and timestamps |
| Backup Record | Type, location, result, verification, restore-test status |
| Reminder / Notification | Trigger, recipient, delivery state, retry history |
| Report / Report Delivery | Report metadata, recipients, generated time, delivery outcome |
| Activity Event | Append-oriented record of significant changes and actions |
| Integration Configuration | Non-secret settings and references to protected credentials |

Workflow templates must be versioned. A session should keep the exact template version and task definitions used when it was started, so later SOP edits do not rewrite past results.

## 16. Security, Auditability, and Data Protection

- Use authenticated access and role-based permissions for the central system.
- Use HTTPS for network communication and protect API tokens and session secrets.
- Keep production credentials out of source code, SQLite plain-text values, attachments, email reports, and application logs.
- Use a credential/secret store and support revocation/rotation.
- Follow least privilege for WordPress accounts and server access; read-only access should be preferred where possible.
- Log who performed important operations, approvals, assignments, status changes, and external actions.
- Restrict evidence attachments and exported reports to authorized users.
- Define retention and deletion rules for logs, attachments, reports, and backups.
- Back up the OpsHub database and test restoration periodically.
- Validate uploaded file type/size and store attachments outside publicly served directories or in controlled object storage.
- Add protections against duplicate jobs, repeated emails, and concurrent updates.
- Provide a way to disable or revoke an integration without losing historical records.
- Treat any action against a live website as sensitive and auditable.

### Safety boundary for automation

The first release should focus on read-only checks, recommendations, and workflow enforcement. Editing `.htaccess`, changing file permissions, editing `wp-config.php`, deleting plugins/themes/users, changing auto-update settings, restoring backups, or updating production components must require explicit authorization and an appropriate test/backup/rollback path. Automation should fail safely and clearly report when it cannot verify a condition.

## 17. User Interface and Experience

The UI should use a consistent navigation shell with a sidebar and a central work area. Suggested primary navigation:

- Overview
- Projects
- My Tasks
- All Tasks
- Websites
- Maintenance Queue
- Issues & Findings
- Approvals
- Backups
- Reports
- Notifications
- Activity History
- Administration / Settings

Key interactions:

- Global search across projects, tasks, sites, and issue IDs.
- Tables with fast filtering, sorting, saved views, and pagination.
- Website detail page with overview, maintenance history, open issues, backups, notes, and schedule.
- Maintenance session page with progress, conditional SOP checklist, evidence, findings, and approval requests.
- Task detail page with owner, due date, dependencies, comments, work logs, and acceptance criteria.
- Clear display of Not Verified, Blocked, Failed, and Not Applicable states; do not convey uncertainty as a success badge.
- Confirmation dialogs for sensitive actions and a visible audit trail after execution.

The visual design should prioritize clarity and efficiency over decorative dashboards. Color must not be the only way to communicate status; pair it with readable text and icons.

## 18. Non-Functional Requirements

- **Reliability:** A failed check or email should not stop other queued jobs or lose records.
- **Responsiveness:** Long-running tasks must not freeze the desktop interface.
- **Traceability:** Important state changes and external actions must be attributable and time-stamped.
- **Data integrity:** Relationships between projects, websites, sessions, tasks, and issues must be validated.
- **Extensibility:** New SOP steps and templates should be configurable without rewriting the whole application.
- **Maintainability:** Use modular code, automated tests, documented configuration, and versioned schema migrations.
- **Security:** Least privilege, protected credentials, role checks, secure transport, and controlled exports.
- **Usability:** Users should be able to identify their next action and why a task is blocked.
- **Portability:** The desktop client should be packageable for the approved operating systems, with Linux/Ubuntu support included.
- **Recoverability:** Database and attachment backups should have documented and tested restoration steps.

## 19. Phased Delivery Roadmap

### Phase 0 — Discovery and SOP sign-off

- Confirm the current Excel columns and import formats.
- Confirm site count, project count, teams, roles, and permission boundaries.
- Review and approve the existing SOP, including environment-specific rules.
- Agree on issue severity, task statuses, reminder thresholds, and report recipients.
- Identify available WordPress, hosting, email, and backup integrations.

**Exit criterion:** The team approves the first workflow template and core data fields.

### Phase 1 — Foundation and inventory

- Create project structure and UI shell.
- Implement user/role foundations and project/site registry.
- Import websites from CSV/Excel with validation and duplicate detection.
- Add search, filters, owner assignment, frequency, last/next due, and notes.
- Build global dashboard from real records.

**Exit criterion:** The inventory can be maintained without the master Excel sheet for new entries, and imported records reconcile correctly.

### Phase 2 — SOP workflow engine

- Implement versioned workflow templates.
- Add all 23 maintenance tasks and conditional rules.
- Add task status, observations, evidence, timestamps, approvals, and reasons for Not Applicable/Blocked.
- Add session progress and required completion gates.
- Preserve historical sessions and template versions.

**Exit criterion:** A maintainer can complete a representative live site and staging site maintenance cycle end-to-end with traceable results.

### Phase 3 — Assignments, issues, and approvals

- Implement task ownership, reassignment history, priority, due dates, dependencies, comments, and work logs.
- Implement issue lifecycle and remediation verification.
- Implement developer/manager approval flow and exception records.
- Add personal task views and manager workload views.

**Exit criterion:** Work can be assigned, followed up, reviewed, and closed without tracking the same action in a separate issue sheet.

### Phase 4 — Central scheduler and email reporting

- Implement recurring schedules and due-date policy.
- Add reminders, escalation rules, retry handling, and delivery logs.
- Create completion, daily, weekly, overdue, issue, approval, and backup reports.
- Add test-send and recipient management.

**Exit criterion:** Scheduled reports and reminders run without an employee's desktop being open, and failures are visible to administrators.

### Phase 5 — Safe website automation

- Add HTTP availability, TLS expiry, security-header, basic performance, and selected link/image checks.
- Store results as evidence and create findings where appropriate.
- Add optional WordPress REST API/authorized SSH checks after access/security review.
- Add browser smoke tests for agreed critical workflows.

**Exit criterion:** Automated checks report their limitations accurately and do not make unapproved production changes.

### Phase 6 — Hardening and rollout

- Complete permissions and security review.
- Test database and attachment restoration.
- Validate audit history, concurrency, scheduler idempotency, and email failures.
- Pilot with a small set of live and staging websites.
- Compare OpsHub outputs with the existing process, resolve gaps, then expand.
- Document onboarding, support, backup, and recovery procedures.

**Exit criterion:** The pilot team signs off and the migration plan for remaining records is approved.

## 20. Acceptance Criteria for the First Useful Release

The release is ready for controlled team use when:

1. Existing website records can be imported and validated without duplicate or silent data loss.
2. Every website can have an owner, environment type, schedule, and persistent notes.
3. A maintenance session creates a historical record and uses a versioned SOP template.
4. All supplied SOP stages are available, with conditional logic for live/staging and Divi where relevant.
5. The application distinguishes Passed, Failed, Blocked, Not Applicable, and Not Verified.
6. Required backup and approval gates work according to configuration.
7. Issues can be created from checklist findings, assigned, tracked, verified, and closed with history retained.
8. Managers can see all overdue tasks, open high-priority issues, pending approvals, and workload by owner.
9. Reminders and emails are generated by a central service, with delivery history and failure handling.
10. Reports reflect saved records and include outstanding tasks and findings.
11. The system records meaningful changes with actor and timestamp.
12. Sensitive actions are protected by permissions and explicit confirmation.
13. Automated checks do not mark inaccessible conditions as Passed.
14. Database backup and restoration have been tested.
15. Basic automated tests cover workflow gating, recurrence, permissions, and issue closure behavior.

## 21. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| SOP contains rules that vary by host or site | Use configurable policies; require review before applying environment-sensitive rules. |
| Automation misreports a result due to lack of access | Use Not Verified/Access Required and record the check's limitations. |
| Production change breaks a website | Read-only first; require approvals, backup gates, test plans, and rollback procedures. |
| Team continues to use parallel untracked spreadsheets | Import existing data, define a cutover date, and retain export capability. |
| Reminders fail when a desktop is closed | Run scheduler and email delivery on a continuously available backend. |
| Too much scope delays initial delivery | Prioritize inventory, SOP workflow, task/issue ownership, and reports before advanced scanning. |
| Duplicate or noisy alerts | Add deduplication, severity thresholds, configurable frequency, and notification preferences. |
| Credentials leak through logs or reports | Secret management, redaction, restricted attachments, and security tests. |
| SOP changes make historic reports confusing | Version templates and preserve the version used by each session. |
| Single-user database becomes a team bottleneck | Design modularly and use a central API/database for production collaboration. |

## 22. Decisions to Confirm Before Development

These items should be resolved during discovery; implementation can proceed with stated defaults if a decision is not yet available.

1. **Initial users:** single maintainer, small internal team, or multiple teams?
2. **Deployment target:** Ubuntu desktop first, Windows as well, or a web interface required from day one?
3. **Shared data:** Is a central server available for the API, database, and scheduler?
4. **Email:** Which SMTP/provider and sender mailbox are approved?
5. **Reports:** Who receives each report, at what frequency, and which information is sensitive?
6. **Website access:** Which sites can use WordPress API, SSH, cPanel, or other supported interfaces?
7. **Backup process:** Which tool/storage is approved, and what qualifies as verified for live-site updates?
8. **Approvals:** Which actions need maintainer, developer, manager, or security approval?
9. **SOP policy:** Are the permission values, robots.txt rules, HSTS choices, auto-update policy, and cleanup list confirmed for every relevant environment?
10. **Migration:** Which existing Excel sheets and historical records must be imported?
11. **Retention:** How long should reports, evidence, issues, activity logs, and backup metadata be retained?
12. **Access control:** Which users can see client/site information, credentials references, security findings, and exported reports?

## 23. Recommended Build Strategy

Build the product in this order:

1. **Make the data trustworthy:** project/site inventory, ownership, schedules, session history, and audit events.
2. **Make the workflow dependable:** complete SOP template, conditional tasks, evidence, approvals, and closure gates.
3. **Make work visible:** task assignment, issue ownership, blockers, reminders, and management dashboards.
4. **Make reporting automatic:** email summaries, completion reports, overdue reports, and delivery logs.
5. **Add safe automation:** begin with read-only checks, then add carefully approved integrations.
6. **Expand coverage:** apply the general project/task system to other operational workstreams.

Avoid building an elaborate dashboard before the underlying records and workflow rules are stable. A simple dashboard driven by reliable data is more useful than a visually impressive dashboard full of manually maintained statuses.

## 24. Conclusion

OpsHub should become the team's single operational record for maintenance and project work. Its first priority is to convert the WordPress Site Maintenance SOP into a reliable, assignable, auditable workflow. Its broader task and project modules will then allow the team to manage development work, incidents, deployments, approvals, and recurring operational tasks in the same system.

The defining qualities are **traceability, practical automation, safe handling of production systems, clear ownership, and dependable reporting**. Every maintenance session should show what was checked, what was found, what was changed, who approved it, what remains open, and when the next action is due.

The recommended production direction is a PySide6 desktop client backed by a centralized FastAPI service and PostgreSQL database, with a scheduler/worker service for reminders and reports. A local prototype can be used to validate the user experience, but team-wide operations should rely on a central source of truth before the system becomes operationally critical.
