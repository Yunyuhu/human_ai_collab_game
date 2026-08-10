import csv
import datetime as dt
import math
import os
from pathlib import Path
from typing import Dict, Any, Optional


class DataLogger:
    def __init__(self, base_dir: Path):
        self.base_data_path = base_dir / "data"
        self.user_id: Optional[str] = None
        self.condition_name: Optional[str] = None
        self.data_path: Optional[Path] = None

        self.experiment_file: Optional[Path] = None
        self.round_file: Optional[Path] = None
        self.event_file: Optional[Path] = None

        self.experiment_header: list[str] = []
        self.round_header: list[str] = []
        self.event_header: list[str] = []

        self.human_shots = 0
        self.human_hits = 0
        self.agent_shots = 0
        self.agent_hits = 0
        self.total_signals = 0
        self.human_total_signals = 0
        self.agent_total_signals = 0
        self.total_conflict = 0

    def setup_experiment(self, user_id: str, condition_name: str):
        self.user_id = user_id
        self.condition_name = condition_name
        self.data_path = self.base_data_path / condition_name / user_id
        try:
            self.data_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"Error creating directory {self.data_path}: {e}")
            return

        self.experiment_file = self.data_path / "experiment.csv"
        self.round_file = self.data_path / "round.csv"
        self.event_file = self.data_path / "events.csv"

        self.experiment_header = self._init_csv(
            self.experiment_file,
            [
                "user_id", "exp_start_time", "exp_end_time", "total_score", "total_errors",
                "human_total_accuracy", "agent_total_accuracy", "total_signals",
                "human_total_signals", "agent_total_signals", "total_conflict",
                "total_rounds", "notes"
            ],
        )
        self.round_header = self._init_csv(
            self.round_file,
            [
                "user_id", "round_id", "round_start_time", "round_end_time", "round_duration",
                "round_score", "round_errors", "human_accuracy", "agent_accuracy",
                "enemy_spawn_count", "conflict_count", "human_signal_count", "agent_signal_count"
            ],
        )
        self.event_header = self._init_csv(
            self.event_file,
            [
                "user_id", "round_id", "timestamp", "event_type", "flight_id",
                "flight_x", "flight_y", "human_x", "human_y", "agent_x", "agent_y",
                "dist_human_flight", "dist_agent_flight", "dist_human_agent", # dist_between is split into 3
                "triggered_by", "signal_type", "dir_ratio", "flight_speed", "flight_angle",
                "human_speed", "human_direction", "agent_speed", "agent_direction"
            ],
        )

    def _init_csv(self, file_path: Path, header: list[str]):
        if not file_path.exists():
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
            except IOError as e:
                print(f"Error initializing CSV {file_path}: {e}")
        return header

    def _append_to_csv(self, file_path: Optional[Path], header: list[str], data: Dict[str, Any]):
        if not file_path or not self.data_path:
            print("[DataLogger] Logger not set up. Cannot write data.")
            return
        if not header:
            print(f"[DataLogger] Header for {file_path} is not initialized. Cannot write data.")
            return

        try:
            self.data_path.mkdir(parents=True, exist_ok=True)
            if not file_path.exists():
                with open(file_path, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(header)
            with open(file_path, "a", newline="", encoding="utf-8") as f:
                # Create a list of values in the correct order based on the cached header
                row = [data.get(h, "") for h in header]
                csv.writer(f).writerow(row)

        except (IOError, StopIteration) as e:
            print(f"Error writing to CSV {file_path}: {e}")

    def log_or_update_experiment(self, data: Dict[str, Any]):
        """
        Logs or updates the experiment data.
        If a row for the user_id already exists, it updates it.
        Otherwise, it appends a new row.
        """
        if not self.experiment_file or not self.experiment_header:
            print("[DataLogger] Experiment file not initialized.")
            return

        user_id_str = f"{self.condition_name}_{self.user_id}"
        data["user_id"] = f"{self.condition_name}_{self.user_id}"

        rows = []
        found = False
        try:
            if self.experiment_file.exists() and self.experiment_file.stat().st_size > 0:
                with open(self.experiment_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get("user_id") == user_id_str:
                            rows.append(data)  # Update with new data
                            found = True
                        else:
                            rows.append(row)
        except (IOError, StopIteration):
            pass  # File might be empty or non-existent, which is fine.

        if not found:
            rows.append(data)

        self.data_path.mkdir(parents=True, exist_ok=True)
        with open(self.experiment_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.experiment_header)
            writer.writeheader()
            writer.writerows(rows)

    def log_round(self, data: Dict[str, Any]):
        data["user_id"] = f"{self.condition_name}_{self.user_id}"
        self._append_to_csv(self.round_file, self.round_header, data)

    def log_event(
        self,
        event_type: str,
        round_id: int,
        flight_id: int,
        game_state: Dict[str, Any],
        triggered_by: str = "NA",
        signal_type: str = "NA",
        dir_ratio: Optional[float] = None,
        human_speed: float = 0.0,
        human_direction: float = 0.0,
        agent_speed: float = 0.0,
        agent_direction: float = 0.0,
    ):
        if not self.data_path:
            return

        flight_x, flight_y = game_state.get("flight_pos", (0, 0))
        human_x, human_y = game_state.get("human_pos", (0, 0))
        agent_x, agent_y = game_state.get("agent_pos", (0, 0))
        flight_vx, flight_vy = game_state.get("flight_vel", (0, 0))

        dist_human_flight = math.hypot(human_x - flight_x, human_y - flight_y)
        dist_agent_flight = math.hypot(agent_x - flight_x, agent_y - flight_y)
        dist_human_agent = math.hypot(human_x - agent_x, human_y - agent_y)

        flight_speed = math.hypot(flight_vx, flight_vy)
        flight_angle = math.degrees(math.atan2(flight_vy, flight_vx))

        event_data = {
            "user_id": f"{self.condition_name}_{self.user_id}",
            "round_id": f"R{round_id}",
            "timestamp": dt.datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "flight_id": flight_id,
            "flight_x": int(flight_x),
            "flight_y": int(flight_y),
            "human_x": int(human_x),
            "human_y": int(human_y),
            "agent_x": int(agent_x),
            "agent_y": int(agent_y),
            "dist_human_flight": round(dist_human_flight, 2),
            "dist_agent_flight": round(dist_agent_flight, 2),
            "dist_human_agent": round(dist_human_agent, 2),
            "triggered_by": triggered_by,
            "signal_type": signal_type,
            "dir_ratio": round(dir_ratio, 3) if dir_ratio is not None else "NA",
            "flight_speed": round(flight_speed, 2),
            "flight_angle": round(flight_angle, 2),
            "human_speed": round(human_speed, 2),
            "human_direction": round(human_direction, 2),
            "agent_speed": round(agent_speed, 2),
            "agent_direction": round(agent_direction, 2),
        }
        self._append_to_csv(self.event_file, self.event_header, event_data)

    def reset_experiment_stats(self):
        self.human_shots = 0
        self.human_hits = 0
        self.agent_shots = 0
        self.agent_hits = 0
        self.total_signals = 0
        self.human_total_signals = 0
        self.agent_total_signals = 0
        self.total_conflict = 0