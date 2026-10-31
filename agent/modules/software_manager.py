"""Read package state without root. Changes go through the privileged helper."""

import re
import subprocess

from modules.catalogue import CATALOGUE
from modules.helper_client import run_helper


def _query(package: str) -> str | None:
    try:
        process = subprocess.run(["dpkg-query", "-W", "-f", "${Version}", package],
                                 capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if process.returncode != 0:
        return None
    version = process.stdout.strip()
    return version or None


def _candidate(package: str) -> str | None:
    try:
        process = subprocess.run(["apt-cache", "policy", package], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in process.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("Candidate:"):
            value = stripped.split(":", 1)[1].strip()
            return None if value in ("", "(none)") else value
    return None


def _display(version: str | None) -> str | None:
    if version and version[:1].isdigit() and ":" in version:
        return version.split(":", 1)[1]
    return version


def _present(spec: dict) -> tuple[str, str] | None:
    for package in spec.get("detect", spec["packages"]):
        version = _query(package)
        if version:
            return package, version
    return None


def inspect() -> dict:
    packages = []
    for software_id, spec in CATALOGUE.items():
        found = _present(spec)
        install_name = spec["packages"][0]
        candidate_name = found[0] if found else install_name
        packages.append({
            "id": software_id,
            "installed": found is not None,
            "version": _display(found[1]) if found else None,
            "candidate": _display(_candidate(candidate_name)),
            "package": found[0] if found else None,
        })
    return {"packages": packages, "exit_code": 0}


def versions(software_id: str) -> dict:
    spec = CATALOGUE.get(software_id)
    if spec is None:
        raise ValueError("Unknown software")
    found: list[str] = []
    for package in spec["packages"]:
        try:
            process = subprocess.run(["apt-cache", "madison", package], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            continue
        for line in process.stdout.splitlines():
            parts = [part.strip() for part in line.split("|")]
            if len(parts) >= 2 and parts[1] and parts[1] not in found:
                found.append(parts[1])
    return {"software_id": software_id, "versions": found, "exit_code": 0}


def _helper_recognizes(token: str) -> bool:
    for path in ("/opt/serverpilot-agent/modules/catalogue.py", "/opt/serverpilot-agent/modules/helper_ops.py"):
        try:
            if token in open(path, encoding="utf-8").read():
                return True
        except OSError:
            continue
    return False


_PACKAGE_NAME = re.compile(r"^[a-z0-9][a-z0-9+.-]{1,60}$")
_SEARCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 +._-]{0,40}$")
_BLOCKED_EXACT = {"apt", "sudo", "bash", "dash", "systemd", "dpkg", "python3", "openssh-server", "openssh-client", "passwd", "login", "mount", "util-linux"}
_BLOCKED_PREFIXES = ("linux-", "grub", "systemd", "shim-", "ubuntu-", "kernel")


def _allowed_package(name: str) -> str:
    package = name.strip().lower()
    if not _PACKAGE_NAME.fullmatch(package):
        raise ValueError("Package name is not valid")
    if package in _BLOCKED_EXACT or any(package.startswith(prefix) for prefix in _BLOCKED_PREFIXES):
        raise ValueError("That package is protected and cannot be installed from the library")
    return package


def library_search(query: str) -> dict:
    text = query.strip()
    if not _SEARCH.fullmatch(text):
        raise ValueError("Search text is not valid")
    try:
        process = subprocess.run(["apt-cache", "search", "--names-only", text], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Package search is not available on this server") from exc
    if process.returncode != 0:
        process = subprocess.run(["apt-cache", "search", text], capture_output=True, text=True, timeout=30)
    items = []
    for line in process.stdout.splitlines():
        if " - " not in line:
            continue
        name, description = line.split(" - ", 1)
        name = name.strip()
        if not _PACKAGE_NAME.fullmatch(name):
            continue
        version = _query(name)
        items.append({
            "name": name,
            "description": description.strip()[:180],
            "installed": version is not None,
            "version": _display(version),
        })
        if len(items) >= 30:
            break
    return {"packages": items, "exit_code": 0}


def install_named(package: str, on_log, timeout: int = 600) -> dict:
    name = _allowed_package(package)
    try:
        shown = subprocess.run(["apt-cache", "show", name], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Could not read the package archive") from exc
    if shown.returncode != 0:
        raise ValueError("That package is not in the archive on this server")
    if not _helper_recognizes("software.archive"):
        raise ValueError("Run sudo bash ~/serverpilot-agent/install-helper.sh once so archive installs are allowed, then try again.")
    return run_helper({"op": "software.archive", "package": name}, timeout, on_log)


def apply(action: str, software_id: str, version: str | None, on_log, timeout: int = 600) -> dict:
    spec = CATALOGUE.get(software_id)
    if spec is None:
        raise ValueError("Unknown software")
    if not _helper_recognizes(f'"{software_id}"'):
        raise ValueError("Run sudo bash ~/serverpilot-agent/install-helper.sh once so this library entry can be installed, then try again.")
    if action != "remove" and spec.get("requires") and not _helper_recognizes("_requirement_packages"):
        raise ValueError("Run sudo bash ~/serverpilot-agent/install-helper.sh once so required software is installed with this package, then try again.")
    found = _present(spec)
    if action in ("update", "remove") and found and found[0] not in spec["packages"] and not _helper_recognizes(found[0]):
        raise ValueError(
            f"{software_id} is installed as {found[0]}, not {spec['packages'][0]}. "
            "Run sudo bash ~/serverpilot-agent/install-helper.sh once before update or remove."
        )
    return run_helper({
        "op": "software.apply",
        "action": action,
        "software_id": software_id,
        "version": version,
        "package": found[0] if found else None,
    }, timeout, on_log)
