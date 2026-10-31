"""Run the root helper. The agent never builds a shell command."""

import json
import os
import signal
import subprocess
import threading
from pathlib import Path

from modules.sanitize import sanitize

HELPER = os.environ.get("AGENT_HELPER", "/opt/serverpilot-agent/serverpilot-helper")
_MISSING = (
    "Privileged helper is not installed. On this server run: "
    "sudo bash ~/serverpilot-agent/install-helper.sh"
)


class HelperError(Exception):
    def __init__(self, code: str, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


def run_helper(payload: dict, timeout: int, on_log) -> dict:
    helper = Path(HELPER)
    if not helper.is_file():
        raise HelperError("helper_missing", _MISSING)
    try:
        process = subprocess.Popen(
            ["sudo", "-n", "--", str(helper)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        )
    except OSError as exc:
        raise HelperError("helper_missing", f"Could not start the privileged helper: {exc.__class__.__name__}") from exc

    stdout_box: list[str] = []
    notes: list[str] = []

    def read_stdout() -> None:
        if process.stdout is not None:
            stdout_box.append(process.stdout.read())

    def read_stderr() -> None:
        if process.stderr is None:
            return
        for line in process.stderr:
            cleaned = sanitize(line)
            if cleaned:
                notes.append(cleaned)
                on_log(cleaned)

    out_thread = threading.Thread(target=read_stdout, daemon=True)
    err_thread = threading.Thread(target=read_stderr, daemon=True)
    out_thread.start()
    err_thread.start()
    assert process.stdin is not None
    process.stdin.write(json.dumps(payload))
    process.stdin.close()
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
        raise HelperError("timeout", f"Operation timed out after {timeout}s", None)
    out_thread.join(timeout=2)
    err_thread.join(timeout=2)
    raw = (stdout_box[0] if stdout_box else "").strip()
    joined = " ".join(notes).lower()
    if "password is required" in joined or "not in the sudoers" in joined or "a terminal is required" in joined:
        raise HelperError("helper_missing", _MISSING, code)
    try:
        body = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        if code != 0:
            raise HelperError("helper_failed", "Privileged helper exited without a result", code)
        body = {}
    if not isinstance(body, dict):
        raise HelperError("helper_failed", "Privileged helper returned an unexpected result", code)
    if body.get("ok") is False:
        raise HelperError(str(body.get("error") or "operation_failed"), str(body.get("message") or "Operation failed"),
                          body.get("exit_code", code))
    if code != 0 and not body:
        raise HelperError("operation_failed", f"Privileged helper exited {code}", code)
    result = body.get("result") if isinstance(body.get("result"), dict) else {}
    result["exit_code"] = body.get("exit_code", code)
    return result
