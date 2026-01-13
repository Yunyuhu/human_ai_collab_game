from typing import Any, Dict, Optional
from pathlib import Path
import subprocess
import sys
import json
import time
import threading

# HTTP client
try:
    import requests
except Exception:
    requests = None

# WebSocket client (optional)
try:
    import asyncio
    import websockets
except Exception:
    websockets = None
    asyncio = None

API_BASE = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 1.5
_backend_process: Optional[subprocess.Popen] = None
_backend_start_attempted = False
_backend_schema_checked = False
_backend_schema_ok = False


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_backend_running() -> None:
    global _backend_process, _backend_start_attempted
    if _backend_start_attempted:
        return
    _backend_start_attempted = True
    try:
        _backend_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=str(_project_root()),
        )
    except Exception as exc:
        print(f"[api] Failed to start backend: {exc}")


def _check_backend_schema() -> bool:
    global _backend_schema_checked, _backend_schema_ok
    if _backend_schema_checked and _backend_schema_ok:
        return True
    for attempt in range(2):
        try:
            resp = requests.get(f"{API_BASE}/health", timeout=DEFAULT_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("schema_version") == "session_v2":
                    _backend_schema_checked = True
                    _backend_schema_ok = True
                    return True
                _backend_schema_ok = False
                print("[api] Backend schema mismatch; please stop old server and restart.")
                return False
        except Exception:
            if attempt == 0:
                _ensure_backend_running()
                time.sleep(0.5)
                continue
    _backend_schema_ok = False
    print("[api] Backend not reachable; please start backend.")
    return False


def has_speed_session(user_id: int, speed_condition: str) -> bool:
    if requests is None:
        return False
    if not _check_backend_schema():
        return False
    try:
        resp = requests.get(
            f"{API_BASE}/user_speed_status",
            params={"user_id": user_id, "speed_condition": speed_condition},
            timeout=DEFAULT_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            return bool(data.get("exists"))
    except Exception as exc:
        print(f"[api] GET {API_BASE}/user_speed_status failed: {exc}")
    return False


def has_any_speed_session(user_id: int) -> bool:
    return has_speed_session(user_id, "A") or has_speed_session(user_id, "B")


def _post(path: str, payload: Dict[str, Any]) -> None:
    url = f"{API_BASE}{path}"
    try:
        if requests is None:
            print(f"[api] requests not available — would POST to {url} with {payload}")
            return
        if not _check_backend_schema():
            return
        resp = requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
        if resp.status_code != 200:
            print(f"[api] POST {url} returned {resp.status_code}: {resp.text}")
    except Exception as exc:
        _ensure_backend_running()
        try:
            time.sleep(0.5)
            if not _check_backend_schema():
                return
            resp = requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
            if resp.status_code != 200:
                print(f"[api] POST {url} returned {resp.status_code}: {resp.text}")
            return
        except Exception:
            pass
        print(f"[api] POST {url} failed: {exc}")


def start_experiment(
    user_id: int,
    condition: int,
    total_rounds: int,
    notes: str,
    exp_start_time: str,
    session_id: Optional[str] = None,
    speed_condition: Optional[str] = None,
) -> None:
    _post(
        "/start_experiment",
        {
            "user_id": user_id,
            "condition": condition,
            "total_rounds": total_rounds,
            "notes": notes,
            "exp_start_time": exp_start_time,
            "session_id": session_id,
            "speed_condition": speed_condition,
        },
    )


def end_experiment(
    user_id: int,
    condition: int,
    exp_start_time: str,
    exp_end_time: str,
    total_rounds: int,
    notes: str,
    session_id: Optional[str] = None,
    speed_condition: Optional[str] = None,
) -> None:
    _post(
        "/end_experiment",
        {
            "user_id": user_id,
            "condition": condition,
            "exp_start_time": exp_start_time,
            "exp_end_time": exp_end_time,
            "total_rounds": total_rounds,
            "notes": notes,
            "session_id": session_id,
            "speed_condition": speed_condition,
        },
    )


def start_round(
    user_id: int,
    condition: int,
    round_id: int,
    agent_active: bool,
    human_active: bool,
    round_start_time: str,
    session_id: Optional[str] = None,
    speed_condition: Optional[str] = None,
    level_name: Optional[str] = None,
) -> None:
    _post(
        "/start_round",
        {
            "user_id": user_id,
            "condition": condition,
            "round_id": round_id,
            "agent_active": agent_active,
            "human_active": human_active,
            "round_start_time": round_start_time,
            "session_id": session_id,
            "speed_condition": speed_condition,
            "level_name": level_name,
        },
    )


def end_round(
    user_id: int,
    condition: int,
    round_id: int,
    round_start_time: str,
    round_end_time: str,
    score: int,
    errors: int,
    collisions: int,
    ball_spawn: int,
    signal_sent: int,
    ball_catch: int,
    ball_miss: int,
    agent_active: bool,
    human_active: bool,
    session_id: Optional[str] = None,
    speed_condition: Optional[str] = None,
    level_name: Optional[str] = None,
) -> None:
    _post(
        "/end_round",
        {
            "user_id": user_id,
            "condition": condition,
            "round_id": round_id,
            "round_start_time": round_start_time,
            "round_end_time": round_end_time,
            "score": score,
            "errors": errors,
            "collisions": collisions,
            "ball_spawn": ball_spawn,
            "signal_sent": signal_sent,
            "ball_catch": ball_catch,
            "ball_miss": ball_miss,
            "agent_active": agent_active,
            "human_active": human_active,
            "session_id": session_id,
            "speed_condition": speed_condition,
            "level_name": level_name,
        },
    )


def log_event(payload: Dict[str, Any]) -> None:
    _post("/log_event", payload)


class AIClient:
    """
    Background AI client:
    - If websockets is available, attempts to connect to ws_uri and receive simple action messages:
      {"move": -1/0/1, "shoot": true/false}
    - Otherwise runs a local fallback that outputs no-op actions.
    Use get_latest_action() from the main thread.
    """
    def __init__(self, ws_uri: str = "ws://localhost:8000/ai/ws"):
        self.ws_uri = ws_uri
        self._latest_action: Dict[str, Any] = {"move": 0, "shoot": False}
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run_loop(self):
        if websockets and asyncio:
            asyncio.new_event_loop().run_until_complete(self._ws_loop())
        else:
            # fallback loop: simple periodic no-op (or very simple rule)
            while self._running:
                with self._lock:
                    # keep default no-op; can be extended to simple heuristic
                    self._latest_action = {"move": 0, "shoot": False}
                time.sleep(0.05)

    async def _ws_loop(self):
        try:
            async with websockets.connect(self.ws_uri) as ws:
                # optional handshake
                try:
                    await ws.send(json.dumps({"type": "hello", "role": "client"}))
                except Exception:
                    pass
                while self._running:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=0.2)
                        data = json.loads(msg)
                        move = int(data.get("move", 0))
                        shoot = bool(data.get("shoot", False))
                        with self._lock:
                            self._latest_action = {"move": move, "shoot": shoot}
                    except asyncio.TimeoutError:
                        # heartbeat: optionally request action
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        print("[AIClient] ws recv error:", e)
                        await asyncio.sleep(0.5)
        except Exception as e:
            print("[AIClient] websocket connection failed:", e)
            # fallback behaviour
            while self._running:
                with self._lock:
                    self._latest_action = {"move": 0, "shoot": False}
                time.sleep(0.2)

    def get_latest_action(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._latest_action)
