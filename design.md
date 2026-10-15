# OpsHub UI/UX & Design System Specification

**Document Version:** 1.0  
**Date:** 15 October 2026  
**Target Framework:** PySide6 (Qt Widgets) with Modular Qt Style Sheets (QSS)  

## 1. Visual Design Philosophy Prioritizes Operational Clarity Over Decoration

OpsHub is a high-density engineering and operations command center. Every screen must communicate ownership, epistemic verification state, blockers, and next actions at a glance.

### Core UX Rules

1. **Never Convey Uncertainty as Success:** `Not Verified / Access Required` and `Not Applicable` must have distinct neutral/warning styling with explicit icons and labels—never green checkmarks.
2. **Color Is Paired with Text and Iconography:** Every status badge combines a distinct background tint, border, icon glyph, and uppercase label so color-vision-deficient users never rely on hue alone.
3. **Every Dashboard Metric Is Clickable:** Summary cards act as live filters; clicking `Overdue Maintenance (4)` opens the Maintenance Queue pre-filtered to `status=overdue`.
4. **Non-Blocking Responsive Shell:** All API calls, file imports, report generations, and HTTP checks run in background `QRunnable` / `QThread` workers with inline progress indicators.
5. **Explicit Confirmation for Sensitive Actions:** Closing a session with findings, approving a backup exception, or overriding a policy requires a modal confirmation dialog that records the actor's rationale.

## 2. Semantic Color Palette and Status Badge Tokens (QSS)

| Semantic Token | Hex / Color Value | Contrast Ratio | Usage & Paired Badge Label |
| :--- | :--- | :--- | :--- |
| **Surface Primary** | `#F8FAFC` (Slate 50) | — | Main work area background for low eye strain during long checklists. |
| **Surface Card / Panel** | `#FFFFFF` (Pure White) | — | Table containers, detail drawers, and checklist step cards (`1px solid #E2E8F0`). |
| **Sidebar Shell** | `#0F172A` (Slate 900) | `15.8:1` (`#F8FAFC` text) | Persistent left navigation shell and global command header. |
| **Primary Brand / Action** | `#2563EB` (Blue 600) | `5.1:1` (White text) | Primary action buttons, active navigation indicator, focused inputs. |
| **Status: Passed / Verified** | `#15803D` text on `#DCFCE7` bg | `5.4:1` | `[✓ PASSED]` / `[✓ VERIFIED]` — Confirmed by human or authorized check. |
| **Status: Failed / Critical** | `#B91C1C` text on `#FEE2E2` bg | `6.1:1` | `[✕ FAILED]` / `[! CRITICAL]` — Check failed or critical blocker active. |
| **Status: Blocked / Gate** | `#9A3412` text on `#FFEDD5` bg | `5.7:1` | `[⊘ BLOCKED]` — Waiting on backup verification, dependency, or approval. |
| **Status: Not Verified** | `#854D0E` text on `#FEF9C3` bg | `6.3:1` | `[? NOT VERIFIED]` — Automated check lacked credentials/access, or pending check. |
| **Status: In Progress / Due** | `#1D4ED8` text on `#DBEAFE` bg | `5.9:1` | `[↻ IN PROGRESS]` / `[◷ DUE TODAY]` — Active operational work. |
| **Status: Not Applicable** | `#475569` text on `#F1F5F9` bg | `6.8:1` | `[— N/A]` — Rule-exempt step (e.g., Divi check on a non-Divi site) with recorded reason. |

## 3. Application Shell and 13 Primary Navigation Views

```text
+--------------------------------------------------------------------------------------------------+
| OpsHub Command Center    [ Global Search: Projects, Sites, Tasks, Issue IDs (Ctrl+K) ]  [User/Role]|
+----------------------+---------------------------------------------------------------------------+
| PRIMARY NAVIGATION   | BREADCRUMB: Websites > acme-corp.com > Maintenance Session #MS-2026-104   |
|                      +---------------------------------------------------------------------------+
| 1. Overview          | HEADER BAR: acme-corp.com [LIVE] | Health: [✓ ONLINE] | Workflow: [↻ IN PROG]|
| 2. Projects          | Backup Gate: [✓ VERIFIED 14:10] | Progress: 14/23 Steps | [Close Session] |
| 3. My Tasks          +-----------------------------------+---------------------------------------+
| 4. All Tasks         | SOP CHECKLIST (23 STEPS)          | STEP DETAIL & EVIDENCE DRAWER         |
| 5. Websites          |                                   |                                       |
| 6. Maintenance Queue | [✓] 01. Website overview          | Step 10: WordPress Core Updates       |
| 7. Issues & Findings | [✓] 02. Slow website / perf       | Current: 6.6.1 -> Available: 6.6.2    |
| 8. Approvals         | [?] 03. Default/core files        |                                       |
| 9. Backups           | [✓] 04. .htaccess security rules  | Pre-Update Backup Gate: [✓ SATISFIED] |
| 10. Reports          | ...                               | Developer Approval: [#AP-88 PENDING]  |
| 11. Notifications    | [✓] 09. Backup (Verified)         |                                       |
| 12. Activity History | [⊘] 10. WordPress core updates    | Observation / Notes:                  |
| 13. Admin / Settings | [ ] 11. Theme updates             | [ Minor security release; requested   |
|                      | [—] 19. Divi Builder (N/A)        |   dev confirmation from @rahul ]      |
|                      | [ ] 22. Final frontend check      |                                       |
|                      | [ ] 23. Review notes              | [Request Approval] [Spawn Issue]      |
+----------------------+-----------------------------------+---------------------------------------+
```

### Module-by-Module UI Specification

| # | Navigation Module | Primary UI Components & User Interactions |
| :--- | :--- | :--- |
| **1** | **Overview (Global Dashboard)** | 11 clickable KPI cards (Active Projects, Websites Due Today/7d/Overdue, Sessions by State, Critical/High Issues, Pending Approvals, Unverified Backups, Tasks Completed, SSL Expirations, Report Delivery Status) + recent activity feed. |
| **2** | **Projects** | Filterable project registry table, milestone progress bars computed from actual completed tasks, team member roster, and linked websites/repositories tab. |
| **3** | **My Tasks** | Focused personal workbench grouped by `Due Today`, `Overdue`, `In Progress`, `Blocked`, and `Awaiting My Review`, with quick work-log entry. |
| **4** | **All Tasks** | Cross-project master task table with multi-column sorting, saved filter views, dependency visualizer, and bulk owner reassignment for managers. |
| **5** | **Websites** | Inventory table showing separate `Health Status` and `Workflow Status` badges, CSV/Excel import wizard with dry-run validation preview, and multi-tab Website Detail view (Overview, SOP History, Open Issues, Backups, Persistent Notes, Rules Reference). |
| **6** | **Maintenance Queue** | Operational queue of due, upcoming, in-progress, blocked, and overdue maintenance sessions with one-click session launch or resume. |
| **7** | **Issues & Findings** | Split-view issue register with separate `Severity` and `Priority` filters, source session/task link, remediation notes, and QA Verification sign-off panel. |
| **8** | **Approvals** | Decision inbox for Developers and Managers displaying requester, affected site/step, risk notes, evidence links, and `[Approve]` / `[Reject]` / `[Request Info]` actions. |
| **9** | **Backups** | Backup ledger recording timestamp, type, storage location, verification checkbox, restore-test status, and exception approval link. |
| **10** | **Reports** | Report generator and delivery log viewer supporting on-demand PDF/CSV/XLSX export, scheduled recipient group management, and `[Test Send]` verification. |
| **11** | **Notifications** | Personal and system alert center showing due reminders, escalations, approval decisions, and failed background job alerts. |
| **12** | **Activity History** | Immutable audit log browser filterable by actor, date range, entity type, and action with JSON diff inspection. |
| **13** | **Administration / Settings** | User/role matrix, SOP template version editor, editable Rule Reference snippets (`.htaccess`, `robots.txt`, cleanup list), and keyring-backed integration settings. |

## 4. Interactive SOP Session Screen Enforces Conditional Logic and Gates

1. **Dynamic Step Filtering:**
   - When `website.environment == 'staging'`, Step 7 (`Search-engine discouragement for staging`) is automatically highlighted as `Required`. When `environment == 'live'`, Step 7 defaults to `Not Applicable` with pre-filled reason `"Live production site"`.
   - When `website.builder != 'divi'`, Step 19 (`Divi Builder`) defaults to `Not Applicable` with a toggle allowing the maintainer to activate it if Divi is detected during inspection.
2. **Inline Rule Reference Drawer:**
   - Selecting Steps 4, 5, 6, 7, 8, 16, or 21 displays a collapsible `"Approved SOP Reference Snippet"` panel alongside the observation field so maintainers can copy or compare approved `.htaccess` headers, debug constants, or the 8-item plugin cleanup review list without leaving the app.
3. **Interactive Gate Banner:**
   - Steps 10, 11, and 12 display a prominent lock banner on Live sites until Step 9 (`Backup`) has a linked verified backup record or an approved exception.
