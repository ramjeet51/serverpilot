"""Allowlisted software and systemd operations. Names here are the only ones the API will accept."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SoftwareSpec:
    id: str
    name: str
    description: str
    packages: tuple[str, ...]
    service: str | None
    protected_remove: bool = False
    # Named extra-archive procedure inside the privileged helper. Never a caller-supplied URL.
    archive: str | None = None
    # Other catalogue ids that must be installed with this one. Already-installed items are skipped.
    requires: tuple[str, ...] = ()


CATALOGUE: dict[str, SoftwareSpec] = {
    "nginx": SoftwareSpec("nginx", "Nginx", "HTTP server and reverse proxy.", ("nginx",), "nginx"),
    "docker-engine": SoftwareSpec(
        "docker-engine", "Docker Engine",
        "Container runtime. Detects Docker CE (docker-ce) and the Ubuntu docker.io package.",
        ("docker-ce", "docker.io"), "docker"),
    "docker-compose": SoftwareSpec(
        "docker-compose", "Docker Compose",
        "Compose plugin. Detects docker-compose-plugin and docker-compose-v2. Installs Docker Engine when it is missing.",
        ("docker-compose-plugin", "docker-compose-v2"), None, requires=("docker-engine",)),
    "java": SoftwareSpec(
        "java", "Java",
        "Java runtime. Installed with Jenkins when the server does not already have Java.",
        ("default-jre-headless",), None),
    "jenkins": SoftwareSpec(
        "jenkins", "Jenkins",
        "Automation server. Installs Java when it is missing, then adds the official Jenkins stable archive.",
        ("jenkins",), "jenkins", archive="jenkins", requires=("java",)),
    "mysql": SoftwareSpec("mysql", "MySQL", "MySQL database server.", ("mysql-server",), "mysql"),
    "postgresql": SoftwareSpec("postgresql", "PostgreSQL", "PostgreSQL database server.", ("postgresql",), "postgresql"),
    "redis": SoftwareSpec("redis", "Redis", "In-memory data store.", ("redis-server",), "redis-server"),
    "nodejs": SoftwareSpec("nodejs", "Node.js", "Node.js from the Ubuntu archive.", ("nodejs",), None),
    "python": SoftwareSpec(
        "python", "Python", "Python 3, already part of Ubuntu. It cannot be removed.",
        ("python3",), None, protected_remove=True),
    "php": SoftwareSpec("php", "PHP", "PHP command line and common runtime.", ("php-cli",), None),
    "prometheus": SoftwareSpec("prometheus", "Prometheus", "Metrics server.", ("prometheus",), "prometheus"),
    "grafana": SoftwareSpec(
        "grafana", "Grafana",
        "Dashboards. The helper adds the official Grafana archive, then installs the package.",
        ("grafana",), "grafana-server", archive="grafana"),
    "git": SoftwareSpec("git", "Git", "Version control client.", ("git",), None),
    "curl": SoftwareSpec("curl", "curl", "Transfer files over HTTP and other protocols.", ("curl",), None),
    "wget": SoftwareSpec("wget", "wget", "Download files from the network.", ("wget",), None),
    "htop": SoftwareSpec("htop", "htop", "Interactive process viewer.", ("htop",), None),
    "jq": SoftwareSpec("jq", "jq", "Read and reshape JSON on the command line.", ("jq",), None),
    "tmux": SoftwareSpec("tmux", "tmux", "Terminal sessions that stay open after you disconnect.", ("tmux",), None),
    "unzip": SoftwareSpec("unzip", "Unzip", "Extract zip archives.", ("unzip",), None),
    "fail2ban": SoftwareSpec("fail2ban", "Fail2ban", "Block hosts that fail login too often.", ("fail2ban",), "fail2ban"),
    "certbot": SoftwareSpec("certbot", "Certbot", "Issue and renew TLS certificates.", ("certbot",), None),
}

CATEGORIES: dict[str, str] = {
    "nginx": "Web", "php": "Web",
    "python": "Runtimes", "nodejs": "Runtimes", "java": "Runtimes",
    "docker-engine": "Containers", "docker-compose": "Containers",
    "mysql": "Databases", "postgresql": "Databases", "redis": "Databases",
    "prometheus": "Observability", "grafana": "Observability",
    "jenkins": "Automation",
    "git": "Tools", "curl": "Tools", "wget": "Tools", "htop": "Tools", "jq": "Tools",
    "tmux": "Tools", "unzip": "Tools", "fail2ban": "Tools", "certbot": "Tools",
}

PACKAGE_NAME = r"^[a-z0-9][a-z0-9+.-]{1,60}$"
_BLOCKED_EXACT = frozenset({
    "apt", "sudo", "bash", "dash", "systemd", "dpkg", "python3", "openssh-server", "openssh-client",
    "passwd", "login", "mount", "util-linux",
})
_BLOCKED_PREFIXES = ("linux-", "linux-image", "linux-headers", "grub", "systemd", "shim-", "ubuntu-", "kernel")


def category_of(software_id: str) -> str:
    return CATEGORIES.get(software_id, "Tools")


def validate_archive_package(name: str) -> str:
    package = name.strip().lower()
    if not re.fullmatch(PACKAGE_NAME, package):
        raise ValueError("Package name is not valid")
    if package in _BLOCKED_EXACT or any(package.startswith(prefix) for prefix in _BLOCKED_PREFIXES):
        raise ValueError("That package is protected and cannot be installed from the library")
    return package

PACKAGE_ACTIONS = frozenset({"install", "remove", "update"})
SERVICE_ACTIONS = frozenset({"restart", "enable", "disable"})

# Stopping or disabling these cuts off the host or the agent tunnel.
PROTECTED_UNITS = frozenset({
    "ssh.service", "sshd.service", "systemd-journald.service", "systemd-logind.service",
    "dbus.service", "systemd-networkd.service", "systemd-resolved.service", "polkit.service",
})
PROTECTED_SERVICE_ACTIONS = frozenset({"disable"})

SUGGESTED_UNITS = (
    "nginx.service", "docker.service", "ssh.service", "mysql.service", "postgresql.service",
    "redis-server.service", "jenkins.service", "cron.service", "fail2ban.service",
)


def software_or_none(software_id: str) -> SoftwareSpec | None:
    return CATALOGUE.get(software_id)


def normalize_unit(unit: str) -> str:
    name = unit.strip()
    if not name or "/" in name or "\\" in name or ".." in name or "\x00" in name or name.startswith("-"):
        raise ValueError("Invalid unit name")
    if not name.endswith(".service"):
        name += ".service"
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:@._-")
    if len(name) > 128 or any(char not in allowed for char in name):
        raise ValueError("Invalid unit name")
    return name
