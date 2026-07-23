# Human-AI Collaborative Game (Thesis Project)

這是一個為了人機協作研究而開發的 Pygame 遊戲。玩家將與一個 AI 代理合作，共同完成擊落目標的任務。系統會詳細記錄實驗過程中的所有互動事件，以供後續分析。

## 核心功能

- **即時協作玩法**: 玩家與 AI 代理在同一個遊戲環境中互動。
- **多種實驗情境**:
  - **No Signal**: 無法發送訊號。
  - **Human Dominant**: 僅人類可主動發送訊號。
  - **Agent Dominant**: 僅 AI 可主動發送訊號。
  - **Negotiation**: 雙方皆可發送訊號進行協商。
- **詳細資料記錄**:
  - 所有關鍵事件（如目標生成、射擊、失誤、訊號）都會被即時記錄到 CSV 檔案中。
  - 依據實驗條件與受試者 ID 自動建立獨立的資料夾。
- **多模態輸入**:
  - 支援鍵盤、滑鼠與遊戲手把（Joystick）操作。
  - 支援中文語音指令（例如「我來」、「給你」）來發送訊號。
- **動態 UI**: 包含遊戲模式選擇、教學引導、暫停選單等界面。

## 系統需求

- Python (建議 3.9 或以上版本)
- Pygame
- Vosk (用於語音辨識)
- SoundDevice

## 安裝與設定

1.  **安裝 Python**:
    請先確保您的電腦已安裝 Python。

2.  **安裝相依套件**:
    打開終端機 (Terminal / Command Prompt)，執行以下指令安裝所有必要的 Python 函式庫：
    ```bash
    pip install pygame vosk sounddevice
    ```

3.  **下載語音模型**:
    - 前往 Vosk Models 頁面下載中文模型（例如 `vosk-model-small-cn-0.22`）。
    - 將下載的檔案解壓縮。
    - 將解壓縮後的模型資料夾重新命名為 `vosk-model-small-cn-0.3`（或修改 `main.py` 中的 `self.voice_model_path` 路徑）。
    - 將此模型資料夾放到 `game/models/` 路徑底下。

## 如何運行

1.  切換到 `game` 資料夾目錄：
    ```bash
    cd "game"
    ```
2.  執行主程式：
    ```bash
    python main.py
    ```

遊戲啟動後，請在主畫面輸入受試者 ID，選擇實驗模式 (SIGNAL) 後點擊 "START" 開始。

## 檔案結構

```
collaborate_ball 2/
├── game/                   # 遊戲主程式目錄
│   ├── main.py             # 遊戲進入點與核心邏輯
│   ├── data_logger.py      # CSV 資料記錄模組
│   ├── voice_signal.py     # 語音辨識模組
│   ├── audio.py            # 音效管理
│   ├── ui_*.py             # 各式 UI 元件
│   ├── source/             # 存放圖片、音效等資源
│   └── models/             # 存放 Vosk 語音模型
└── data/                     # 所有實驗數據的輸出目錄 (會自動建立)
```

## 操作方式

- **移動**:
  - `W, A, S, D` 或 `方向鍵`
  - 遊戲手把左類比搖桿 (Left Stick)
- **射擊**:
  - `空白鍵`
  - 遊戲手把 `A` 鍵
- **發送訊號「我來！」**:
  - `C` 鍵
  - 遊戲手把 `RT` (右扳機)
  - 語音指令：「我來」、「我可以」、「交給我」
- **發送訊號「給你！」**:
  - `X` 鍵
  - 遊戲手把 `LT` (左扳機) 或 `Y` 鍵
  - 語音指令：「交給你」、「給你」、「你去」
