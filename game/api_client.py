import json
from typing import Any, Dict, Optional

import requests

API_BASE = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 1.5


def _post(path: str, payload: Dict[str, Any]) -> None:
    url = f"{API_BASE}{path}"
    try:
        requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
    except Exception as exc:
        print(f"[api] POST {path} failed: {exc}")


def start_experiment(user_id: int, condition: int, total_rounds: int, notes: str, exp_start_time: str) -> None:
    _post(
        "/start_experiment",
        {
            "user_id": user_id,
            "condition": condition,
            "total_rounds": total_rounds,
            "notes": notes,
            "exp_start_time": exp_start_time,
        },
    )


def end_experiment(user_id: int, condition: int, exp_start_time: str, exp_end_time: str, total_rounds: int, notes: str) -> None:
    _post(
        "/end_experiment",
        {
            "user_id": user_id,
            "condition": condition,
            "exp_start_time": exp_start_time,
            "exp_end_time": exp_end_time,
            "total_rounds": total_rounds,
            "notes": notes,
        },
    )


def start_round(user_id: int, condition: int, round_id: int, agent_active: bool, human_active: bool, round_start_time: str) -> None:
    _post(
        "/start_round",
        {
            "user_id": user_id,
            "condition": condition,
            "round_id": round_id,
            "agent_active": agent_active,
            "human_active": human_active,
            "round_start_time": round_start_time,
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
        },
    )


def log_event(payload: Dict[str, Any]) -> None:
    _post("/log_event", payload)
