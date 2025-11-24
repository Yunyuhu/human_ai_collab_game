from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import csv
from typing import Optional


app = FastAPI()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# --- 簡單資料模型示意 ---

class StateUpdate(BaseModel):
    user_id: str
    condition: str  # NoSignal / HumanDominant / AgentDominant / Negotiation
    round_id: int
    timestamp: float
    ball_x: float
    ball_y: float
    human_x: float
    human_y: float
    agent_x: float
    agent_y: float
    triggered_by: Optional[str] = None  # "human" / "agent" / None
    signal_type: Optional[str] = None   # "I_CAN" / "YOUR_TURN" / None
    dir_ratio: Optional[float] = None   # DIR = D_agent / (D_agent + D_human)
    event_type: str = "state"



def _ensure_csv(file_path: Path, header: list[str]):
    if not file_path.exists():
        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)


@app.on_event("startup")
def init_csv_files():
    # 先準備 events.csv，experiment.csv / round.csv 之後再細分
    events_file = DATA_DIR / "events.csv"
    header = [
        "user_id", "condition", "round_id", "timestamp",
        "event_type", "ball_x", "ball_y",
        "human_x", "human_y",
        "agent_x", "agent_y",
        "triggered_by", "signal_type", "dir_ratio",
        "server_received_at"
    ]
    _ensure_csv(events_file, header)


@app.get("/health")
def health_check():
    return {"status": "ok", "time": datetime.utcnow().isoformat() + "Z"}


@app.post("/log_event")
def log_event(state: StateUpdate):
    events_file = DATA_DIR / "events.csv"
    row = [
        state.user_id,
        state.condition,
        state.round_id,
        state.timestamp,
        state.event_type,
        state.ball_x,
        state.ball_y,
        state.human_x,
        state.human_y,
        state.agent_x,
        state.agent_y,
        state.triggered_by,
        state.signal_type,
        state.dir_ratio,
        datetime.utcnow().isoformat() + "Z",
    ]
    with events_file.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)

    return {"status": "logged"}
