"""Start / stop / status for the external Threat Intelligence Engine process.

The Console toggle in ``tie_engine_mode`` only controls scrape forwarding.
This module owns the actual uvicorn process for the TIE project.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from config import PROJECT_ROOT

logger = logging.getLogger("tie_process")

_STATE_PATH = PROJECT_ROOT / "data" / "tie_engine_process.json"
_LOG_PATH = PROJECT_ROOT / "data" / "tie_engine_process.log"
_LOCK = threading.Lock()

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tie_base_url() -> str:
    return (
        os.getenv("TIE_API_URL")
        or os.getenv("THREAT_INTELLIGENCE_ENGINE_URL")
        or f"http://{_DEFAULT_HOST}:{_DEFAULT_PORT}"
    ).rstrip("/")


def _tie_port() -> int:
    raw = (os.getenv("TIE_ENGINE_PORT") or "").strip()
    if raw.isdigit():
        return int(raw)
    try:
        from urllib.parse import urlparse

        port = urlparse(_tie_base_url()).port
        if port:
            return int(port)
    except Exception:
        pass
    return _DEFAULT_PORT


def resolve_tie_engine_cwd() -> Path | None:
    """Locate the external TIE project directory."""
    candidates: list[Path] = []
    env = (os.getenv("TIE_ENGINE_CWD") or "").strip()
    if env:
        candidates.append(Path(env).expanduser())
    home = Path.home()
    candidates.extend(
        [
            home / "threat translation engine",
            home / "threat-translation-engine",
            home / "Threat Intelligence Engine",
            PROJECT_ROOT.parent / "threat translation engine",
            PROJECT_ROOT.parent / "threat-translation-engine",
        ]
    )
    for path in candidates:
        try:
            if path.is_dir() and (path / "app" / "main.py").is_file():
                return path.resolve()
        except OSError:
            continue
    return None


def _python_for_cwd(cwd: Path) -> Path:
    win = cwd / ".venv" / "Scripts" / "python.exe"
    unix = cwd / ".venv" / "bin" / "python"
    if win.is_file():
        return win
    if unix.is_file():
        return unix
    return Path(sys.executable)


def resolve_tie_engine_command(cwd: Path) -> list[str]:
    """Build argv used to launch TIE (override with TIE_ENGINE_CMD)."""
    override = (os.getenv("TIE_ENGINE_CMD") or "").strip()
    if override:
        # Simple Windows/Unix split that respects quoted segments.
        return _split_cmd(override)

    python = _python_for_cwd(cwd)
    host = (os.getenv("TIE_ENGINE_HOST") or _DEFAULT_HOST).strip() or _DEFAULT_HOST
    port = str(_tie_port())
    return [
        str(python),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        port,
    ]


def _split_cmd(raw: str) -> list[str]:
    try:
        import shlex

        return shlex.split(raw, posix=os.name != "nt")
    except ValueError:
        return raw.split()


def _read_state() -> dict[str, Any]:
    if not _STATE_PATH.is_file():
        return {}
    try:
        data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("tie_process_state_read_failed")
        return {}


def _write_state(payload: dict[str, Any]) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _clear_state() -> None:
    try:
        if _STATE_PATH.is_file():
            _STATE_PATH.unlink()
    except OSError:
        pass


def _pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        if os.name == "nt":
            # OpenProcess-style check via tasklist is slow; use os.kill(0) is not on Windows.
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            out = (result.stdout or "").strip()
            return str(pid) in out and "No tasks" not in out
        os.kill(pid, 0)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _pids_on_port(port: int) -> list[int]:
    pids: list[int] = []
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            needle = f":{port}"
            for line in (result.stdout or "").splitlines():
                if needle not in line or "LISTENING" not in line.upper():
                    continue
                parts = line.split()
                if not parts:
                    continue
                try:
                    pid = int(parts[-1])
                except ValueError:
                    continue
                if pid > 0:
                    pids.append(pid)
        else:
            result = subprocess.run(
                ["lsof", "-ti", f"tcp:{port}"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            for part in (result.stdout or "").split():
                try:
                    pids.append(int(part))
                except ValueError:
                    continue
    except Exception:
        logger.exception("tie_process_port_lookup_failed port=%s", port)
    return sorted(set(pids))


def _probe_healthy(timeout: float = 2.0) -> bool:
    url = f"{_tie_base_url()}/api/v1/tie/health"
    try:
        req = Request(url, headers={"Accept": "application/json"}, method="GET")
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — local TIE only
            return 200 <= getattr(resp, "status", 200) < 300
    except Exception:
        # Fallback: root identity
        try:
            req = Request(_tie_base_url() + "/", headers={"Accept": "application/json"}, method="GET")
            with urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return 200 <= getattr(resp, "status", 200) < 300
        except (URLError, OSError, TimeoutError, ValueError):
            return False


def _kill_pid(pid: int) -> None:
    if pid <= 0:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        else:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except (OSError, AttributeError):
                os.kill(pid, signal.SIGTERM)
            time.sleep(0.4)
            if _pid_alive(pid):
                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                except (OSError, AttributeError):
                    os.kill(pid, signal.SIGKILL)
    except Exception:
        logger.exception("tie_process_kill_failed pid=%s", pid)


def get_tie_process_status() -> dict[str, Any]:
    """Return process + health status for the dashboard."""
    state = _read_state()
    pid = state.get("pid")
    try:
        pid_i = int(pid) if pid is not None else None
    except (TypeError, ValueError):
        pid_i = None

    managed_alive = _pid_alive(pid_i)
    port = _tie_port()
    port_pids = _pids_on_port(port)
    healthy = _probe_healthy()
    running = managed_alive or bool(port_pids) or healthy
    cwd = resolve_tie_engine_cwd()

    return {
        "running": running,
        "managed": managed_alive,
        "pid": pid_i if managed_alive else (port_pids[0] if port_pids else None),
        "port": port,
        "url": _tie_base_url(),
        "healthy": healthy,
        "cwd": str(cwd) if cwd else None,
        "configured": cwd is not None,
        "started_at": state.get("started_at"),
        "command": state.get("command"),
        "log_path": str(_LOG_PATH),
    }


def start_tie_process(*, wait_seconds: float = 8.0) -> dict[str, Any]:
    """Launch the TIE uvicorn process if it is not already running."""
    with _LOCK:
        current = get_tie_process_status()
        if current.get("healthy") or current.get("running"):
            return {
                **current,
                "ok": True,
                "started": False,
                "detail": "already_running",
            }

        cwd = resolve_tie_engine_cwd()
        if cwd is None:
            return {
                "ok": False,
                "started": False,
                "running": False,
                "healthy": False,
                "configured": False,
                "error": (
                    "TIE project not found. Set TIE_ENGINE_CWD to the path of "
                    "'threat translation engine' (folder containing app/main.py)."
                ),
                "url": _tie_base_url(),
                "port": _tie_port(),
            }

        cmd = resolve_tie_engine_command(cwd)
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        log_fh = open(_LOG_PATH, "a", encoding="utf-8")  # noqa: SIM115 — kept open for child
        try:
            log_fh.write(f"\n--- start {_now_iso()} ---\n")
            log_fh.write(f"cwd={cwd}\ncmd={' '.join(cmd)}\n")
            log_fh.flush()

            popen_kwargs: dict[str, Any] = {
                "cwd": str(cwd),
                "stdout": log_fh,
                "stderr": subprocess.STDOUT,
                "stdin": subprocess.DEVNULL,
            }
            if os.name == "nt":
                popen_kwargs["creationflags"] = (
                    subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
                )
            else:
                popen_kwargs["start_new_session"] = True

            proc = subprocess.Popen(cmd, **popen_kwargs)  # noqa: S603
        except Exception as exc:
            log_fh.close()
            logger.exception("tie_process_start_failed")
            return {
                "ok": False,
                "started": False,
                "running": False,
                "healthy": False,
                "configured": True,
                "cwd": str(cwd),
                "error": str(exc),
                "url": _tie_base_url(),
                "port": _tie_port(),
            }

        started_at = _now_iso()
        _write_state(
            {
                "pid": proc.pid,
                "cwd": str(cwd),
                "command": cmd,
                "started_at": started_at,
                "port": _tie_port(),
            }
        )
        # Don't close log_fh — child inherits it on Windows.

        deadline = time.time() + max(1.0, wait_seconds)
        healthy = False
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            if _probe_healthy(timeout=1.5):
                healthy = True
                break
            time.sleep(0.4)

        status = get_tie_process_status()
        if proc.poll() is not None and not healthy:
            _clear_state()
            return {
                **status,
                "ok": False,
                "started": False,
                "error": (
                    f"TIE process exited early (code {proc.returncode}). "
                    f"Check {_LOG_PATH}."
                ),
            }

        return {
            **status,
            "ok": True,
            "started": True,
            "healthy": healthy or status.get("healthy"),
            "detail": "started" if healthy or status.get("running") else "starting",
        }


def stop_tie_process() -> dict[str, Any]:
    """Kill the managed TIE process and anything still listening on the TIE port."""
    with _LOCK:
        state = _read_state()
        pid = state.get("pid")
        try:
            pid_i = int(pid) if pid is not None else None
        except (TypeError, ValueError):
            pid_i = None

        killed: list[int] = []
        if pid_i and _pid_alive(pid_i):
            _kill_pid(pid_i)
            killed.append(pid_i)

        for port_pid in _pids_on_port(_tie_port()):
            if port_pid not in killed:
                _kill_pid(port_pid)
                killed.append(port_pid)

        _clear_state()
        time.sleep(0.3)
        status = get_tie_process_status()
        return {
            **status,
            "ok": True,
            "stopped": True,
            "killed_pids": killed,
            "running": bool(status.get("running")),
        }
