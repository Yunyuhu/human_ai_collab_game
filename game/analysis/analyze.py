# -*- coding: utf-8 -*-
"""
Floating Rescue 實驗資料分析
讀取 game/data/<組別>/<實驗編號>/{experiment,round,events}.csv
輸出：
  1. combined_raw.xlsx      -- 彙整後的原始資料 + 組間比較統計 + 圖表（給 Excel 開）
  2. charts/*.png           -- 個別圖表檔案
可重複執行：資料夾新增實驗編號後，重新執行本檔案即可更新彙整結果。
"""
import os
import glob
import numpy as np
import pandas as pd
from scipy import stats

# ---------------------------------------------------------------------------
# 設定
# 預設假設本檔案放在 game/analysis/ 底下，資料夾結構為 game/data/...
# 若要在別的位置執行，可用環境變數 FR_DATA_ROOT / FR_OUT_DIR 覆蓋路徑。
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data"))
DEFAULT_OUT_DIR = SCRIPT_DIR

DATA_ROOT = os.environ.get("FR_DATA_ROOT", DEFAULT_DATA_ROOT)
OUT_DIR = os.environ.get("FR_OUT_DIR", DEFAULT_OUT_DIR)
CHART_DIR = os.path.join(OUT_DIR, "charts")
os.makedirs(CHART_DIR, exist_ok=True)

# 四組的固定順序與圖表配色（來自 dataviz 色票，類別色依固定順序指派，不可循環套用）
GROUP_ORDER = ["Agent Dominant", "Human Dominant", "Negotiation", "No Signal"]
GROUP_COLOR = {
    "Agent Dominant": "#2a78d6",   # blue
    "Human Dominant":  "#eb6834",  # orange
    "Negotiation":     "#1baf7a",  # aqua
    "No Signal":       "#eda100",  # yellow
}

# 排除的實驗編號（使用者要求撇除的參與者資料）。
# experiment_id 以資料夾名稱（字串）儲存，故此處以字串比對。
EXCLUDE_IDS = {"33", "35", "42", "44", "49", "50"}

# 訊號後移動反應：觀察視窗長度（秒）與「視為原地不動」的距離變化門檻（像素）。
# 畫面尺寸 WIDTH=1280, HEIGHT=720、角色準心寬度 PADDLE_W=100（見 main.py）。
# 3 秒視窗大約是遊戲內一次來回反應的時間；40px（約 0.4 個準心寬）以內的距離變化
# 視為「停留原地」（雜訊或原地小幅調整），超過則視為明確靠近／遠離敵機。
MOVEMENT_WINDOW_SEC = 3.0
MOVEMENT_STAY_THRESHOLD_PX = 40.0

# 「連續衝突只算一次」的合併秒數門檻。
# 依遊戲原始碼 main.py：
#   - 人類射擊誤傷（friendly fire）的懲罰時間 FRIENDLY_FIRE_PENALTY_SEC = 1.0 秒
#   - 準心重疊（overlap）的懲罰／護欄時間 OVERLAP_PENALTY_SEC = 1.5 秒
# 遊戲本身在重疊衝突已有 1.5 秒的「護欄期」，但護欄一過、若雙方仍黏在一起，就會
# 立刻再記一次 conflict 事件，導致原始 total_conflict / conflict_count 把同一段
# 「黏在一起／連續誤傷」的衝突拆成好幾筆。實際資料觀察也確認：同一段衝突的相鄰
# events 間隔大多落在 1.0～1.5 秒左右，真正各自獨立的新衝突則間隔數秒到數十秒不等。
# 因此這裡取 2.0 秒（略大於最長的懲罰／護欄時間）作為合併門檻：同一回合內，時間差
# <= 2.0 秒的相鄰 conflict 事件視為同一段連續衝突，只算一次。
CONFLICT_MERGE_GAP_SEC = 2.0

# ---------------------------------------------------------------------------
# 讀取並彙整三種 CSV
# ---------------------------------------------------------------------------
def load_all():
    exp_rows, round_rows, event_rows = [], [], []
    for group_dir in sorted(glob.glob(os.path.join(DATA_ROOT, "*"))):
        if not os.path.isdir(group_dir):
            continue
        group = os.path.basename(group_dir)
        for exp_dir in sorted(glob.glob(os.path.join(group_dir, "*"))):
            if not os.path.isdir(exp_dir):
                continue
            exp_id = os.path.basename(exp_dir)
            if exp_id in EXCLUDE_IDS:
                continue

            exp_csv = os.path.join(exp_dir, "experiment.csv")
            round_csv = os.path.join(exp_dir, "round.csv")
            event_csv = os.path.join(exp_dir, "events.csv")

            if os.path.exists(exp_csv) and os.path.getsize(exp_csv) > 0:
                df = pd.read_csv(exp_csv)
                df.insert(0, "group", group)
                df.insert(1, "experiment_id", exp_id)
                exp_rows.append(df)

            if os.path.exists(round_csv) and os.path.getsize(round_csv) > 0:
                df = pd.read_csv(round_csv)
                df.insert(0, "group", group)
                df.insert(1, "experiment_id", exp_id)
                round_rows.append(df)

            if os.path.exists(event_csv) and os.path.getsize(event_csv) > 0:
                df = pd.read_csv(event_csv)
                df.insert(0, "group", group)
                df.insert(1, "experiment_id", exp_id)
                event_rows.append(df)

    experiment_all = pd.concat(exp_rows, ignore_index=True) if exp_rows else pd.DataFrame()
    round_all = pd.concat(round_rows, ignore_index=True) if round_rows else pd.DataFrame()
    event_all = pd.concat(event_rows, ignore_index=True) if event_rows else pd.DataFrame()

    for df in (experiment_all, round_all, event_all):
        if not df.empty and "group" in df.columns:
            df["group"] = pd.Categorical(df["group"], categories=GROUP_ORDER, ordered=True)

    return experiment_all, round_all, event_all


# ---------------------------------------------------------------------------
# 組間比較統計（描述性統計 + Kruskal-Wallis，樣本數小僅供參考）
# ---------------------------------------------------------------------------
def group_summary(experiment_all: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "total_score", "total_errors", "human_total_accuracy", "agent_total_accuracy",
        "total_signals", "human_total_signals", "agent_total_signals",
        "total_conflict", "total_conflict_dedup", "total_rounds",
    ]
    rows = []
    for metric in metrics:
        if metric not in experiment_all.columns:
            continue
        groups_data = []
        row = {"metric": metric}
        for g in GROUP_ORDER:
            vals = experiment_all.loc[experiment_all["group"] == g, metric].dropna().astype(float)
            groups_data.append(vals)
            row[f"{g}_n"] = len(vals)
            row[f"{g}_mean"] = round(vals.mean(), 3) if len(vals) else np.nan
            row[f"{g}_sd"] = round(vals.std(ddof=1), 3) if len(vals) > 1 else np.nan
        # Kruskal-Wallis（非參數，適合小樣本、不假設常態）
        valid_groups = [g for g in groups_data if len(g) >= 2]
        if len(valid_groups) >= 2 and any(len(g) for g in valid_groups):
            try:
                h, p = stats.kruskal(*valid_groups)
                row["kruskal_H"] = round(h, 3)
                row["kruskal_p"] = round(p, 4)
            except ValueError:
                row["kruskal_H"] = np.nan
                row["kruskal_p"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def round_group_summary(round_all: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "round_score", "round_errors", "human_accuracy", "agent_accuracy",
        "conflict_count", "conflict_count_dedup", "human_signal_count", "agent_signal_count", "round_duration",
    ]
    rows = []
    for metric in metrics:
        if metric not in round_all.columns:
            continue
        groups_data = []
        row = {"metric": metric}
        for g in GROUP_ORDER:
            vals = round_all.loc[round_all["group"] == g, metric].dropna().astype(float)
            groups_data.append(vals)
            row[f"{g}_n"] = len(vals)
            row[f"{g}_mean"] = round(vals.mean(), 3) if len(vals) else np.nan
            row[f"{g}_sd"] = round(vals.std(ddof=1), 3) if len(vals) > 1 else np.nan
        valid_groups = [g for g in groups_data if len(g) >= 2]
        if len(valid_groups) >= 2:
            try:
                h, p = stats.kruskal(*valid_groups)
                row["kruskal_H"] = round(h, 3)
                row["kruskal_p"] = round(p, 4)
            except ValueError:
                row["kruskal_H"] = np.nan
                row["kruskal_p"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 輔助：回合編號 (R1 -> 1)、擊中敵機次數（由 events.csv 的 shot_hit 還原）
# ---------------------------------------------------------------------------
def add_round_num(df: pd.DataFrame, col: str = "round_id") -> pd.DataFrame:
    df = df.copy()
    df["round_num"] = df[col].str.replace("R", "", regex=False).astype(int)
    return df


def compute_hits(event_all: pd.DataFrame):
    """從 events.csv 還原人類 / AI 各自的擊中（shot_hit）次數。
    回傳 (hits_by_experiment, hits_by_round)，欄位皆含 human_hits / agent_hits。
    """
    hits = event_all[
        (event_all["event_type"] == "shot_hit") & (event_all["triggered_by"].isin(["human", "agent"]))
    ].copy()

    by_exp = (
        hits.groupby(["group", "experiment_id", "triggered_by"], observed=True)
        .size()
        .unstack(fill_value=0)
        .reindex(columns=["human", "agent"], fill_value=0)
        .rename(columns={"human": "human_hits", "agent": "agent_hits"})
        .reset_index()
    )

    hits = add_round_num(hits)
    by_round = (
        hits.groupby(["group", "experiment_id", "round_num", "triggered_by"], observed=True)
        .size()
        .unstack(fill_value=0)
        .reindex(columns=["human", "agent"], fill_value=0)
        .rename(columns={"human": "human_hits", "agent": "agent_hits"})
        .reset_index()
    )
    return by_exp, by_round


def compute_conflicts_dedup(event_all: pd.DataFrame, merge_gap_sec: float = CONFLICT_MERGE_GAP_SEC):
    """將 events.csv 裡的 conflict 事件，依「同一回合內、時間間隔 <= merge_gap_sec 秒」
    合併為同一段連續衝突，只算一次，藉此還原「衝突事件次數」（新欄位）。
    保留原始（未合併）的 total_conflict / conflict_count 不變，此函式只回傳新增的
    total_conflict_dedup（experiment 層級）與 conflict_count_dedup（round 層級），
    供之後與舊欄位並排比較。
    回傳 (by_exp, by_round)。
    """
    conf = event_all[event_all["event_type"] == "conflict"].copy()
    if conf.empty:
        by_exp = pd.DataFrame(columns=["group", "experiment_id", "total_conflict_dedup"])
        by_round = pd.DataFrame(columns=["group", "experiment_id", "round_num", "conflict_count_dedup"])
        return by_exp, by_round

    conf["timestamp"] = pd.to_datetime(conf["timestamp"])
    conf = add_round_num(conf)
    conf = conf.sort_values(["group", "experiment_id", "round_num", "timestamp"])

    gap = conf.groupby(["group", "experiment_id", "round_num"], observed=True)["timestamp"].diff().dt.total_seconds()
    conf["is_new_episode"] = gap.isna() | (gap > merge_gap_sec)

    by_round = (
        conf.groupby(["group", "experiment_id", "round_num"], observed=True)["is_new_episode"]
        .sum()
        .reset_index(name="conflict_count_dedup")
    )
    by_exp = (
        by_round.groupby(["group", "experiment_id"], observed=True)["conflict_count_dedup"]
        .sum()
        .reset_index()
        .rename(columns={"conflict_count_dedup": "total_conflict_dedup"})
    )
    return by_exp, by_round


def compute_signal_types(event_all: pd.DataFrame) -> pd.DataFrame:
    """拆解各組人類 / AI 發送的訊號內容：
    signal_type = "i_can"     -> 發送者要自己接手（不是交接）
    signal_type = "your_turn" -> 發送者把目標交給「對方」（human 發 your_turn = 交給AI；
                                   agent 發 your_turn = 交給人類）
    回傳每組 x 發送者 x 訊號類型的次數，並附上「交接對象」欄位方便閱讀。
    """
    sig = event_all[event_all["event_type"].isin(["human_signal", "agent_signal"])].copy()
    counts = (
        sig.groupby(["group", "triggered_by", "signal_type"], observed=True)
        .size()
        .reset_index(name="count")
    )

    def _recipient(row):
        if row["signal_type"] == "i_can":
            return "自己接手（不交接）"
        return "AI" if row["triggered_by"] == "human" else "人類"

    counts["hands_off_to"] = counts.apply(_recipient, axis=1)
    counts["sender"] = counts["triggered_by"].map({"human": "人類", "agent": "AI"})
    counts = counts[["group", "sender", "signal_type", "hands_off_to", "count"]]
    return counts.sort_values(["group", "sender", "signal_type"]).reset_index(drop=True)


ROLE_OTHER = {"human": "agent", "agent": "human"}
ROLE_LABEL = {"human": "人類", "agent": "AI"}


def _classify_movement(delta, threshold=MOVEMENT_STAY_THRESHOLD_PX):
    """delta = 訊號後距敵機距離 - 訊號當下距敵機距離。
    delta > threshold  -> 距離變大 -> 遠離敵機
    delta < -threshold -> 距離變小 -> 靠近／追擊敵機
    否則              -> 停留原地（距離變化在雜訊範圍內）
    """
    if pd.isna(delta):
        return "無法判斷"
    if delta > threshold:
        return "遠離敵機"
    if delta < -threshold:
        return "靠近／追擊敵機"
    return "停留原地"


def compute_signal_movement_response(
    event_all: pd.DataFrame,
    window_sec: float = MOVEMENT_WINDOW_SEC,
    stay_threshold_px: float = MOVEMENT_STAY_THRESHOLD_PX,
) -> pd.DataFrame:
    """針對每一次發送的訊號，觀察「發送訊號後 window_sec 秒內」發送者本人、以及
    另一方（訊號的接收對象）與敵機（flight）距離的變化，藉此判斷雙方是否真的依訊號
    做出對應動作：
      - 靠近／追擊敵機：距敵機距離明顯變小
      - 停留原地：距離變化在門檻內，沒有明顯移動
      - 遠離敵機：距敵機距離明顯變大
    做法：每一列 events.csv（不限事件類型）都帶有當下的 human_x/y、agent_x/y、
    flight_x/y 與 dist_human_flight / dist_agent_flight，訊號那一列本身的
    dist_*_flight 當作「訊號當下」基準值；再用 merge_asof 找出「訊號時間
    + window_sec 秒」當下最接近的那一列資料當作「訊號後」快照，兩者相減即為
    距離變化量。

    重要：往後找快照時，只在「同一架敵機（同一 flight_id）」的資料列裡找，
    不會跨到下一架敵機。因為敵機平均存活時間常常小於 window_sec，若不限制
    flight_id，「訊號後」快照很容易已經是下一架（位置全新、距離不相干）的
    敵機，量出來的距離變化會失真（甚至出現接近整個畫面對角線長度的離譜跳動）。
    限制在同一架敵機後，如果這架敵機在 window_sec 秒內就已經被擊落／被放過，
    「訊號後」快照就會停在它被處理的那一刻，這其實更貼近想問的問題：
    「這架敵機從被訊號提到、到落幕為止，兩人各自怎麼移動」。
    回傳每一次訊號一列的明細表。
    """
    need_cols = ["dist_human_flight", "dist_agent_flight", "human_x", "human_y", "agent_x", "agent_y"]
    ev = event_all.dropna(subset=need_cols).copy()
    ev["timestamp"] = pd.to_datetime(ev["timestamp"])

    sig = ev[ev["event_type"].isin(["human_signal", "agent_signal"])].copy()
    if sig.empty:
        return pd.DataFrame(columns=[
            "group", "experiment_id", "round_id", "flight_id", "timestamp",
            "sender", "signal_type", "hands_off_to",
            "sender_delta_dist", "sender_movement",
            "receiver", "receiver_delta_dist", "receiver_movement",
        ])
    sig = sig.rename(columns={
        "dist_human_flight": "dist_human_flight_at_signal",
        "dist_agent_flight": "dist_agent_flight_at_signal",
    })
    sig["t_after"] = sig["timestamp"] + pd.to_timedelta(window_sec, unit="s")

    rows = []
    for (g, exp, rnd, fid), grp in ev.groupby(["group", "experiment_id", "round_id", "flight_id"], observed=True):
        sub_sig = sig[
            (sig["group"] == g) & (sig["experiment_id"] == exp)
            & (sig["round_id"] == rnd) & (sig["flight_id"] == fid)
        ]
        if sub_sig.empty:
            continue
        ref = grp.sort_values("timestamp")[["timestamp", "dist_human_flight", "dist_agent_flight"]]
        merged = pd.merge_asof(
            sub_sig.sort_values("t_after"), ref, left_on="t_after", right_on="timestamp",
            direction="backward", suffixes=("", "_after"),
        )
        rows.append(merged)

    if not rows:
        return pd.DataFrame(columns=[
            "group", "experiment_id", "round_id", "flight_id", "timestamp",
            "sender", "signal_type", "hands_off_to",
            "sender_delta_dist", "sender_movement",
            "receiver", "receiver_delta_dist", "receiver_movement",
        ])

    out = pd.concat(rows, ignore_index=True)
    out["sender"] = out["triggered_by"]
    out["receiver"] = out["sender"].map(ROLE_OTHER)
    out["hands_off_to"] = np.where(
        out["signal_type"] == "i_can", "自己接手（不交接）", out["receiver"].map(ROLE_LABEL)
    )

    def _delta(ev_role):
        before = out[f"dist_{ev_role}_flight_at_signal"]
        after = out[f"dist_{ev_role}_flight"]
        return after - before

    out["sender_delta_dist"] = np.where(out["sender"] == "human", _delta("human"), _delta("agent"))
    out["receiver_delta_dist"] = np.where(out["receiver"] == "human", _delta("human"), _delta("agent"))
    out["sender_movement"] = out["sender_delta_dist"].apply(lambda d: _classify_movement(d, stay_threshold_px))
    out["receiver_movement"] = out["receiver_delta_dist"].apply(lambda d: _classify_movement(d, stay_threshold_px))

    cols = [
        "group", "experiment_id", "round_id", "flight_id", "timestamp",
        "sender", "signal_type", "hands_off_to",
        "sender_delta_dist", "sender_movement",
        "receiver", "receiver_delta_dist", "receiver_movement",
    ]
    return out[cols].sort_values(["group", "experiment_id", "round_id", "timestamp"]).reset_index(drop=True)


def summarize_movement_response(movement_df: pd.DataFrame) -> pd.DataFrame:
    """把 compute_signal_movement_response() 的明細，攤成「發送者反應」與「接收方反應」
    兩種角度的長格式次數表，並保留該次反應實際是「人類」還是「AI」做的（role），
    不把兩者混在一起，方便畫圖／樞紐分析時把人類跟 AI 的反應分開比較：
    欄位：group, signal_type, perspective（發送者自己 / 接收方（對方）), role（human/agent）,
          role_label（人類/AI）, movement, count
    """
    cols = ["group", "signal_type", "perspective", "role", "role_label", "movement", "count"]
    if movement_df.empty:
        return pd.DataFrame(columns=cols)
    a = movement_df.groupby(["group", "signal_type", "sender", "sender_movement"], observed=True).size()
    a = a.reset_index(name="count").rename(columns={"sender": "role", "sender_movement": "movement"})
    a.insert(2, "perspective", "發送者自己")
    b = movement_df.groupby(["group", "signal_type", "receiver", "receiver_movement"], observed=True).size()
    b = b.reset_index(name="count").rename(columns={"receiver": "role", "receiver_movement": "movement"})
    b.insert(2, "perspective", "接收方（對方）")
    out = pd.concat([a, b], ignore_index=True)
    out["role_label"] = out["role"].map(ROLE_LABEL)
    out = out[cols]
    return out.sort_values(["group", "signal_type", "perspective", "role"]).reset_index(drop=True)


def compute_last_signal_outcome(event_all: pd.DataFrame) -> pd.DataFrame:
    """針對每一回合「最後一次發送的訊號」，比對訊號當下的意思（i_can=自己來處理；
    your_turn=交給對方）跟該訊號所指的那架敵機（flight_id）最後實際的結果：
      - 由誰擊落（shot_hit 的 triggered_by）
      - 或被放過（flight_missed）
      - 或該回合結束前仍未有結果（unresolved，例如回合時間到）
    predicted_handler：依訊號語意「應該」由誰處理這架敵機。
    match：predicted_handler 是否等於 actual_handler（僅在敵機確實被擊落時才有意義）。
    回傳每個 (group, experiment_id, round_id) 一列（只涵蓋該回合有發送過訊號的情況）。
    """
    sig = event_all[event_all["event_type"].isin(["human_signal", "agent_signal"])].copy()
    if sig.empty:
        return pd.DataFrame(columns=[
            "group", "experiment_id", "round_id", "flight_id", "timestamp",
            "last_sender", "last_signal_type", "predicted_handler", "actual_handler", "match",
        ])
    sig["timestamp"] = pd.to_datetime(sig["timestamp"])
    idx = sig.groupby(["group", "experiment_id", "round_id"], observed=True)["timestamp"].idxmax()
    last_sig = sig.loc[idx].copy()
    last_sig["predicted_handler"] = np.where(
        last_sig["signal_type"] == "i_can", last_sig["triggered_by"], last_sig["triggered_by"].map(ROLE_OTHER)
    )

    hits = event_all.loc[
        (event_all["event_type"] == "shot_hit") & (event_all["triggered_by"].isin(["human", "agent"])),
        ["group", "experiment_id", "round_id", "flight_id", "triggered_by"],
    ].rename(columns={"triggered_by": "actual_handler"})
    missed = event_all.loc[
        event_all["event_type"] == "flight_missed", ["group", "experiment_id", "round_id", "flight_id"]
    ].copy()
    missed["actual_handler"] = "missed"
    outcome = pd.concat([hits, missed], ignore_index=True)
    outcome = outcome.drop_duplicates(subset=["group", "experiment_id", "round_id", "flight_id"], keep="first")

    merged = last_sig.merge(outcome, on=["group", "experiment_id", "round_id", "flight_id"], how="left")
    merged["actual_handler"] = merged["actual_handler"].fillna("unresolved")
    merged["match"] = merged["actual_handler"] == merged["predicted_handler"]
    merged = merged.rename(columns={"triggered_by": "last_sender", "signal_type": "last_signal_type"})

    cols = [
        "group", "experiment_id", "round_id", "flight_id", "timestamp",
        "last_sender", "last_signal_type", "predicted_handler", "actual_handler", "match",
    ]
    return merged[cols].sort_values(["group", "experiment_id", "round_id"]).reset_index(drop=True)


def summarize_last_signal_outcome(outcome_df: pd.DataFrame) -> pd.DataFrame:
    """依組別彙整 compute_last_signal_outcome() 的結果：
    有訊號的回合數、敵機確實被擊落的回合數（resolved）、其中預測命中的回合數與命中率、
    以及最後未被任何一方擊落（missed）、回合結束仍未有結果（unresolved）的回合數。
    """
    if outcome_df.empty:
        return pd.DataFrame(columns=[
            "group", "n_rounds_with_signal", "n_resolved", "n_predicted_match",
            "match_rate_among_resolved", "n_missed", "n_unresolved",
        ])
    rows = []
    for g in GROUP_ORDER:
        sub = outcome_df[outcome_df["group"] == g]
        n_rounds = len(sub)
        resolved = sub[sub["actual_handler"].isin(["human", "agent"])]
        n_resolved = len(resolved)
        n_match = int(resolved["match"].sum())
        n_missed = int((sub["actual_handler"] == "missed").sum())
        n_unresolved = int((sub["actual_handler"] == "unresolved").sum())
        rows.append({
            "group": g,
            "n_rounds_with_signal": n_rounds,
            "n_resolved": n_resolved,
            "n_predicted_match": n_match,
            "match_rate_among_resolved": round(n_match / n_resolved, 4) if n_resolved else np.nan,
            "n_missed": n_missed,
            "n_unresolved": n_unresolved,
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    experiment_all, round_all, event_all = load_all()
    print("experiment_all:", experiment_all.shape)
    print("round_all:", round_all.shape)
    print("event_all:", event_all.shape)
    print(experiment_all[["group", "experiment_id"]].to_string())
