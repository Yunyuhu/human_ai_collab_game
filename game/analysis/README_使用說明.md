# Floating Rescue 實驗資料分析 — 使用說明

本資料夾包含兩部分：

1. **Python 分析程式**（`analyze.py` / `build_report.py`）— 彙整四組（Agent Dominant / Human
   Dominant / Negotiation / No Signal）所有實驗編號的 `experiment.csv` / `round.csv` /
   `events.csv`，輸出組間比較統計與圖表到 `combined_raw.xlsx`。
2. **Excel 即時連結設定**（Power Query）— 讓 Excel 直接連到 `game/data` 資料夾，之後每次新增
   實驗資料夾、按下「重新整理」，Excel 就會自動抓到最新資料，不必手動複製貼上。

這兩部分互相獨立，你可以只用其中一種，也可以兩者並用（Power Query 做即時瀏覽/樞紐分析，
Python 做統計檢定與圖表）。

---

## 一、Python 分析程式

### 檔案位置

建議把 `analysis/` 這個資料夾整個放在 `collaborate_ball 2/game/` 底下，維持這樣的相對結構：

```
collaborate_ball 2/
└── game/
    ├── data/                     ← 現有的實驗資料（不動）
    │   ├── Agent Dominant/...
    │   ├── Human Dominant/...
    │   ├── Negotiation/...
    │   └── No Signal/...
    └── analysis/                 ← 這次交付的內容
        ├── analyze.py
        ├── build_report.py
        ├── requirements.txt
        ├── combined_raw.xlsx     ← 已幫你跑過一次的結果
        └── charts/*.png
```

程式預設會抓 `analysis/` 上一層的 `data/` 資料夾（也就是 `game/data`），輸出也會寫回
`analysis/` 這一層，所以只要照上面的結構放，不用改路徑。

### 安裝套件（第一次使用）

在終端機（Terminal）執行：

```bash
cd "/Users/yun/Desktop/collaborate_ball 2/game/analysis"
pip3 install -r requirements.txt --break-system-packages
```

如果你想用獨立虛擬環境（跟 `game/.venv`、`backend/.venv` 分開），也可以：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 執行

```bash
python3 build_report.py
```

會重新掃描 `game/data` 底下所有組別、所有實驗編號，更新：

* `combined_raw.xlsx` — 內含 11 個工作表：`Charts`（22 張圖表）、`Raw_Experiment`、
  `Raw_Round`、`Raw_Events`（三種 CSV 的彙整原始資料，每列多了 `group` / `experiment_id`
  兩欄；`Raw_Experiment`／`Raw_Round` 另外併入了從 `events.csv` 還原出的 `human_hits` /
  `agent_hits` 擊中敵機次數，以及下面說明的 `total_conflict_dedup` / `conflict_count_dedup`
  欄位）、`Group_Summary_Experiment`、`Group_Summary_Round`（四組的平均值、標準差、樣本數，
  以及 Kruskal-Wallis 檢定的 H 值與 p 值）、`Signal_Type_Breakdown`（見下方第 16 張圖說明）、
  `Signal_Movement_Detail`／`Signal_Movement_Summary`（見下方第 20、21 張圖說明）、
  `Last_Signal_Outcome`／`Last_Signal_Outcome_Summary`（見下方第 22 張圖說明）。
* `charts/01~22_*.png` — 22 張圖表，分成 5 個指標家族 + 1 個訊號內容拆解 + 1 組衝突次數
  「原始 vs 去重複」比較 + 1 組「訊號後移動反應」與「最後一次訊號 vs 敵機最終處理結果」：

  | # | 檔名 | 內容 |
  |---|---|---|
  | 1 | `01_score_group_avg` | 各組平均總分（長條圖 ± SD） |
  | 2 | `02_score_round_growth` | 各組每回合平均總分（單圖 4 條組平均線，該回合原始值） |
  | 3 | `03_score_participant_growth` | 組內每位參與者每回合總分（2x2 小圖，每人一條細線） |
  | 4 | `04_hits_group_avg` | 各組人類 vs AI 擊中敵機平均數（分組長條） |
  | 5 | `05_hits_round_avg` | 各組每回合人類 vs AI 擊中敵機平均數（2x2 小圖，各 2 條線） |
  | 6 | `06_hits_participant_avg` | 組內每位參與者人類 vs AI 擊中敵機數（2x2 小圖，各人分組長條） |
  | 7 | `07_accuracy_group_avg` | 各組人類 vs AI 準確率（分組長條） |
  | 8 | `08_accuracy_round_avg` | 各組每回合人類 vs AI 準確率（2x2 小圖） |
  | 9 | `09_accuracy_participant_avg` | 組內每位參與者人類 vs AI 準確率（2x2 小圖，分組長條） |
  | 10 | `10_conflict_group_avg` | 各組平均衝突次數（長條圖 ± SD） |
  | 11 | `11_conflict_round_growth` | 各組每回合平均衝突次數（單圖 4 條組平均線，該回合原始值） |
  | 12 | `12_conflict_participant_growth` | 組內每位參與者每回合衝突次數（2x2 小圖） |
  | 13 | `13_signals_group_avg` | 各組人類 vs AI 訊號發送次數（分組長條） |
  | 14 | `14_signals_round_growth` | 各組每回合人類 vs AI 平均訊號發送次數（2x2 小圖，該回合原始值） |
  | 15 | `15_signals_participant_growth` | 組內每位參與者每回合人類 vs AI 訊號發送次數（2x2 小圖，每人兩條線：實線=人類／虛線=AI） |
  | 16 | `16_signal_type_breakdown` | **各組人類 / AI 發送的訊號內容拆解**（見下方說明） |
  | 17 | `17_conflict_compare_group_avg` | **各組平均衝突次數：原始 vs 去重複**（分組長條，見下方說明） |
  | 18 | `18_conflict_compare_round_avg` | **各組每回合衝突次數：原始 vs 去重複**（2x2 小圖，各 2 條線） |
  | 19 | `19_conflict_compare_participant` | **組內每位參與者每回合衝突次數：原始 vs 去重複**（2x2 小圖，每人兩條線：實線=原始／虛線=去重複） |
  | 20 | `20_signal_movement_sender` | **發送訊號後，發送者自己的移動反應**（2x2 小圖，見下方說明） |
  | 21 | `21_signal_movement_receiver` | **發送訊號後，接收方（對方）的移動反應**（2x2 小圖，見下方說明） |
  | 22 | `22_last_signal_vs_outcome` | **各組：最後一次訊號的預測 vs 該輪敵機最終處理結果**（見下方說明） |

  **重要更正**：所有「每回合」圖表畫的都是**該回合當下的原始值**（例如第 3 回合的總分就是
  第 3 回合實際得到的分數），**不是累積加總**。四組平均線／每位參與者的線都會隨回合上下
  波動，而不是單調遞增——這樣才能看出「哪一回合表現特別好或特別差」。

  ### 新增：衝突次數「連續衝突只算一次」欄位（`total_conflict_dedup` / `conflict_count_dedup`）

  **背景**：遊戲原始碼（`main.py`）裡，「準心重疊」造成的衝突有 1.5 秒的護欄期，護欄一過、
  若雙方仍黏在一起，就會馬上再記一次 `conflict` 事件；「人類射擊誤傷」造成的衝突也可能因
  快速連續開火而在很短時間內重複觸發。這代表原本的 `total_conflict`／`conflict_count`
  （直接取自 `experiment.csv`／`round.csv`，等於 `events.csv` 裡 `event_type=="conflict"`
  的原始筆數）其實會把「同一段黏在一起、持續好幾秒的衝突」拆成好幾筆，可能高估真正發生
  的衝突次數。

  **作法**：`analyze.py` 新增 `compute_conflicts_dedup()`，把 `events.csv` 中的 `conflict`
  事件依「同一回合內、時間戳記排序」處理：只要相鄰兩筆 `conflict` 事件的時間間隔
  **<= 2.0 秒**，就視為同一段連續衝突、只算一次；間隔超過 2.0 秒才算是新的一次衝突。
  這個 2.0 秒門檻是依遊戲原始碼中的懲罰／護欄時間（誤傷懲罰 1.0 秒、重疊護欄 1.5 秒）
  再加一點緩衝訂出來的，也用實際資料核對過：同一段衝突的相鄰事件間隔幾乎都落在
  1.0~1.5 秒，真正各自獨立的新衝突則間隔數秒到數十秒。如果想調整這個門檻，改
  `analyze.py` 最上面的 `CONFLICT_MERGE_GAP_SEC` 即可。

  **新欄位**（**不刪除、不覆蓋舊欄位**，兩者在 `Raw_Experiment` / `Raw_Round` /
  `Group_Summary_Experiment` / `Group_Summary_Round` 都並排存在，方便直接比較）：
  - `total_conflict_dedup`（`Raw_Experiment`）／`conflict_count_dedup`（`Raw_Round`）：
    去重複後的衝突次數。
  - 舊欄位 `total_conflict` / `conflict_count` 完全維持原樣，仍是原始（每次都算）的次數。

  **目前跑出來的結果（46 筆實驗，去重複門檻 2.0 秒）**：

  | 組別 | 原始平均衝突次數 | 去重複後平均衝突次數 | 減少比例 |
  |---|---|---|---|
  | Agent Dominant | 5.33 | 3.83 | -28% |
  | Human Dominant | 4.58 | 3.17 | -31% |
  | Negotiation | 10.25 | 5.50 | -46% |
  | No Signal | 8.40 | 5.00 | -40% |

  去重複後，四組間的差異幅度明顯縮小（Negotiation／No Signal 兩組原本的「原始衝突次數」
  最高，去重複後降幅也最大，代表這兩組較常出現「黏在一起好幾秒、被重複計次」的情況）。
  Kruskal-Wallis 檢定的結果也從邊緣趨勢變成完全不顯著：原始 `total_conflict`
  H=6.47、p≈0.091（僅邊緣顯著）；去重複後 `total_conflict_dedup` H=2.55、p≈0.466
  （不顯著）。也就是說，原本「四組衝突次數好像有點差異」的訊號，有相當大一部分其實是
  「同一段衝突被重複記錄的次數」造成的假象，把連續衝突合併計算一次之後，四組之間衝突
  次數的差異證據更加薄弱。

  ### 第 16 張圖：訊號內容拆解（我來 vs 換你）

  `events.csv` 裡每一次訊號（`human_signal` / `agent_signal`）都帶有 `signal_type`，只有
  兩種值：
  - **`i_can`**（我來）：發送者要**自己接手**目標，不是交接。
  - **`your_turn`**（換你）：發送者把目標**交給對方**——人類發 `your_turn` 就是「交給 AI」；
    AI 發 `your_turn` 就是「交給人類」。

  第 16 張圖用堆疊長條呈現：每組 x 每個發送者（人類／AI）一根柱子，柱子下半段（淺色）是
  「我來」次數，上半段（深色）是「換你」次數，柱子上直接標數字。`Signal_Type_Breakdown`
  工作表則是完整的明細表（`group` / `sender` / `signal_type` / `hands_off_to` / `count`），
  `hands_off_to` 欄位已經幫你把「換你」翻譯成實際交給的對象（人類或 AI），可以直接篩選、
  樞紐分析。No Signal 組因為完全沒有訊號資料，這張圖該組會是空白，屬於正常現象。

  ### 第 20、21 張圖：發送訊號後，雙方是否真的照訊號行動（移動反應）

  **問題**：發送「我來（`i_can`）」的人，是不是真的有衝上去接手？發送「換你
  （`your_turn`）」交出去的人，是不是真的有讓開／停手？收到「換你」的另一方，
  是不是真的有接手上前？

  **作法**：`analyze.py` 新增 `compute_signal_movement_response()`。每一次訊號事件
  本身就帶有當下「發送者／接收方與敵機的距離」（`dist_human_flight` /
  `dist_agent_flight`），以此為基準，往後找「同一架敵機（同一 `flight_id`）」
  之後最多 3 秒（`MOVEMENT_WINDOW_SEC`）內最新的一筆資料，算出距離變化量：
  - 距離明顯變小（> 40px，`MOVEMENT_STAY_THRESHOLD_PX`）→ **靠近／追擊敵機**
  - 距離變化在 ±40px 內 → **停留原地**
  - 距離明顯變大 → **遠離敵機**

  限制在「同一架敵機」內找資料很重要：因為敵機平均存活時間常常不到 3 秒，若不限制，
  3 秒後可能已經換成下一架全新位置的敵機，量出來的距離變化會失真。限制在同一架後，
  如果這架敵機提早被擊落／放過，就直接用它落幕那一刻的位置來算，更貼近「這架敵機
  從訊號提到、到落幕為止，兩人各自怎麼移動」。視窗長度、停留門檻都可以在 `analyze.py`
  開頭的 `MOVEMENT_WINDOW_SEC` / `MOVEMENT_STAY_THRESHOLD_PX` 調整。

  第 20 張圖是**發送者自己**的反應、第 21 張圖是**接收方（對方）**的反應，兩張都以
  2x2 小圖依組別呈現（No Signal 組沒有訊號，圖是空的，屬於正常現象）。**x 軸把「人類」
  跟「AI」明確拆開**（人類-我來 / 人類-換你 / AI-我來 / AI-換你），不會把兩者的反應
  混在一起平均——Agent Dominant 組只有 AI 會發訊號、Human Dominant 組只有人類會發
  訊號，所以這兩組各自會有兩根「人類」或「AI」的柱子顯示「—」（無資料，屬於正常
  現象，不是缺漏）；只有 Negotiation 組雙方都會發訊號，四根柱子都有資料，也是唯一
  能直接比較「同一組情境下，人類 vs AI 反應是否不同」的組別。每根柱子是 100% 堆疊
  長條（綠=靠近／追擊、灰=停留原地、紅=遠離敵機）。明細列在 `Signal_Movement_Detail`
  （每一次訊號一列）、彙整次數在 `Signal_Movement_Summary`（group x signal_type x
  角色（人類/AI，`role`／`role_label` 欄位）x 發送者/接收方 x 移動類型的次數）。

  **目前跑出來的結果（發送者自己「靠近／追擊敵機」的比例，依人類 / AI 分開）**：

  | 組別 | 發送者角色 | 我來（i_can）：靠近 | 換你（your_turn）：靠近 |
  |---|---|---|---|
  | Agent Dominant | AI | 92.4% | 63.7% |
  | Human Dominant | 人類 | 75.6% | 60.8% |
  | Negotiation | 人類 | 80.0% | 62.0% |
  | Negotiation | AI | 84.7% | 65.1% |

  **接收方（對方）「靠近／追擊敵機」的比例，依人類 / AI 分開**：

  | 組別 | 接收方角色 | 對方發「我來」時：靠近 | 對方發「換你」時：靠近 |
  |---|---|---|---|
  | Agent Dominant | 人類 | 77.8% | 73.4% |
  | Human Dominant | AI | 69.1% | 86.7% |
  | Negotiation | 人類 | 68.4% | 69.9% |
  | Negotiation | AI | 63.7% | 85.1% |

  幾個一致的規律：

  1. **「我來」時，發送者自己靠近／追擊敵機的比例（76~92%）都明顯高於「換你」時
     （60~65%）**，人類、AI 都一樣——換你時，發送者停留原地或遠離敵機的比例都明顯
     升高。也就是說，不論是人類還是 AI，「換你」訊號確實伴隨發送者本人的退讓行為，
     不是隨便發送卻沒有對應動作。人類跟 AI 在這件事上的差異不大（人類我來 76~80%、
     AI 我來 85~92%；人類換你 60~62%、AI 換你 64~66%），AI 自己來的時候略微更積極
     一點，但整體上人類、AI 遵守自己發出訊號的程度相當接近。

  2. **AI 收到「換你」時的反應，比人類收到「換你」時明確得多**：AI 被告知換你後
     靠近敵機的比例是 85~87%（Human Dominant、Negotiation 都一樣），而人類被告知
     換你後靠近的比例只有 70~73%（Agent Dominant、Negotiation 都一樣）——這是唯一
     出現明顯人類 vs AI 差異的地方。換句話說，**AI 對「換你」訊號的反應比人類更
     果斷、更一致**；人類收到換你的訊號後，靠近敵機的比例只比單純旁觀對方「我來」
     時（68~78%）高一點點，代表人類即使沒被明確叫「換你」，本來就有一定機率主動
     上前，「換你」訊號帶給人類的額外推力比帶給 AI 的小。

  整體來說，訊號的語意（自己來 / 交給你）跟實際移動行為的方向是吻合的，訊號並非
  裝飾性的、雙方確實會依訊號調整自己要不要靠近敵機；差異主要出現在「接收換你訊號」
  這一端——AI 比人類更會確實回應「換你」的指示。

  ### 第 22 張圖：最後一次訊號 vs 該輪敵機最終由誰處理

  **問題**：每一回合最後一次發送的訊號，說好是「我來」還是「換你」，最後真的是那個人
  處理掉那架敵機嗎？

  **作法**：`analyze.py` 新增 `compute_last_signal_outcome()`。取每個
  (組別, 實驗編號, 回合) 裡時間戳記最晚的一次訊號，依訊號語意算出「預測應該由誰
  處理」（`predicted_handler`：我來 → 發送者本人；換你 → 對方）；再用訊號當下的
  `flight_id`，去 `events.csv` 找同一架敵機最後的結果：被擊中（`shot_hit` 的
  `triggered_by`）或被放過（`flight_missed`）。兩者相符即為「預測命中」。
  明細在 `Last_Signal_Outcome`（每回合一列）、彙整在 `Last_Signal_Outcome_Summary`。

  **目前跑出來的結果（僅計入「該回合有發送過訊號」的回合，每組 72 回合 = 12 位
  參與者 x 6 回合）**：

  | 組別 | 有結果的回合（敵機確實被擊落） | 其中預測命中 | 命中率 | 敵機被放過的回合 |
  |---|---|---|---|---|
  | Agent Dominant | 53 / 72 | 46 | 86.8% | 19（26%） |
  | Human Dominant | 51 / 72 | 42 | 82.4% | 21（29%） |
  | Negotiation | 57 / 72 | 49 | 86.0% | 15（21%） |

  三組的「最後一次訊號」預測命中率都落在 82~87% 之間，代表訊號雖然偶爾會落空
  （有 8~12% 的回合，最後真正擊落敵機的人跟訊號說的不一樣），但整體來說是相當
  可靠的預測——回合最後一次的訊號，多數時候確實對應到誰會接手處理那架敵機。三組
  另外都有約兩到三成的回合，最後一架敵機沒有任何一方擊中（被放過），這部分不算
  「預測錯誤」，只是那架敵機最終沒人處理掉。

**之後只要資料夾裡新增了實驗編號（新的受試者跑完實驗），重新執行一次
`python3 build_report.py` 就會自動包含新資料，不需要改程式。**

### 資料排除說明

目前分析已**撇除以下 6 筆實驗編號**（依你的要求排除，不計入任何統計與圖表）：

`33`、`35`、`42`、`44`、`49`、`50`

這個排除清單寫在 `analyze.py` 檔案開頭的 `EXCLUDE_IDS` 變數裡（`load_all()` 掃描資料夾時會
直接跳過這些編號的資料夾）。之後如果要調整排除名單，直接修改 `EXCLUDE_IDS` 這個集合即可，
例如：

```python
EXCLUDE_IDS = {"33", "35", "42", "44", "49", "50"}
```

若之後不需要排除任何資料，把這行改成空集合 `EXCLUDE_IDS = set()` 再重新執行
`python3 build_report.py` 即可。

### 目前跑出來的重點（排除上述 6 筆後，共 46 筆實驗；各組樣本數 n=10~12）

* 四組的總分、衝突次數，用 Kruskal-Wallis 檢定都**沒有**達到統計顯著（總分 p ≈ 0.069、
  衝突次數 p ≈ 0.091），僅能說有邊緣性的趨勢，尚不足以下定論。
* **AI 準確率**在四組間的差異達統計顯著（p ≈ 0.008）：Human Dominant 與 Negotiation 組的
  AI 準確率（約 0.62）高於 Agent Dominant 組（約 0.55）。人類準確率四組間則沒有顯著差異
  （p ≈ 0.83）。
* 訊號發送次數的組間差異在統計上顯著（p < 0.001），但這主要是**實驗設計本身**造成的：
  No Signal 組本來就不發訊號、Agent Dominant 組只有 AI 發訊號、Human Dominant 組幾乎只有
  人類發訊號，這不是「發現」，而是操弄檢查（manipulation check）通過的證據。

---

## 二、Excel 即時連結（Power Query「從資料夾」）

這一步只需要在 Excel 裡設定**一次**，之後每次按「全部重新整理」，Excel 就會重新讀取
`game/data` 資料夾目前的內容（包含新增的實驗編號），不需要重跑 Python、也不需要重新匯入。

> 需要 Microsoft 365 版本的 Excel for Mac（有「取得資料」/Get Data 功能）。若你的 Excel
> 版本沒有「從資料夾」選項，請改用下面 Python 產生的 `combined_raw.xlsx`，手動重新整理。

### 步驟

1. 開一個新的 Excel 活頁簿。
2. 上方選單 **資料 (Data) → 取得資料 (Get Data) → 從檔案 (From File) → 從資料夾
   (From Folder)**。
3. 路徑貼上：`/Users/yun/Desktop/collaborate_ball 2/game/data`，按「確定」。
4. 預覽視窗會列出資料夾底下（含子資料夾）所有檔案。**不要按「載入」，按「轉換資料
   (Transform Data)」**，開啟 Power Query 編輯器。
5. 在 Power Query 編輯器左上角，點選 **常用 (Home) → 進階編輯器 (Advanced Editor)**，
   把裡面原本的內容全部刪掉，貼上下面三段程式碼**其中一段**（分別對應
   experiment.csv / round.csv / events.csv）。建議做法：
   - 先用這一步驟建立 `Experiment_Raw` 這個查詢（貼上第一段程式碼）。
   - 在查詢清單按右鍵 → 「複製 (Duplicate)」兩次，分別改名成 `Round_Raw`、
     `Events_Raw`，再對這兩份複本各自打開進階編輯器，換成第二段、第三段程式碼。

**如果路徑不是 `/Users/yun/Desktop/collaborate_ball 2/game/data`，請把三段程式碼第一行的
路徑改成你實際的路徑。**

#### 查詢 1：Experiment_Raw

```powerquery-m
let
    Source = Folder.Files("/Users/yun/Desktop/collaborate_ball 2/game/data"),
    FilteredRows = Table.SelectRows(Source, each [Name] = "experiment.csv"),
    AddedPathParts = Table.AddColumn(FilteredRows, "PathParts",
        each List.Select(Text.Split(Text.Replace([Folder.Path], "\", "/"), "/"), each Text.Trim(_) <> "")),
    AddedGroup = Table.AddColumn(AddedPathParts, "Group",
        each [PathParts]{List.PositionOf([PathParts], "data") + 1}),
    AddedExperimentID = Table.AddColumn(AddedGroup, "ExperimentID",
        each [PathParts]{List.PositionOf([PathParts], "data") + 2}),
    ParsedCSV = Table.AddColumn(AddedExperimentID, "Data",
        each Csv.Document([Content], [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv])),
    PromotedHeaders = Table.TransformColumns(ParsedCSV, {"Data", each Table.PromoteHeaders(_, [PromoteAllScalars=true])}),
    Selected = Table.SelectColumns(PromotedHeaders, {"Group", "ExperimentID", "Data"}),
    Expanded = Table.ExpandTableColumn(Selected, "Data",
        {"user_id", "exp_start_time", "exp_end_time", "total_score", "total_errors",
         "human_total_accuracy", "agent_total_accuracy", "total_signals",
         "human_total_signals", "agent_total_signals", "total_conflict",
         "total_rounds", "notes"}),
    ChangedType = Table.TransformColumnTypes(Expanded, {
        {"total_score", Int64.Type}, {"total_errors", Int64.Type},
        {"human_total_accuracy", type number}, {"agent_total_accuracy", type number},
        {"total_signals", Int64.Type}, {"human_total_signals", Int64.Type},
        {"agent_total_signals", Int64.Type}, {"total_conflict", Int64.Type},
        {"total_rounds", Int64.Type}
    })
in
    ChangedType
```

#### 查詢 2：Round_Raw

```powerquery-m
let
    Source = Folder.Files("/Users/yun/Desktop/collaborate_ball 2/game/data"),
    FilteredRows = Table.SelectRows(Source, each [Name] = "round.csv"),
    AddedPathParts = Table.AddColumn(FilteredRows, "PathParts",
        each List.Select(Text.Split(Text.Replace([Folder.Path], "\", "/"), "/"), each Text.Trim(_) <> "")),
    AddedGroup = Table.AddColumn(AddedPathParts, "Group",
        each [PathParts]{List.PositionOf([PathParts], "data") + 1}),
    AddedExperimentID = Table.AddColumn(AddedGroup, "ExperimentID",
        each [PathParts]{List.PositionOf([PathParts], "data") + 2}),
    ParsedCSV = Table.AddColumn(AddedExperimentID, "Data",
        each Csv.Document([Content], [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv])),
    PromotedHeaders = Table.TransformColumns(ParsedCSV, {"Data", each Table.PromoteHeaders(_, [PromoteAllScalars=true])}),
    Selected = Table.SelectColumns(PromotedHeaders, {"Group", "ExperimentID", "Data"}),
    Expanded = Table.ExpandTableColumn(Selected, "Data",
        {"user_id", "round_id", "round_start_time", "round_end_time", "round_duration",
         "round_score", "round_errors", "human_accuracy", "agent_accuracy",
         "enemy_spawn_count", "conflict_count", "human_signal_count", "agent_signal_count"}),
    ChangedType = Table.TransformColumnTypes(Expanded, {
        {"round_duration", type number}, {"round_score", Int64.Type},
        {"round_errors", Int64.Type}, {"human_accuracy", type number},
        {"agent_accuracy", type number}, {"enemy_spawn_count", Int64.Type},
        {"conflict_count", Int64.Type}, {"human_signal_count", Int64.Type},
        {"agent_signal_count", Int64.Type}
    })
in
    ChangedType
```

#### 查詢 3：Events_Raw

```powerquery-m
let
    Source = Folder.Files("/Users/yun/Desktop/collaborate_ball 2/game/data"),
    FilteredRows = Table.SelectRows(Source, each [Name] = "events.csv"),
    AddedPathParts = Table.AddColumn(FilteredRows, "PathParts",
        each List.Select(Text.Split(Text.Replace([Folder.Path], "\", "/"), "/"), each Text.Trim(_) <> "")),
    AddedGroup = Table.AddColumn(AddedPathParts, "Group",
        each [PathParts]{List.PositionOf([PathParts], "data") + 1}),
    AddedExperimentID = Table.AddColumn(AddedGroup, "ExperimentID",
        each [PathParts]{List.PositionOf([PathParts], "data") + 2}),
    ParsedCSV = Table.AddColumn(AddedExperimentID, "Data",
        each Csv.Document([Content], [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv])),
    PromotedHeaders = Table.TransformColumns(ParsedCSV, {"Data", each Table.PromoteHeaders(_, [PromoteAllScalars=true])}),
    Selected = Table.SelectColumns(PromotedHeaders, {"Group", "ExperimentID", "Data"}),
    Expanded = Table.ExpandTableColumn(Selected, "Data",
        {"user_id", "round_id", "timestamp", "event_type", "flight_id",
         "flight_x", "flight_y", "human_x", "human_y", "agent_x", "agent_y",
         "dist_human_flight", "dist_agent_flight", "dist_human_agent",
         "triggered_by", "signal_type", "dir_ratio", "flight_speed", "flight_angle",
         "human_speed", "human_direction", "agent_speed", "agent_direction"})
in
    Expanded
```

> `events.csv` 資料量較大（目前約 2.2 萬列），若電腦跑起來覺得慢，可以在
> `Table.SelectRows` 那一步先篩選你需要的 `event_type`（例如只留 `agent_signal` /
> `shot_miss`），減少載入的資料量。

6. 三個查詢都設定完成後，在每個查詢按 **關閉並載入 (Close & Load)**，選「僅建立連線」
   或「載入至工作表」都可以（若要直接建樞紐分析表，選「只建立連線」再從
   插入 (Insert) → 樞紐分析表 (PivotTable) 選這三個查詢當資料來源即可）。

7. 之後每次資料夾新增實驗編號，只要在 Excel 按 **資料 (Data) → 全部重新整理
   (Refresh All)**，三個查詢跟所有以它們為來源的樞紐分析表/圖表都會自動更新。

### 用這三個表做「四組比較」的樞紐分析表

以 `Experiment_Raw` 為例：

1. 插入 (Insert) → 樞紐分析表 (PivotTable)，資料來源選 `Experiment_Raw`。
2. **列 (Rows)** 拖入 `Group`。
3. **值 (Values)** 拖入 `total_score`、`human_total_accuracy`、`agent_total_accuracy`、
   `total_conflict`，並把彙總方式改成「平均值」。
4. 插入 (Insert) → 樞紐分析圖 (PivotChart)，就能得到一張會隨資料更新的長條圖。

---

## 檔案清單

| 檔案 | 說明 |
|---|---|
| `analyze.py` | 讀取與彙整 CSV 的核心函式（載入資料、計算組間統計、還原擊中次數、衝突去重複、訊號移動反應、最後訊號比對） |
| `build_report.py` | 產生 22 張圖表 PNG 與 `combined_raw.xlsx`，執行進入點 |
| `requirements.txt` | Python 套件需求 |
| `combined_raw.xlsx` | 目前跑出的彙整報告（46 個實驗、4 組、22 張圖表；已撇除編號 33、35、42、44、49、50 共 6 筆） |
| `charts/` | 22 張個別圖表 PNG（檔名對照見上方表格） |
