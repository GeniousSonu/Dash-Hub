from enum import Enum


class WebsiteEnvironment(str, Enum):
    LIVE = "live"
    STAGING = "staging"
    DEV = "dev"


class HealthStatus(str, Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class WorkflowStatus(str, Enum):
    UP_TO_DATE = "up_to_date"
    DUE = "due"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    OVERDUE = "overdue"


class BuilderType(str, Enum):
    GUTENBERG = "gutenberg"
    DIVI = "divi"
    ELEMENTOR = "elementor"
    OTHER = "other"


class ChecklistItemStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"
    NOT_VERIFIED = "not_verified"


class SessionStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPLETED_WITH_FINDINGS = "completed_with_findings"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class IssueSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueStatus(str, Enum):
    NEW = "new"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    FIXED_MITIGATED = "fixed_mitigated"
    VERIFICATION = "verification"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"
    ACCEPTED_RISK = "accepted_risk"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MORE_INFO_REQUIRED = "more_info_required"
    EXECUTED = "executed"
    VERIFIED = "verified"


class DueAnchorPolicy(str, Enum):
    PLANNED_DATE = "planned_date"
    COMPLETION_DATE = "completion_date"


class UserRole(str, Enum):
    SYSTEM_ADMIN = "system_admin"
    MANAGER = "manager"
    DEV_OPS_ENGINEER = "Dev_Ops_Engineer"
    MAINTENANCE_ENGINEER = "maintenance_engineer"
    DEVELOPER = "developer"
    REVIEWER_QA = "reviewer_qa"
    READONLY_STAKEHOLDER = "readonly_stakeholder"
    REPORT_RECIPIENT = "report_recipient"
