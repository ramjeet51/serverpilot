"""Package and service allowlist for the agent. Keep ids aligned with backend app.services.catalogue."""

CATALOGUE = {
    "nginx": {"packages": ("nginx",), "service": "nginx", "protected_remove": False, "archive": None},
    # detect lists every package name that means this product is already on the machine.
    # packages is what we install only when none of those names is present.
    "docker-engine": {
        "packages": ("docker.io",),
        "detect": ("docker-ce", "docker-ce-cli", "docker.io"),
        "service": "docker", "protected_remove": False, "archive": None,
    },
    "docker-compose": {
        "packages": ("docker-compose-v2",),
        "detect": ("docker-compose-plugin", "docker-compose-v2", "docker-compose"),
        "service": None, "protected_remove": False, "archive": None,
        "requires": ("docker-engine",),
    },
    "java": {
        "packages": ("default-jre-headless",),
        "detect": ("default-jre-headless", "openjdk-21-jre-headless", "openjdk-17-jre-headless"),
        "service": None, "protected_remove": False, "archive": None,
    },
    "jenkins": {
        "packages": ("jenkins",), "service": "jenkins", "protected_remove": False, "archive": "jenkins",
        "requires": ("java",),
    },
    "mysql": {"packages": ("mysql-server",), "service": "mysql", "protected_remove": False, "archive": None},
    "postgresql": {"packages": ("postgresql",), "service": "postgresql", "protected_remove": False, "archive": None},
    "redis": {"packages": ("redis-server",), "service": "redis-server", "protected_remove": False, "archive": None},
    "nodejs": {"packages": ("nodejs",), "service": None, "protected_remove": False, "archive": None},
    "python": {"packages": ("python3",), "service": None, "protected_remove": True, "archive": None},
    "php": {"packages": ("php-cli",), "service": None, "protected_remove": False, "archive": None},
    "prometheus": {"packages": ("prometheus",), "service": "prometheus", "protected_remove": False, "archive": None},
    "grafana": {"packages": ("grafana",), "service": "grafana-server", "protected_remove": False, "archive": "grafana"},
    "git": {"packages": ("git",), "service": None, "protected_remove": False, "archive": None},
    "curl": {"packages": ("curl",), "service": None, "protected_remove": False, "archive": None},
    "wget": {"packages": ("wget",), "service": None, "protected_remove": False, "archive": None},
    "htop": {"packages": ("htop",), "service": None, "protected_remove": False, "archive": None},
    "jq": {"packages": ("jq",), "service": None, "protected_remove": False, "archive": None},
    "tmux": {"packages": ("tmux",), "service": None, "protected_remove": False, "archive": None},
    "unzip": {"packages": ("unzip",), "service": None, "protected_remove": False, "archive": None},
    "fail2ban": {"packages": ("fail2ban",), "service": "fail2ban", "protected_remove": False, "archive": None},
    "certbot": {"packages": ("certbot",), "service": None, "protected_remove": False, "archive": None},
}

PACKAGE_ACTIONS = frozenset({"install", "remove", "update"})
SERVICE_ACTIONS = frozenset({"restart", "enable", "disable"})
PROTECTED_UNITS = frozenset({
    "ssh.service", "sshd.service", "systemd-journald.service", "systemd-logind.service",
    "dbus.service", "systemd-networkd.service", "systemd-resolved.service", "polkit.service",
})
PROTECTED_SERVICE_ACTIONS = frozenset({"disable"})


def normalize_unit(unit: str) -> str:
    name = (unit or "").strip()
    if not name or "/" in name or "\\" in name or ".." in name or "\x00" in name or name.startswith("-"):
        raise ValueError("Invalid unit name")
    if not name.endswith(".service"):
        name += ".service"
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:@._-")
    if len(name) > 128 or any(char not in allowed for char in name):
        raise ValueError("Invalid unit name")
    return name
