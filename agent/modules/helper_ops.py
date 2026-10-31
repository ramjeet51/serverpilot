"""Root-only package and service operations.

This file is installed as /opt/serverpilot-agent/serverpilot-helper and is the only
command the agent user may run with sudo. It accepts one JSON object on stdin and
writes one JSON object on stdout. Progress goes to stderr. It does not run a shell.
"""

import fcntl
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.catalogue import (  # noqa: E402
    CATALOGUE, PACKAGE_ACTIONS, PROTECTED_SERVICE_ACTIONS, PROTECTED_UNITS, SERVICE_ACTIONS, normalize_unit,
)
from modules.sanitize import sanitize  # noqa: E402

_VERSION = re.compile(r"^[0-9][A-Za-z0-9.+:~_-]{0,80}$")
_LOCKS = ("/var/lib/dpkg/lock-frontend", "/var/lib/dpkg/lock", "/var/lib/apt/lists/lock")
_APT_ENV = {**os.environ, "DEBIAN_FRONTEND": "noninteractive", "NEEDRESTART_MODE": "a", "APT_LISTCHANGES_FRONTEND": "none"}


def log(message: str) -> None:
    print(sanitize(message), file=sys.stderr, flush=True)


def fail(code: str, message: str, exit_code: int | None = 1) -> None:
    json.dump({"ok": False, "error": code, "message": message, "exit_code": exit_code, "result": {}}, sys.stdout)
    raise SystemExit(0)


def apt_locked() -> bool:
    for path in _LOCKS:
        try:
            handle = os.open(path, os.O_RDWR)
        except (FileNotFoundError, PermissionError):
            continue
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(handle, fcntl.LOCK_UN)
        except BlockingIOError:
            return True
        finally:
            os.close(handle)
    return False


def run(command: list[str], timeout: int) -> tuple[int, str]:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=_APT_ENV)
    assert process.stdout is not None
    lines: list[str] = []
    try:
        for line in process.stdout:
            cleaned = sanitize(line)
            if cleaned:
                lines.append(cleaned)
                log(cleaned)
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        fail("timeout", f"Command timed out after {timeout}s")
    output = "\n".join(lines)
    if "Could not get lock" in output or "Unable to acquire the dpkg frontend lock" in output:
        fail("apt_locked", "APT or dpkg is locked by another process. Wait for it to finish, then retry.")
    return code, output


def _allowed_packages(spec: dict) -> tuple[str, ...]:
    names = tuple(spec.get("detect", ())) + tuple(spec["packages"])
    unique: list[str] = []
    for name in names:
        if name not in unique:
            unique.append(name)
    return tuple(unique)


def _choose_package(spec: dict, body: dict) -> str:
    allowed = _allowed_packages(spec)
    requested = body.get("package")
    if isinstance(requested, str) and requested in allowed and _installed_version(requested):
        return requested
    for package in spec.get("detect", spec["packages"]):
        if _installed_version(package):
            return package
    return spec["packages"][0]


def _requirement_packages(spec: dict, seen: set[str] | None = None) -> list[str]:
    """Packages for catalogue requirements that are not already installed."""
    seen = set() if seen is None else seen
    packages: list[str] = []
    for req_id in spec.get("requires") or ():
        if req_id in seen or req_id not in CATALOGUE:
            continue
        seen.add(req_id)
        req = CATALOGUE[req_id]
        packages.extend(_requirement_packages(req, seen))
        chosen = _choose_package(req, {})
        if _installed_version(chosen):
            continue
        if req.get("archive"):
            _ensure_archive(req["archive"])
        packages.append(req["packages"][0])
    return packages


def _known_versions(package: str) -> set[str]:
    process = subprocess.run(["apt-cache", "madison", package], capture_output=True, text=True, timeout=30, env=_APT_ENV)
    found = set()
    for line in process.stdout.splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 2 and parts[1]:
            found.add(parts[1])
    return found


def _dependencies(targets: list[str]) -> list[str]:
    code, output = run(["apt-get", "install", "-s", "-y", *targets], 90)
    if code != 0:
        return []
    names = []
    for line in output.splitlines():
        if line.startswith("Inst "):
            parts = line.split()
            if len(parts) > 1:
                names.append(parts[1])
    return names


def _installed_version(package: str) -> str | None:
    process = subprocess.run(["dpkg-query", "-W", "-f", "${Version}", package], capture_output=True, text=True, timeout=20)
    if process.returncode != 0:
        return None
    version = process.stdout.strip()
    return version or None


def _ensure_archive(name: str) -> None:
    if name == "jenkins":
        key = Path("/usr/share/keyrings/jenkins-keyring.asc")
        listing = Path("/etc/apt/sources.list.d/jenkins.list")
        if listing.exists():
            return
        log("Adding the Jenkins stable archive")
        key.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen("https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key", timeout=30) as response:
            key.write_bytes(response.read())
        os.chmod(key, 0o644)
        listing.write_text(
            "deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/\n")
        code, _ = run(["apt-get", "update"], 180)
        if code != 0:
            fail("archive_failed", "Could not update package lists after adding the Jenkins archive", code)
        return
    if name == "grafana":
        key = Path("/usr/share/keyrings/grafana.gpg")
        listing = Path("/etc/apt/sources.list.d/grafana.list")
        if listing.exists():
            return
        log("Adding the Grafana archive")
        key.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen("https://apt.grafana.com/gpg.key", timeout=30) as response:
            dearmor = subprocess.run(["gpg", "--dearmor"], input=response.read(), capture_output=True, timeout=20)
        if dearmor.returncode != 0:
            fail("archive_failed", "Could not read the Grafana signing key")
        key.write_bytes(dearmor.stdout)
        os.chmod(key, 0o644)
        listing.write_text("deb [signed-by=/usr/share/keyrings/grafana.gpg] https://apt.grafana.com stable main\n")
        code, _ = run(["apt-get", "update"], 180)
        if code != 0:
            fail("archive_failed", "Could not update package lists after adding the Grafana archive", code)


def apply_software(body: dict) -> dict:
    action = body.get("action")
    software_id = body.get("software_id")
    version = body.get("version") or None
    spec = CATALOGUE.get(software_id) if isinstance(software_id, str) else None
    if action not in PACKAGE_ACTIONS or spec is None:
        fail("invalid_request", "Unknown software or action")
    if action == "remove" and spec["protected_remove"]:
        fail("protected_package", f"{software_id} is protected and cannot be removed")
    package = _choose_package(spec, body)
    if version is not None:
        if action != "install" or not isinstance(version, str) or not _VERSION.match(version):
            fail("invalid_version", "Version is not a valid package version")
        if version not in _known_versions(package):
            fail("invalid_version", "That version is not published for this package")
    if apt_locked():
        fail("apt_locked", "APT or dpkg is locked by another process. Wait for it to finish, then retry.")
    if action == "install" and spec["archive"] and not _installed_version(package):
        _ensure_archive(spec["archive"])
    target = f"{package}={version}" if action == "install" and version else package
    extras = _requirement_packages(spec) if action != "remove" else []
    targets = [*extras, target]
    dependencies = _dependencies(targets) if action != "remove" else []
    if extras:
        log("Also installing required software: " + ", ".join(extras))
    if dependencies:
        log("Packages that will be installed or upgraded: " + ", ".join(dependencies))
    if action == "remove":
        command = ["apt-get", "remove", "-y", package]
    else:
        command = ["apt-get", "install", "-y", "--no-install-recommends",
                   "-o", "Dpkg::Lock::Timeout=15", "-o", "Dpkg::Options::=--force-confdef",
                   "-o", "Dpkg::Options::=--force-confold", *targets]
    code, _ = run(command, 600)
    if code != 0:
        fail("operation_failed", f"apt-get exited {code}", code)
    return {
        "software_id": software_id,
        "action": action,
        "version": _installed_version(package),
        "package": package,
        "dependencies": dependencies,
        "required_packages": extras,
        "exit_code": code,
    }


def apply_service(body: dict) -> dict:
    action = body.get("action")
    try:
        unit = normalize_unit(str(body.get("unit") or ""))
    except ValueError:
        fail("invalid_unit", "Invalid unit name")
    if action not in SERVICE_ACTIONS:
        fail("invalid_request", "Unknown service action")
    if unit in PROTECTED_UNITS and action in PROTECTED_SERVICE_ACTIONS:
        fail("protected_service", f"{unit} cannot be disabled from ServerPilot")
    code, _ = run(["systemctl", action, unit], 90)
    if code != 0:
        fail("operation_failed", f"systemctl {action} exited {code}", code)
    show = subprocess.run(
        ["systemctl", "show", unit, "-p", "ActiveState", "-p", "SubState", "-p", "UnitFileState", "--no-pager"],
        capture_output=True, text=True, timeout=20,
    )
    fields = {}
    for line in show.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    return {
        "unit": unit,
        "action": action,
        "active": fields.get("ActiveState", "unknown"),
        "sub": fields.get("SubState", "unknown"),
        "enabled": fields.get("UnitFileState", "unknown"),
        "exit_code": code,
    }


def apply_archive(body: dict) -> dict:
    import re
    package = str(body.get("package") or "").strip().lower()
    if not re.fullmatch(r"^[a-z0-9][a-z0-9+.-]{1,60}$", package):
        fail("invalid_request", "Package name is not valid")
    blocked = {"apt", "sudo", "bash", "dash", "systemd", "dpkg", "python3", "openssh-server", "openssh-client", "passwd", "login", "mount", "util-linux"}
    if package in blocked or package.startswith(("linux-", "grub", "systemd", "shim-", "ubuntu-", "kernel")):
        fail("protected_package", "That package is protected and cannot be installed from the library")
    shown = subprocess.run(["apt-cache", "show", package], capture_output=True, text=True, timeout=20)
    if shown.returncode != 0:
        fail("invalid_request", "That package is not in the archive on this server")
    if apt_locked():
        fail("apt_locked", "APT or dpkg is locked by another process. Wait for it to finish, then retry.")
    dependencies = _dependencies([package])
    if dependencies:
        log("Packages that will be installed or upgraded: " + ", ".join(dependencies))
    else:
        log(f"Installing {package} from the archive")
    code, _ = run(["apt-get", "install", "-y", "--no-install-recommends",
                   "-o", "Dpkg::Lock::Timeout=15", "-o", "Dpkg::Options::=--force-confdef",
                   "-o", "Dpkg::Options::=--force-confold", package], 600)
    if code != 0:
        fail("operation_failed", f"apt-get exited {code}", code)
    return {"package": package, "action": "install", "version": _installed_version(package), "exit_code": code}


def main() -> None:
    try:
        body = json.load(sys.stdin)
    except json.JSONDecodeError:
        fail("invalid_request", "Expected a JSON request")
    if not isinstance(body, dict):
        fail("invalid_request", "Expected a JSON object")
    operation = body.get("op")
    if operation == "software.archive":
        result = apply_archive(body)
    elif operation == "software.apply":
        result = apply_software(body)
    elif operation == "services.apply":
        result = apply_service(body)
    elif operation == "services.logs":
        try:
            unit = normalize_unit(str(body.get("unit") or ""))
        except ValueError:
            fail("invalid_unit", "Invalid unit name")
        code, output = run(["journalctl", "-u", unit, "-n", "100", "--no-pager", "-o", "short-iso"], 20)
        result = {"unit": unit, "lines": output.splitlines()[-100:], "exit_code": code}
    else:
        fail("invalid_request", "Unknown operation")
    json.dump({"ok": True, "error": None, "message": "", "exit_code": result.get("exit_code", 0), "result": result}, sys.stdout)


if __name__ == "__main__":
    main()
