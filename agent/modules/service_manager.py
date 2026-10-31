"""Read systemd state without root. Changes and journal access go through the privileged helper."""

import subprocess

from modules.catalogue import normalize_unit
from modules.helper_client import run_helper
from modules.sanitize import sanitize


def _run(command: list[str], timeout: int = 20) -> str:
    process = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if process.returncode != 0 and not process.stdout:
        raise RuntimeError(sanitize(process.stderr) or f"Command exited {process.returncode}")
    return process.stdout


def list_services() -> dict:
    units = _run(["systemctl", "list-units", "--type=service", "--all", "--plain", "--no-legend", "--no-pager"])
    files = _run(["systemctl", "list-unit-files", "--type=service", "--plain", "--no-legend", "--no-pager"])
    enabled: dict[str, str] = {}
    for line in files.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            enabled[parts[0]] = parts[1]
    services = []
    for line in units.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        try:
            unit = normalize_unit(parts[0])
        except ValueError:
            continue
        services.append({
            "unit": unit,
            "active": parts[2],
            "sub": parts[3],
            "enabled": enabled.get(unit, enabled.get(parts[0], "unknown")),
            "description": parts[4] if len(parts) > 4 else "",
        })
        if len(services) >= 400:
            break
    return {"services": services, "exit_code": 0}


def show(unit: str) -> dict:
    name = normalize_unit(unit)
    output = _run(["systemctl", "show", name, "-p", "Id", "-p", "Description", "-p", "ActiveState",
                   "-p", "SubState", "-p", "UnitFileState", "-p", "FragmentPath", "-p", "MainPID", "--no-pager"])
    fields: dict[str, str] = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    return {
        "unit": name,
        "description": fields.get("Description", ""),
        "active": fields.get("ActiveState", "unknown"),
        "sub": fields.get("SubState", "unknown"),
        "enabled": fields.get("UnitFileState", "unknown"),
        "fragment_path": fields.get("FragmentPath", ""),
        "main_pid": fields.get("MainPID", ""),
        "exit_code": 0,
    }


def logs(unit: str, on_log) -> dict:
    name = normalize_unit(unit)
    try:
        output = _run(["journalctl", "-u", name, "-n", "100", "--no-pager", "-o", "short-iso"], timeout=20)
        lines = [sanitize(line) for line in output.splitlines() if sanitize(line)]
    except (OSError, subprocess.TimeoutExpired, RuntimeError):
        body = run_helper({"op": "services.logs", "unit": name}, 30, on_log)
        lines = body.get("lines") or []
    return {"unit": name, "lines": lines[-100:], "exit_code": 0}


def apply(action: str, unit: str, on_log, timeout: int = 90) -> dict:
    return run_helper({"op": "services.apply", "action": action, "unit": normalize_unit(unit)}, timeout, on_log)
