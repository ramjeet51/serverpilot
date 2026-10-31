"""Single source of truth for RBAC permission codes and built-in roles."""

PERMISSIONS: dict[str, str] = {
    "accounts:read": "View platform user accounts",
    "accounts:write": "Create and modify platform user accounts",
    "audit:read": "View the audit log",
    "jobs:read": "View jobs and job logs",
    "jobs:write": "Create and retry jobs",
    "jobs:cancel": "Cancel jobs",
    "servers:read": "View servers and agents",
    "servers:write": "Add, register and remove servers",
    "monitoring:read": "View metrics and dashboards",
    "system:read": "View system information",
    "files:read": "Browse and download files",
    "files:write": "Upload, edit and delete files",
    "software:read": "View installed software",
    "software:write": "Install, update and remove software",
    "services:read": "View system services",
    "services:write": "Control system services",
    "docker:read": "View Docker resources",
    "docker:write": "Manage Docker resources",
    "linux_users:read": "View Linux users and groups",
    "linux_users:write": "Manage Linux users and groups",
    "network:read": "View network configuration",
    "network:write": "Change network and firewall configuration",
    "deployments:read": "View deployments",
    "deployments:write": "Run and roll back deployments",
    "plugins:read": "View plugins",
    "plugins:write": "Install and configure plugins",
}

_READ = [p for p in PERMISSIONS if p.endswith(":read") and p not in ("audit:read", "accounts:read")]
_OPERATOR_WRITE = ["jobs:write", "jobs:cancel", "servers:write", "files:write", "software:write", "services:write",
                   "docker:write", "deployments:write"]

ROLES: dict[str, dict] = {
    "admin": {"description": "Full administrative access", "permissions": list(PERMISSIONS)},
    "operator": {"description": "Operate servers and run jobs", "permissions": _READ + _OPERATOR_WRITE},
    "viewer": {"description": "Read-only access", "permissions": _READ},
}
