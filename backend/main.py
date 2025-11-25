from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Optional, Callable, Iterable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CONDITION_MAP = {
    1: "no_signal",
    2: "human_dom",
    3: "agent_dom",
    4: "negotiation",
}


# ---------- Pydantic Schemas ----------
class ExperimentStart(BaseModel):
    user_id: int
    condition: int
    total_rounds: int = 3
    notes: str = ""
    exp_start_time: Optional[str] = None  # ISO string; if None, use now


class ExperimentEnd(BaseModel):
    user_id: int
    condition: int
    exp_start_time: Optional[str] = None  # send back the original start or leave None
    exp_end_time: Optional[str] = None  # if None, use now
    total_rounds: Optional[int] = None
    notes: str = ""


class RoundStart(BaseModel):
    user_id: int
    condition: int
    round_id: int
    agent_active: bool = False
    human_active: bool = False
    round_start_time: Optional[str] = None  # ISO


class RoundEnd(BaseModel):
    user_id: int
    condition: int
    round_id: int
    round_start_time: Optional[str] = None
    round_end_time: Optional[str] = None
    score: int = 0
    errors: int = 0
    collisions: int = 0
    ball_spawn: int = 0
    signal_sent: int = 0
    ball_catch: int = 0
    ball_miss: int = 0
    agent_active: bool = False
    human_active: bool = False


class EventLog(BaseModel):
    user_id: int
    condition: int
    round_id: int
    timestamp: Optional[str] = None  # ISO
    event_type: str
    ball_x: int
    ball_y: int
    human_x: int
    human_y: int
    agent_x: int
    agent_y: int
    triggered_by: str = "NA"
    signal_type: str = "NA"
    dir_ratio: Optional[float] = None
    ball_speed: Optional[float] = None
    ball_angle: Optional[float] = None


# ---------- Helpers ----------
def condition_folder(condition: int) -> str:
    return CONDITION_MAP.get(condition, str(condition))


def ensure_dir(user_id: int, condition: int) -> Path:
    path = DATA_DIR / condition_folder(condition) / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_csv(file_path: Path, header: list[str]) -> None:
    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)


def append_row(file_path: Path, row: Iterable) -> None:
    with file_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)


def update_row(
    file_path: Path, match_fn: Callable[[dict], bool], update_fn: Callable[[dict], dict]
) -> bool:
    if not file_path.exists():
        return False
    updated = False
    with file_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames
    if not fieldnames:
        return False

    for i in range(len(rows) - 1, -1, -1):  # update latest match
        if match_fn(rows[i]):
            rows[i] = update_fn(rows[i])
            updated = True
            break

    if updated:
        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    return updated


def now_iso() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


# ---------- Endpoints ----------
@app.get("/health")
def health_check():
    return {"status": "ok", "time": now_iso()}


@app.post("/start_experiment")
def start_experiment(req: ExperimentStart):
    exp_start = req.exp_start_time or now_iso()
    dir_path = ensure_dir(req.user_id, req.condition)
    exp_file = dir_path / "experiment.csv"
    ensure_csv(
        exp_file,
        [
            "user_id",
            "condition",
            "exp_start_time",
            "exp_end_time",
            "total_rounds",
            "notes",
        ],
    )
    append_row(
        exp_file,
        [
            req.user_id,
            req.condition,
            exp_start,
            "",
            req.total_rounds,
            req.notes,
        ],
    )
    return {"status": "ok", "exp_start_time": exp_start}


@app.post("/end_experiment")
def end_experiment(req: ExperimentEnd):
    exp_end = req.exp_end_time or now_iso()
    dir_path = ensure_dir(req.user_id, req.condition)
    exp_file = dir_path / "experiment.csv"
    ensure_csv(
        exp_file,
        [
            "user_id",
            "condition",
            "exp_start_time",
            "exp_end_time",
            "total_rounds",
            "notes",
        ],
    )

    def match(row: dict) -> bool:
        return (
            row.get("user_id") == str(req.user_id)
            and row.get("condition") == str(req.condition)
            and (row.get("exp_end_time") == "" or row.get("exp_end_time") is None)
        )

    def updater(row: dict) -> dict:
        row["exp_end_time"] = exp_end
        if req.total_rounds is not None:
            row["total_rounds"] = str(req.total_rounds)
        if req.notes:
            row["notes"] = req.notes
        if req.exp_start_time:
            row["exp_start_time"] = req.exp_start_time
        return row

    updated = update_row(exp_file, match, updater)
    if not updated:
        # fallback: append a new row
        append_row(
            exp_file,
            [
                req.user_id,
                req.condition,
                req.exp_start_time or "",
                exp_end,
                req.total_rounds or "",
                req.notes,
            ],
        )
    return {"status": "ok", "exp_end_time": exp_end}


@app.post("/start_round")
def start_round(req: RoundStart):
    start_time = req.round_start_time or now_iso()
    dir_path = ensure_dir(req.user_id, req.condition)
    round_file = dir_path / "round.csv"
    ensure_csv(
        round_file,
        [
            "user_id",
            "condition",
            "round_id",
            "round_start_time",
            "round_end_time",
            "score",
            "errors",
            "agent_active",
            "human_active",
            "ball_spawn",
            "paddle_collision",
            "signal_sent",
            "ball_catch",
            "ball_miss",
        ],
    )
    append_row(
        round_file,
        [
            req.user_id,
            req.condition,
            req.round_id,
            start_time,
            "",
            0,
            0,
            1 if req.agent_active else 0,
            1 if req.human_active else 0,
            0,
            0,
            0,
            0,
            0,
        ],
    )
    return {"status": "ok", "round_start_time": start_time}


@app.post("/end_round")
def end_round(req: RoundEnd):
    end_time = req.round_end_time or now_iso()
    dir_path = ensure_dir(req.user_id, req.condition)
    round_file = dir_path / "round.csv"
    ensure_csv(
        round_file,
        [
            "user_id",
            "condition",
            "round_id",
            "round_start_time",
            "round_end_time",
            "score",
            "errors",
            "agent_active",
            "human_active",
            "ball_spawn",
            "paddle_collision",
            "signal_sent",
            "ball_catch",
            "ball_miss",
        ],
    )

    def match(row: dict) -> bool:
        return (
            row.get("user_id") == str(req.user_id)
            and row.get("condition") == str(req.condition)
            and row.get("round_id") == str(req.round_id)
            and (row.get("round_end_time") == "" or row.get("round_end_time") is None)
        )

    def updater(row: dict) -> dict:
        row["round_end_time"] = end_time
        row["score"] = str(req.score)
        row["errors"] = str(req.errors)
        row["agent_active"] = "1" if req.agent_active else "0"
        row["human_active"] = "1" if req.human_active else "0"
        row["ball_spawn"] = str(req.ball_spawn)
        row["paddle_collision"] = str(req.collisions)
        row["signal_sent"] = str(req.signal_sent)
        row["ball_catch"] = str(req.ball_catch)
        row["ball_miss"] = str(req.ball_miss)
        if req.round_start_time:
            row["round_start_time"] = req.round_start_time
        return row

    updated = update_row(round_file, match, updater)
    if not updated:
        append_row(
            round_file,
            [
                req.user_id,
                req.condition,
                req.round_id,
                req.round_start_time or "",
                end_time,
                req.score,
                req.errors,
                1 if req.agent_active else 0,
                1 if req.human_active else 0,
                req.ball_spawn,
                req.collisions,
                req.signal_sent,
                req.ball_catch,
                req.ball_miss,
            ],
        )

    return {"status": "ok", "round_end_time": end_time}


@app.post("/log_event")
def log_event(ev: EventLog):
    ts = ev.timestamp or now_iso()
    dir_path = ensure_dir(ev.user_id, ev.condition)
    events_file = dir_path / "events.csv"
    ensure_csv(
        events_file,
        [
            "user_id",
            "condition",
            "round_id",
            "timestamp",
            "event_type",
            "ball_x",
            "ball_y",
            "human_x",
            "human_y",
            "agent_x",
            "agent_y",
            "triggered_by",
            "signal_type",
            "dir_ratio",
            "ball_speed",
            "ball_angle",
        ],
    )
    append_row(
        events_file,
        [
            ev.user_id,
            ev.condition,
            ev.round_id,
            ts,
            ev.event_type,
            ev.ball_x,
            ev.ball_y,
            ev.human_x,
            ev.human_y,
            ev.agent_x,
            ev.agent_y,
            ev.triggered_by,
            ev.signal_type,
            ev.dir_ratio if ev.dir_ratio is not None else "NA",
            ev.ball_speed if ev.ball_speed is not None else "NA",
            ev.ball_angle if ev.ball_angle is not None else "NA",
        ],
    )
    return {"status": "ok", "timestamp": ts}
