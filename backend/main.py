from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()

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


def now_iso() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


# ---------- Endpoints ----------
@app.get("/health")
def health_check():
    return {"status": "ok", "time": now_iso()}


@app.post("/start_experiment")
def start_experiment(req: ExperimentStart):
    exp_start = req.exp_start_time or now_iso()
    return {"status": "ok", "exp_start_time": exp_start}


@app.post("/end_experiment")
def end_experiment(req: ExperimentEnd):
    exp_end = req.exp_end_time or now_iso()
    return {"status": "ok", "exp_end_time": exp_end}


@app.post("/start_round")
def start_round(req: RoundStart):
    start_time = req.round_start_time or now_iso()
    return {"status": "ok", "round_start_time": start_time}


@app.post("/end_round")
def end_round(req: RoundEnd):
    end_time = req.round_end_time or now_iso()
    return {"status": "ok", "round_end_time": end_time}


@app.post("/log_event")
def log_event(ev: EventLog):
    ts = ev.timestamp or now_iso()
    return {"status": "ok", "timestamp": ts}
