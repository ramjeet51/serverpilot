#!/usr/bin/env python3
"""ServerPilot agent. Connects outbound, reports health, and runs allowlisted operations."""

import base64
import hashlib
import json
import os
import platform
import queue
import shutil
import socket
import ssl
import struct
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from modules.catalogue import PACKAGE_ACTIONS, SERVICE_ACTIONS
from modules.helper_client import HelperError
from modules.sanitize import sanitize
from modules import service_manager, software_manager

VERSION = "1.1.0"
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
ROOT = Path(__file__).resolve().parent
STATE_PATH = Path(os.environ.get("AGENT_STATE_DIRECTORY", ROOT / "state")) / "agent.json"
_cpu_sample: tuple[int, int] | None = None


def log(message: str) -> None:
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {message}", flush=True)


def _read_mem() -> tuple[int, int]:
    info: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            info[key] = int(value.strip().split()[0]) * 1024
    except OSError:
        return 0, 0
    total = info.get("MemTotal", 0)
    available = info.get("MemAvailable", 0)
    return total, max(total - available, 0)


def _cpu_percent() -> float:
    global _cpu_sample
    try:
        parts = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
        numbers = [int(part) for part in parts]
    except (OSError, ValueError, IndexError):
        return 0.0
    idle, total = numbers[3], sum(numbers)
    previous = _cpu_sample
    _cpu_sample = (idle, total)
    if previous is None or total <= previous[1]:
        return 0.0
    idle_delta = idle - previous[0]
    total_delta = total - previous[1]
    return round(max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100)), 1)


def _net() -> tuple[int, int]:
    rx = tx = 0
    try:
        lines = Path("/proc/net/dev").read_text().splitlines()[2:]
    except OSError:
        return 0, 0
    for line in lines:
        name, rest = line.split(":", 1)
        if name.strip() == "lo":
            continue
        columns = rest.split()
        rx += int(columns[0])
        tx += int(columns[8])
    return rx, tx


def _os_release() -> tuple[str | None, str | None]:
    name = version = None
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("NAME="):
                name = line.split("=", 1)[1].strip().strip('"')[:64]
            elif line.startswith("VERSION_ID="):
                version = line.split("=", 1)[1].strip().strip('"')[:64]
    except OSError:
        pass
    return name, version


def collect() -> dict:
    total, used = _read_mem()
    usage = shutil.disk_usage("/")
    os_name, os_version = _os_release()
    try:
        load = [float(part) for part in Path("/proc/loadavg").read_text().split()[:3]]
    except (OSError, ValueError):
        load = [None, None, None]
    try:
        processes = sum(1 for entry in Path("/proc").iterdir() if entry.name.isdigit())
    except OSError:
        processes = None
    uname = platform.uname()
    memory_percent = round(used / total * 100, 1) if total else 0.0
    return {
        "hostname": uname.node[:255],
        "os_name": os_name,
        "os_version": os_version,
        "kernel_version": uname.release[:128],
        "cpu_cores": os.cpu_count(),
        "cpu_percent": _cpu_percent(),
        "memory_total_bytes": total,
        "memory_used_bytes": used,
        "memory_percent": memory_percent,
        "disk_total_bytes": usage.total,
        "disk_percent": round(usage.used / usage.total * 100, 1) if usage.total else 0.0,
        "net_rx_bytes": _net()[0],
        "net_tx_bytes": _net()[1],
        "load_1": load[0],
        "load_5": load[1],
        "load_15": load[2],
        "process_count": processes,
        "version": VERSION,
    }


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {
        "server_url": os.environ.get("AGENT_SERVER_URL", ""),
        "agent_token": "",
        "registration_token": os.environ.get("AGENT_REGISTRATION_TOKEN", ""),
    }


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps({k: state.get(k, "") for k in ("server_url", "agent_token")}))
    os.chmod(temporary, 0o600)
    temporary.replace(STATE_PATH)


class SocketWebSocket:
    def __init__(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("ws", "wss") or not parsed.hostname:
            raise ValueError(f"Unsupported agent URL: {url}")
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        raw = socket.create_connection((parsed.hostname, port), timeout=10)
        if parsed.scheme == "wss":
            context = ssl.create_default_context()
            raw = context.wrap_socket(raw, server_hostname=parsed.hostname)
        self.sock = raw
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        key = base64.b64encode(os.urandom(16)).decode()
        host = parsed.hostname if parsed.port is None else f"{parsed.hostname}:{port}"
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Gateway closed during handshake")
            response += chunk
            if len(response) > 8192:
                raise ConnectionError("Handshake too large")
        head = response.split(b"\r\n\r\n", 1)[0].decode("latin1")
        expected = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
        if "101" not in head.split("\r\n", 1)[0] or expected not in head:
            raise ConnectionError("Gateway rejected the WebSocket handshake")
        self.buffer = response.split(b"\r\n\r\n", 1)[1]

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def send_json(self, payload: dict) -> None:
        self._send(0x1, json.dumps(payload).encode())

    def recv_json(self, timeout: float) -> dict:
        self.sock.settimeout(timeout)
        while True:
            opcode, data = self._recv()
            if opcode == 0x1:
                return json.loads(data.decode())
            if opcode == 0x8:
                raise ConnectionError("Gateway closed the connection")
            if opcode == 0x9:
                self._send(0xA, data)

    def _send(self, opcode: int, payload: bytes) -> None:
        mask = os.urandom(4)
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header += struct.pack("!H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack("!Q", length)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + mask + masked)

    def _read(self, count: int) -> bytes:
        while len(self.buffer) < count:
            chunk = self.sock.recv(max(4096, count - len(self.buffer)))
            if not chunk:
                raise ConnectionError("Connection closed")
            self.buffer += chunk
        data, self.buffer = self.buffer[:count], self.buffer[count:]
        return data

    def _recv(self) -> tuple[int, bytes]:
        first, second = self._read(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read(8))[0]
        if length > 1_000_000:
            raise ConnectionError("Frame too large")
        return opcode, self._read(length)


def _dispatch(action: str, params: dict, on_log) -> dict:
    if action == "software.inspect":
        return software_manager.inspect()
    if action == "software.versions":
        return software_manager.versions(str(params.get("software_id") or ""))
    if action == "software.library":
        return software_manager.library_search(str(params.get("query") or ""))
    if action == "software.apply":
        if params.get("source") == "archive":
            return software_manager.install_named(str(params.get("package") or ""), on_log)
        operation = str(params.get("action") or "")
        if operation not in PACKAGE_ACTIONS:
            raise ValueError("Unknown package action")
        version = params.get("version") or None
        return software_manager.apply(operation, str(params.get("software_id") or ""), version, on_log)
    if action == "services.list":
        return service_manager.list_services()
    if action == "services.show":
        return service_manager.show(str(params.get("unit") or ""))
    if action == "services.logs":
        return service_manager.logs(str(params.get("unit") or ""), on_log)
    if action == "services.apply":
        operation = str(params.get("action") or "")
        if operation not in SERVICE_ACTIONS:
            raise ValueError("Unknown service action")
        return service_manager.apply(operation, str(params.get("unit") or ""), on_log)
    raise ValueError("Unknown action")


def _run_command(message: dict, outbound: queue.Queue, busy: threading.Event) -> None:
    request_id = message.get("id")
    action = str(message.get("action") or "")
    params = message.get("params") if isinstance(message.get("params"), dict) else {}

    def finish(**payload: object) -> None:
        outbound.put({"type": "command_result", "id": request_id, **payload})
        busy.clear()

    def on_log(line: str) -> None:
        cleaned = sanitize(line)
        if cleaned:
            outbound.put({"type": "command_log", "id": request_id, "line": cleaned})

    try:
        result = _dispatch(action, params, on_log)
        finish(ok=True, exit_code=result.get("exit_code", 0), result=result, error=None, message="")
    except HelperError as exc:
        finish(ok=False, exit_code=exc.exit_code, result={}, error=exc.code, message=str(exc))
    except (ValueError, RuntimeError, OSError) as exc:
        finish(ok=False, exit_code=1, result={}, error="operation_failed", message=str(exc)[:500])
    except Exception as exc:  # noqa: BLE001
        finish(ok=False, exit_code=1, result={}, error="operation_failed", message=exc.__class__.__name__)


def run_once(state: dict) -> None:
    url = state.get("server_url") or ""
    if not url:
        raise RuntimeError("AGENT_SERVER_URL is not set")
    socket_client = SocketWebSocket(url)
    try:
        report = collect()
        if state.get("agent_token"):
            socket_client.send_json({"type": "hello", "token": state["agent_token"], "report": report})
        elif state.get("registration_token"):
            socket_client.send_json({"type": "register", "token": state["registration_token"], "report": report})
        else:
            raise RuntimeError("No registration token or saved agent token")
        reply = socket_client.recv_json(30)
        if reply.get("type") == "registered":
            state["agent_token"] = reply["agent_token"]
            state.pop("registration_token", None)
            os.environ.pop("AGENT_REGISTRATION_TOKEN", None)
            save_state(state)
            log("Registered with the management server")
        elif reply.get("type") != "ready":
            raise RuntimeError("Unexpected gateway reply")
        else:
            log("Connected")
        interval = max(5, int(reply.get("heartbeat_interval", 15)))
        outbound: queue.Queue = queue.Queue()
        busy = threading.Event()
        next_beat = time.monotonic() + interval
        while True:
            wait = max(0.2, min(1.0, next_beat - time.monotonic()))
            try:
                incoming = socket_client.recv_json(wait)
            except (TimeoutError, socket.timeout):
                incoming = None
            if incoming and incoming.get("type") == "command":
                if busy.is_set():
                    socket_client.send_json({
                        "type": "command_result", "id": incoming.get("id"), "ok": False,
                        "error": "busy", "message": "Another operation is already running on this agent",
                        "exit_code": None, "result": {},
                    })
                else:
                    busy.set()
                    threading.Thread(target=_run_command, args=(incoming, outbound, busy), daemon=True).start()
            elif incoming and incoming.get("type") not in ("ok",):
                raise RuntimeError("Unexpected gateway message")
            while True:
                try:
                    socket_client.send_json(outbound.get_nowait())
                except queue.Empty:
                    break
            if time.monotonic() >= next_beat:
                socket_client.send_json({"type": "heartbeat", "token": state["agent_token"], "report": collect()})
                next_beat = time.monotonic() + interval
    finally:
        socket_client.close()


def main() -> None:
    delay = 2
    while True:
        state = load_state()
        try:
            run_once(state)
            delay = 2
        except Exception as exc:
            log(f"Disconnected: {exc.__class__.__name__}: {exc}")
            time.sleep(delay)
            delay = min(delay * 2, 60)


if __name__ == "__main__":
    main()
