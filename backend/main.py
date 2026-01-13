from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path
from typing import Optional, Iterable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)



# ---------- Pydantic Schemas ----------
class ExperimentStart(BaseModel):
    user_id: int
    condition: int
    total_rounds: int = 3
    notes: str = ""
    exp_start_time: Optional[str] = None  # ISO string; if None, use now
    session_id: Optional[str] = None
    speed_condition: Optional[str] = None


class ExperimentEnd(BaseModel):
    user_id: int
    condition: int
    exp_start_time: Optional[str] = None  # send back the original start or leave None
    exp_end_time: Optional[str] = None  # if None, use now
    total_rounds: Optional[int] = None
    notes: str = ""
    session_id: Optional[str] = None
    speed_condition: Optional[str] = None


class RoundStart(BaseModel):
    user_id: int
    condition: int
    round_id: int
    agent_active: bool = False
    human_active: bool = False
    round_start_time: Optional[str] = None  # ISO
    session_id: Optional[str] = None
    speed_condition: Optional[str] = None
    level_name: Optional[str] = None


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
    session_id: Optional[str] = None
    speed_condition: Optional[str] = None
    level_name: Optional[str] = None


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
    session_id: Optional[str] = None
    speed_condition: Optional[str] = None
    level_name: Optional[str] = None
    shot_hit: Optional[bool] = None
    shot_interval: Optional[float] = None
    shot_distance: Optional[float] = None
    shot_inner_radius: Optional[float] = None
    overlap_crosshair: Optional[bool] = None


# ---------- Helpers ----------


def user_dir(user_id: int) -> Path:
    path = DATA_DIR / f"user_{user_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_speed_condition(speed_condition: Optional[str]) -> str:
    if speed_condition and speed_condition.upper() in ("A", "B"):
        return speed_condition.upper()
    return "A"


def level_name_for_round(round_id: int) -> str:
    return f"level{max(1, round_id)}"


def session_id_now() -> str:
    return dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def session_dir(user_id: int, speed_condition: str, session_id: str) -> Path:
    return user_dir(user_id) / f"condition_{speed_condition}" / f"session_{session_id}"


def ensure_user_meta(user_id: int) -> None:
    meta_path = user_dir(user_id) / "meta.json"
    if meta_path.exists():
        return
    meta = {
        "user_id": f"{user_id:03d}",
        "conditions": {
            "A": {"human_speed": 2.2},
            "B": {"human_speed": 2.4},
        },
        "segment_setting": {
            "practice_sec": 0,
            "level_sec": 120,
            "level_count": 3,
        },
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=True, indent=2), encoding="utf-8")


def parse_iso(ts: Optional[str]) -> Optional[dt.datetime]:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1]
        return dt.datetime.fromisoformat(ts)
    except Exception:
        return None


def load_summary(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_summary(path: Path, summary: dict) -> None:
    path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")


def ensure_level_csv(path: Path) -> None:
    ensure_csv(
        path,
        [
            "user_id",
            "session_id",
            "speed_condition",
            "round_id",
            "level_name",
            "timestamp",
            "event_type",
            "triggered_by",
            "signal_type",
            "dir_ratio",
            "ball_x",
            "ball_y",
            "human_x",
            "human_y",
            "agent_x",
            "agent_y",
            "ball_speed",
            "ball_angle",
            "shot_hit",
            "shot_interval",
            "shot_distance",
            "shot_inner_radius",
            "overlap_crosshair",
        ],
    )


def compute_level_metrics(level_file: Path, score: int, errors: int, start_time: Optional[str], end_time: Optional[str]) -> dict:
    overlap_start_times = []
    overlap_end_times = []
    shot_times = []
    success_times = []
    miss_times = []
    overlap_intervals = []
    last_overlap_start = None
    if level_file.exists():
        with level_file.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                event = row.get("event_type")
                ts = parse_iso(row.get("timestamp"))
                if event == "overlap_start" and ts:
                    overlap_start_times.append(row.get("timestamp"))
                    last_overlap_start = ts
                elif event == "overlap_end" and ts:
                    overlap_end_times.append(row.get("timestamp"))
                    if last_overlap_start:
                        overlap_intervals.append((last_overlap_start, ts))
                        last_overlap_start = None
                elif event == "shot" and ts:
                    shot_times.append(row.get("timestamp"))
                elif event == "success" and ts:
                    success_times.append(row.get("timestamp"))
                elif event == "miss" and ts:
                    miss_times.append(row.get("timestamp"))
    end_dt = parse_iso(end_time)
    if last_overlap_start and end_dt:
        overlap_intervals.append((last_overlap_start, end_dt))

    overlap_total_time_ms = 0.0
    for start_dt, end_dt in overlap_intervals:
        overlap_total_time_ms += max(0.0, (end_dt - start_dt).total_seconds() * 1000.0)

    opportunity_count = len(overlap_start_times)
    success_count = len(success_times)
    miss_count = len(miss_times)
    shot_count = len(shot_times)
    shot_intervals_ms = []
    prev_shot_dt = None
    for ts in shot_times:
        ts_dt = parse_iso(ts)
        if ts_dt and prev_shot_dt:
            shot_intervals_ms.append((ts_dt - prev_shot_dt).total_seconds() * 1000.0)
        if ts_dt:
            prev_shot_dt = ts_dt
    shot_interval_mean_ms = (
        sum(shot_intervals_ms) / len(shot_intervals_ms) if shot_intervals_ms else None
    )
    shot_interval_min_ms = min(shot_intervals_ms) if shot_intervals_ms else None
    shot_interval_max_ms = max(shot_intervals_ms) if shot_intervals_ms else None
    accuracy_rate = success_count / opportunity_count if opportunity_count > 0 else None
    shooting_accuracy_rate = (
        success_count / (success_count + miss_count) if (success_count + miss_count) > 0 else None
    )
    accuracy_integral = (
        accuracy_rate * overlap_total_time_ms if accuracy_rate is not None else None
    )

    start_dt = parse_iso(start_time)
    duration_sec = None
    if start_dt and end_dt:
        duration_sec = max(0.0, (end_dt - start_dt).total_seconds())
    score_rate = (score / duration_sec) if duration_sec else None
    error_rate = (errors / duration_sec) if duration_sec else None

    return {
        "score_end_total": score,
        "errors_end_total": errors,
        "score_delta": score,
        "errors_delta": errors,
        "duration_sec": duration_sec,
        "score_rate": score_rate,
        "error_rate": error_rate,
        "overlap_start_times": overlap_start_times,
        "overlap_end_times": overlap_end_times,
        "overlap_total_time_ms": overlap_total_time_ms,
        "opportunity_count": opportunity_count,
        "shot_times": shot_times,
        "success_times": success_times,
        "miss_times": miss_times,
        "shot_count": shot_count,
        "shot_interval_mean_ms": shot_interval_mean_ms,
        "shot_interval_min_ms": shot_interval_min_ms,
        "shot_interval_max_ms": shot_interval_max_ms,
        "success_count": success_count,
        "miss_count": miss_count,
        "accuracy_rate": accuracy_rate,
        "shooting_accuracy_rate": shooting_accuracy_rate,
        "accuracy_integral": accuracy_integral,
    }


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


def now_iso() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


# ---------- Endpoints ----------
@app.get("/health")
def health_check():
    return {"status": "ok", "time": now_iso(), "schema_version": "session_v2"}


@app.post("/start_experiment")
def start_experiment(req: ExperimentStart):
    exp_start = req.exp_start_time or now_iso()
    session_id = req.session_id or session_id_now()
    speed_condition = normalize_speed_condition(req.speed_condition)
    ensure_user_meta(req.user_id)
    session_path = session_dir(req.user_id, speed_condition, session_id)
    session_path.mkdir(parents=True, exist_ok=True)
    for round_id in range(1, req.total_rounds + 1):
        level_name = level_name_for_round(round_id)
        ensure_level_csv(session_path / f"{level_name}.csv")
    summary_path = session_path / "summary.json"
    if not summary_path.exists():
        summary = {
            "user_id": req.user_id,
            "session_id": session_id,
            "speed_condition": speed_condition,
            "exp_start_time": exp_start,
            "levels": {},
            "totals": {},
        }
        save_summary(summary_path, summary)

    return {
        "status": "ok",
        "exp_start_time": exp_start,
        "session_id": session_id,
        "speed_condition": speed_condition,
    }


@app.post("/end_experiment")
def end_experiment(req: ExperimentEnd):
    exp_end = req.exp_end_time or now_iso()
    session_id = req.session_id
    speed_condition = normalize_speed_condition(req.speed_condition)
    if session_id:
        summary_path = session_dir(req.user_id, speed_condition, session_id) / "summary.json"
        summary = load_summary(summary_path)
        summary["exp_end_time"] = exp_end
        save_summary(summary_path, summary)
    return {
        "status": "ok",
        "exp_end_time": exp_end,
        "session_id": session_id or "",
        "speed_condition": speed_condition,
    }


@app.post("/start_round")
def start_round(req: RoundStart):
    start_time = req.round_start_time or now_iso()
    if req.session_id:
        speed_condition = normalize_speed_condition(req.speed_condition)
        level_name = req.level_name or level_name_for_round(req.round_id)
        session_path = session_dir(req.user_id, speed_condition, req.session_id)
        session_path.mkdir(parents=True, exist_ok=True)
        ensure_level_csv(session_path / f"{level_name}.csv")
    return {"status": "ok", "round_start_time": start_time}


@app.post("/end_round")
def end_round(req: RoundEnd):
    end_time = req.round_end_time or now_iso()
    if req.session_id:
        speed_condition = normalize_speed_condition(req.speed_condition)
        level_name = req.level_name or level_name_for_round(req.round_id)
        session_path = session_dir(req.user_id, speed_condition, req.session_id)
        session_path.mkdir(parents=True, exist_ok=True)
        level_file = session_path / f"{level_name}.csv"
        ensure_level_csv(level_file)
        metrics = compute_level_metrics(
            level_file,
            req.score,
            req.errors,
            req.round_start_time,
            end_time,
        )
        summary_path = session_path / "summary.json"
        summary = load_summary(summary_path)
        summary["user_id"] = req.user_id
        summary["session_id"] = req.session_id
        summary["speed_condition"] = speed_condition
        summary.setdefault("levels", {})
        summary["levels"][level_name] = {
            "round_id": req.round_id,
            "round_start_time": req.round_start_time,
            "round_end_time": end_time,
            **metrics,
        }
        totals = {
            "score": 0,
            "errors": 0,
            "duration_sec": 0.0,
            "opportunity_count": 0,
            "success_count": 0,
            "miss_count": 0,
            "overlap_total_time_ms": 0.0,
            "shot_count": 0,
            "shot_intervals_ms": [],
        }
        for level in summary["levels"].values():
            totals["score"] += int(level.get("score_end_total") or 0)
            totals["errors"] += int(level.get("errors_end_total") or 0)
            totals["duration_sec"] += float(level.get("duration_sec") or 0.0)
            totals["opportunity_count"] += int(level.get("opportunity_count") or 0)
            totals["success_count"] += int(level.get("success_count") or 0)
            totals["miss_count"] += int(level.get("miss_count") or 0)
            totals["overlap_total_time_ms"] += float(level.get("overlap_total_time_ms") or 0.0)
            totals["shot_count"] += int(level.get("shot_count") or 0)
            mean_ms = level.get("shot_interval_mean_ms")
            if mean_ms is not None:
                totals["shot_intervals_ms"].append(float(mean_ms))
        totals["score_rate"] = (
            totals["score"] / totals["duration_sec"] if totals["duration_sec"] else None
        )
        totals["error_rate"] = (
            totals["errors"] / totals["duration_sec"] if totals["duration_sec"] else None
        )
        totals["accuracy_rate"] = (
            totals["success_count"] / totals["opportunity_count"] if totals["opportunity_count"] else None
        )
        totals["shooting_accuracy_rate"] = (
            totals["success_count"] / (totals["success_count"] + totals["miss_count"])
            if (totals["success_count"] + totals["miss_count"])
            else None
        )
        totals["accuracy_integral"] = (
            totals["accuracy_rate"] * totals["overlap_total_time_ms"]
            if totals["accuracy_rate"] is not None
            else None
        )
        if totals["shot_intervals_ms"]:
            totals["shot_interval_mean_ms"] = (
                sum(totals["shot_intervals_ms"]) / len(totals["shot_intervals_ms"])
            )
            totals["shot_interval_min_ms"] = min(totals["shot_intervals_ms"])
            totals["shot_interval_max_ms"] = max(totals["shot_intervals_ms"])
        else:
            totals["shot_interval_mean_ms"] = None
            totals["shot_interval_min_ms"] = None
            totals["shot_interval_max_ms"] = None
        totals.pop("shot_intervals_ms", None)
        summary["totals"] = totals
        save_summary(summary_path, summary)

    return {"status": "ok", "round_end_time": end_time}


@app.post("/log_event")
def log_event(ev: EventLog):
    ts = ev.timestamp or now_iso()
    if ev.session_id:
        speed_condition = normalize_speed_condition(ev.speed_condition)
        level_name = ev.level_name or level_name_for_round(ev.round_id)
        session_path = session_dir(ev.user_id, speed_condition, ev.session_id)
        session_path.mkdir(parents=True, exist_ok=True)
        level_file = session_path / f"{level_name}.csv"
        ensure_level_csv(level_file)
        append_row(
            level_file,
            [
                ev.user_id,
                ev.session_id,
                speed_condition,
                ev.round_id,
                level_name,
                ts,
                ev.event_type,
                ev.triggered_by,
                ev.signal_type,
                ev.dir_ratio if ev.dir_ratio is not None else "NA",
                ev.ball_x,
                ev.ball_y,
                ev.human_x,
                ev.human_y,
                ev.agent_x,
                ev.agent_y,
                ev.ball_speed if ev.ball_speed is not None else "NA",
                ev.ball_angle if ev.ball_angle is not None else "NA",
                1 if ev.shot_hit else 0 if ev.shot_hit is not None else "",
                ev.shot_interval if ev.shot_interval is not None else "",
                ev.shot_distance if ev.shot_distance is not None else "",
                ev.shot_inner_radius if ev.shot_inner_radius is not None else "",
                1 if ev.overlap_crosshair else 0 if ev.overlap_crosshair is not None else "",
            ],
        )
    return {"status": "ok", "timestamp": ts}
