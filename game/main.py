import sys
import random
import math
import os
from pathlib import Path
import datetime as dt
import time
from typing import Optional, Dict
import pygame as pg
from enum import Enum, auto

import api_client
from audio import AudioManager
from ui_mode_selector import ModeSelector
from ui_signal_selector import SignalSelector
from voice_signal import VoiceSignalListener
from ui_intro_overlay import IntroOverlay

# === 基本設定 ===
WIDTH, HEIGHT = 1280, 720
FPS = 60

# 顏色
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (80, 80, 80)
LIGHT_GRAY = (150, 150, 150)
BLUE = (100, 180, 255)
ORANGE = (255, 170, 120)
BG_COLOR = (20, 20, 30)

# 遊戲設定
ROUND_DURATION_MS = 60_000  # 每回合 60 秒
TOTAL_ROUNDS = 3

PADDLE_W, PADDLE_H = 100, 20
BALL_R = 10

# 新增協作 / 友火相關參數
SHOOT_RANGE = 120                 # 保留備用（不直接用於內圈判定）
INNER_SHOOT_FACTOR = 1.0 / 3.0    # 只允許在準心內圈的 1/3 開火
EXPLOSION_VISUAL_SCALE = 1.25     # 爆炸視覺放大倍率
VISUAL_Y_OFFSET = -2               # 視覺效果下移微調
SIGNAL_ICON_DURATION = 0.5        # 訊號圖示顯示時間（秒）
FRIENDLY_FIRE_RADIUS = 80         # 開火時若另一準心在此半徑內視為友火風險（像素）
FRIENDLY_FIRE_PENALTY_SEC = 1.0   # 友火造成的干擾時間（秒） -> 1 秒
OVERLAP_PENALTY_SEC = 1.5         # 準心重疊造成的被動干擾時間（秒）


class GameState(Enum):
    HOME = auto()
    ROUND = auto()
    BREAK = auto()
    DONE = auto()


# condition 對照表：編號 -> (內部代碼, 顯示文字)
CONDITIONS = {
    1: ("no_signal", "No Signal"),
    2: ("human_dom", "Human Dominant"),
    3: ("agent_dom", "Agent Dominant"),
    4: ("negotiation", "Negotiation"),
}

CONDITION_BY_MODE = {
    "no_signal": 1,
    "human_dom": 2,
    "agent_dom": 3,
    "negotiation": 4,
}


def draw_text(surface, text, font, color, pos, center=False):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    surface.blit(img, rect)


class Game:
    def __init__(self):
        pg.init()
        pg.joystick.init()
        try:
            pg.mixer.init()
        except Exception as e:
            print("Audio init failed:", e)
        global WIDTH, HEIGHT
        # 視窗模式（保留標題列），允許調整大小
        self.screen = pg.display.set_mode((WIDTH, HEIGHT), pg.RESIZABLE)
        # 取得實際視窗大小，覆蓋全域常數，讓 UI 依視窗尺度調整
        WIDTH, HEIGHT = self.screen.get_size()
        self.clock = pg.time.Clock()

        # 字型
        self.font_large = pg.font.SysFont("arial", 40)
        self.font_medium = pg.font.SysFont("arial", 28)
        self.font_small = pg.font.SysFont("arial", 22)
        self.font_tiny = pg.font.SysFont("arial", 18)

        # 路徑 / 音效
        self.base_dir = Path(__file__).resolve().parent
        self.audio = AudioManager(str(self.base_dir))
        self.intro_overlay = IntroOverlay(
            [
                self.base_dir / "source" / "game_info1.png",
                self.base_dir / "source" / "game_info2.png",
                self.base_dir / "source" / "game_info3.png",
                self.base_dir / "source" / "game_info4.png",
            ]
        )
        self.voice_listener = None
        self.voice_model_path = self.base_dir / "models" / "vosk-model-small-cn-0.3"
        self.init_voice_listener()
        self.show_intro = False

        # 載入兩個準心圖（human_crosshair.png, ai_crosshair.png）並依 scale_factor 縮放
        self.human_cross_img = None
        self.human_cross_img_base = None
        self.human_cross_img_left = None
        self.human_cross_img_right = None
        self.human_cross_img_my = None
        self.ai_cross_img = None
        self.ai_cross_img_base = None
        self.ai_cross_img_left = None
        self.ai_cross_img_right = None
        self.ai_cross_img_my = None
        self.target_img = None
        self.ball_radius = BALL_R
        try:
            human_path = self.base_dir / "source" / "human_crosshair.png"
            human_left_path = self.base_dir / "source" / "human_your_left.png"
            human_right_path = self.base_dir / "source" / "human_your_right.png"
            human_my_path = self.base_dir / "source" / "human_my.png"
            ai_path = self.base_dir / "source" / "agent_crosshair.png"
            agent_left_path = self.base_dir / "source" / "agent_your_left.png"
            agent_right_path = self.base_dir / "source" / "agent_your_right.png"
            agent_my_path = self.base_dir / "source" / "agent_my.png"
            target_path = self.base_dir / "source" / "fighter.png"
            # 以 128x128 為基準再乘上縮放因子
            scale_factor = 1.2
            target_size = int(128 * scale_factor)
            def load_scaled_image(path):
                img = pg.image.load(str(path)).convert_alpha()
                w, h = img.get_width(), img.get_height()
                if w > 0 and h > 0:
                    scale = target_size / max(w, h)
                    new_w = max(1, int(w * scale))
                    new_h = max(1, int(h * scale))
                    if new_w != w or new_h != h:
                        img = pg.transform.smoothscale(img, (new_w, new_h))
                return img
            if human_path.exists():
                img_h = load_scaled_image(human_path)
                self.human_cross_img = img_h
                self.human_cross_img_base = img_h
            if human_left_path.exists():
                img_hl = load_scaled_image(human_left_path)
                self.human_cross_img_left = img_hl
            if human_right_path.exists():
                img_hr = load_scaled_image(human_right_path)
                self.human_cross_img_right = img_hr
            if human_my_path.exists():
                img_hm = load_scaled_image(human_my_path)
                self.human_cross_img_my = img_hm
            if ai_path.exists():
                img_a = load_scaled_image(ai_path)
                self.ai_cross_img = img_a
                self.ai_cross_img_base = img_a
            if agent_left_path.exists():
                img_al = load_scaled_image(agent_left_path)
                self.ai_cross_img_left = img_al
            if agent_right_path.exists():
                img_ar = load_scaled_image(agent_right_path)
                self.ai_cross_img_right = img_ar
            if agent_my_path.exists():
                img_am = load_scaled_image(agent_my_path)
                self.ai_cross_img_my = img_am
            if target_path.exists():
                img_t = pg.image.load(str(target_path)).convert_alpha()
                max_dim = max(img_t.get_width(), img_t.get_height())
                desired = 65
                if max_dim != desired and max_dim > 0:
                    scale = desired / max_dim
                    img_t = pg.transform.smoothscale(
                        img_t,
                        (max(1, int(img_t.get_width() * scale)), max(1, int(img_t.get_height() * scale))),
                    )
                self.target_img = img_t
                self.ball_radius = max(1, int(max(img_t.get_width(), img_t.get_height()) / 2))
            if not (self.human_cross_img or self.ai_cross_img):
                print("human_crosshair.png / ai_crosshair.png not found in source/, will draw procedural crosshairs.")
        except Exception as e:
            print("Failed to load crosshair images:", e)
            self.human_cross_img = None
            self.ai_cross_img = None
            self.target_img = None
            self.ball_radius = BALL_R

        if self.intro_overlay:
            try:
                self.intro_overlay.set_practice_assets(self.human_cross_img_base, self.target_img)
                self.intro_overlay.set_practice_signal_assets(
                    self.human_cross_img_my,
                    self.human_cross_img_left,
                    self.human_cross_img_right,
                )
            except Exception:
                pass

        # 狀態相關
        self.state = GameState.HOME
        self.running = True
        self.pending_start = False
        self.countdown_active = False
        self.countdown_end_time = 0.0
        self.human_icon_until = 0.0
        self.joystick_axes = []
        self.lt_latched = False
        self.rt_latched = False

        self.lt_prev = None
        self.rt_prev = None

        self.kx_latched = False
        self.kc_latched = False
        self.agent_icon_until = 0.0

        # Home 畫面輸入
        # 移除手動輸入欄位：首頁只保留 Start 按鈕
        self.start_button_rect = pg.Rect(WIDTH // 2 - 130, 540, 260, 60)

        # 實驗與回合資料
        self.current_user_id = None      # 真的開始實驗後才設定
        self.condition_code = None       # 1~4
        self.signal_mode = "negotiation"
        self.current_round = 0
        self.total_rounds = TOTAL_ROUNDS
        self.exp_start_iso: Optional[str] = None
        self.exp_logged = False

        # 回合內的統計
        self.round_score = 0
        self.round_errors = 0
        self.round_collisions = 0
        self.round_ball_spawn = 0
        self.round_signal_sent = 0
        self.round_ball_catch = 0
        self.round_ball_miss = 0
        self.total_score = 0
        self.total_errors = 0

        # 計時
        self.round_start_ms = None
        self.round_start_iso: Optional[str] = None
        self.round_end_iso: Optional[str] = None

        # 球與 paddle
        self.reset_round_objects()
        self.conflict_flash_ms = 0  # paddles 衝突後的閃爍計時

        # UI 按鈕（回合中）
        self.mode_options = {
            "agent_only": "AGENT ONLY",
            "human_only": "HUMAN ONLY",
            "both": "BOTH",
        }
        self.control_mode = "both"
        self.mode_selector = ModeSelector(
            rect=pg.Rect(12, 10, 250, 28),
            font=self.font_tiny,
            options=self.mode_options,
            initial_key=self.control_mode,
        )
        self.signal_options = {
            "no_signal": "No Signal",
            "human_dom": "Human Dominant",
            "agent_dom": "Agent Dominant",
            "negotiation": "Negotiation",
        }
        self.signal_selector = SignalSelector(
            rect=pg.Rect(264, 10, 250, 28),
            font=self.font_tiny,
            options=self.signal_options,
            initial_key=self.signal_mode,
        )
        self.info_button_rect = pg.Rect(0, 0, 28, 28)
        self.info_button_rect.topright = (WIDTH - 12, 10)

        # 搖桿支援
        self.joystick = None
        self.joystick_id = None
        self.joystick_deadzone = 0.25
        self.joystick_debug_buttons = True
        self.joystick_debug_axes = True
        self.joystick_debug_next_dump = 0.0
        self.lt_rest = None
        self.rt_rest = None
        self.list_joysticks()
        self.attach_first_joystick()

    # --- 共用邏輯 ---

    def reset_round_objects(self):
        """重置目標與準心等物件"""
        self.reset_ball_random()
        # 初始位置避免重疊：左右偏移確保不在同一位置
        offset = 100
        self.human_x = max(50, WIDTH // 2 - offset)
        self.human_y = int(HEIGHT * 0.82)
        self.agent_x = min(WIDTH - 50, WIDTH // 2 + offset)
        self.agent_y = int(HEIGHT * 0.75)
        self.hit_cooldown_ms = 0

        # 改為使用爆炸效果（取代子彈）
        self.explosions = []  # each: {"x","y","t","dur","r","owner"}
        self.explosion_duration = 0.28
        self.explosion_radius = 48

        # 射擊冷卻
        self.last_human_shot = 0.0
        self.human_shot_cooldown = 0.25
        self.last_ai_shot = 0.0
        self.ai_shot_cooldown = 0.5
        self.ai_track_until = 0.0
        self.ai_idle_until = 0.0
        self.ai_slow_until = 0.0
        self.ai_slow_factor = 1.0
        self.ai_aggressive_until = 0.0
        self.human_my_block_until = 0.0
        self.ai_passive_until = 0.0
        self.hide_mode_ui = False
        self.signal_sent_for_ball = False

        # 友火 / 干擾狀態
        self.human_penalty_until = 0.0
        self.ai_penalty_until = 0.0
        # flash / freeze 狀態（ms）
        self.human_flash_ms = 0
        self.ai_flash_ms = 0
        self.conflict_freeze_ms = 0
        # 衝突後的護欄期（ms）：暫停後允許短暫自動柔性分離（預設 0；會在發生衝突時設為 1000ms）
        self.post_conflict_guard_ms = 0
        self.human_icon_until = 0.0
        if self.human_cross_img_base is not None:
            self.human_cross_img = self.human_cross_img_base
        self.lt_latched = False
        self.rt_latched = False
        self.kx_latched = False
        self.kc_latched = False
        self.lt_prev = None
        self.rt_prev = None
        self.joystick_axes = []

    def reset_round_stats(self):
        self.round_score = 0
        self.round_errors = 0
        self.round_collisions = 0
        self.round_ball_spawn = 0
        self.round_signal_sent = 0
        self.round_ball_catch = 0
        self.round_ball_miss = 0
        self.round_start_ms = pg.time.get_ticks()
        self.round_start_iso = dt.datetime.utcnow().isoformat() + "Z"
        self.reset_round_objects()
        self.conflict_flash_ms = 0

    def get_elapsed_ms(self):
        """回傳本回合已經過的毫秒數（扣掉暫停時間）"""
        if self.round_start_ms is None:
            return 0
        now = pg.time.get_ticks()
        return now - self.round_start_ms

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
        if self.voice_listener:
            self.voice_listener.stop()
        pg.quit()
        sys.exit()

    # --- 事件處理 ---

    def handle_events(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.running = False
            elif event.type == pg.VIDEORESIZE:
                self.handle_resize(event)
            elif event.type == pg.JOYDEVICEADDED:
                self.attach_joystick(event.device_index)
            elif event.type == pg.JOYDEVICEREMOVED:
                self.detach_joystick(event.instance_id)
            if getattr(self, "show_intro", False):
                result = self.intro_overlay.handle_event(event)
                if result == "close":
                    self.show_intro = False
                    if self.pending_start or self.state == GameState.ROUND:
                        self.start_countdown()
                if result:
                    continue
            if getattr(self, "countdown_active", False):
                continue

            if self.state == GameState.HOME:
                self.handle_events_home(event)
            elif self.state == GameState.ROUND:
                self.handle_events_round(event)
            elif self.state == GameState.BREAK:
                self.handle_events_break(event)
            elif self.state == GameState.DONE:
                self.handle_events_done(event)

    def handle_events_home(self, event):
        # 首頁只保留 Start 按鈕（假設 self.start_button_rect 已建立）
        import pygame as pg
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            if getattr(self, "start_button_rect", None) and self.start_button_rect.collidepoint(event.pos):
                self.try_start_experiment()
                self.intro_overlay.index = 0
                self.show_intro = True
        if event.type == pg.KEYDOWN:
            # Enter 鍵也可啟動
            if event.key == pg.K_RETURN or event.key == pg.K_KP_ENTER:
                self.try_start_experiment()
                self.intro_overlay.index = 0
                self.show_intro = True
        if event.type == pg.JOYBUTTONDOWN:
            if event.button == 0:
                self.try_start_experiment()
                self.intro_overlay.index = 0
                self.show_intro = True

    def handle_resize(self, event):
        """視窗縮放時重新取得尺寸，讓 UI 保持置中。"""
        global WIDTH, HEIGHT
        WIDTH, HEIGHT = event.w, event.h
        self.screen = pg.display.set_mode((WIDTH, HEIGHT), pg.RESIZABLE)
        self.mode_selector.set_position(12, 10)
        self.signal_selector.set_position(self.mode_selector.rect.right + 12, 10)
        self.info_button_rect.topright = (WIDTH - 12, 10)

    def init_voice_listener(self):
        model_path = self.voice_model_path
        if not model_path.exists():
            candidates = sorted((self.base_dir / "models").glob("vosk-model-small-cn-*"))
            if candidates:
                model_path = candidates[0]
                self.voice_model_path = model_path
            else:
                print("Voice model not found:", self.voice_model_path)
                return
        phrase_map = {
            "我来": "human_my",
            "我可以": "human_my",
            "給我": "human_my",
            "教給我": "human_my",
            "交給我": "human_my",
            "交给你": "human_your",
            "教给你": "human_your",
            "你": "human_your",
            "給你": "human_your",
            "你去": "human_your",
        }
        self.voice_listener = VoiceSignalListener(
            model_path,
            phrase_map,
            debug=True,
        )
        self.voice_listener.start()

    def attach_first_joystick(self):
        if pg.joystick.get_count() <= 0:
            return
        self.attach_joystick(0)

    def list_joysticks(self):
        try:
            count = pg.joystick.get_count()
            print(f"Joystick count: {count}")
            for i in range(count):
                joy = pg.joystick.Joystick(i)
                joy.init()
                print(f"Joystick[{i}]: {joy.get_name()}")
        except Exception as e:
            print("List joysticks failed:", e)

    def attach_joystick(self, device_index):
        if self.joystick is not None:
            return
        try:
            joy = pg.joystick.Joystick(device_index)
            joy.init()
            self.joystick = joy
            if hasattr(joy, "get_instance_id"):
                self.joystick_id = joy.get_instance_id()
            else:
                self.joystick_id = joy.get_id()
            print(f"Joystick connected: {joy.get_name()}")
        except Exception as e:
            print("Joystick init failed:", e)

    def detach_joystick(self, instance_id):
        if self.joystick is None:
            return
        if instance_id != self.joystick_id:
            return
        try:
            self.joystick.quit()
        except Exception:
            pass
        self.joystick = None
        self.joystick_id = None
        print("Joystick disconnected")

    def read_joystick_move(self):
        if self.joystick is None:
            return 0.0, 0.0
        dx = 0.0
        dy = 0.0
        try:
            num_axes = self.joystick.get_numaxes()
            if num_axes >= 2:
                x = self.joystick.get_axis(0)
                y = self.joystick.get_axis(1)
                if abs(x) < self.joystick_deadzone:
                    x = 0.0
                if abs(y) < self.joystick_deadzone:
                    y = 0.0
                dx += x
                dy += y
                if getattr(self, "joystick_debug_axes", False):
                    now = time.time()
                    if (abs(x) > 0 or abs(y) > 0) and now >= getattr(
                        self, "joystick_debug_next_dump", 0.0
                    ):
                        print(f"Joystick move: x={x:.3f}, y={y:.3f}")
                        self.joystick_debug_next_dump = now + 0.5
        except Exception:
            pass
        try:
            hat_x, hat_y = self.joystick.get_hat(0)
            dx += hat_x
            dy += -hat_y
        except Exception:
            pass
        dx = max(-1.0, min(1.0, dx))
        dy = max(-1.0, min(1.0, dy))
        return dx, dy

    def human_active(self):
        return self.control_mode in ("human_only", "both")

    def agent_active(self):
        return self.control_mode in ("agent_only", "both")

    def human_signal_allowed(self):
        return self.signal_mode in ("human_dom", "negotiation")

    def agent_signal_allowed(self):
        return self.signal_mode in ("agent_dom", "negotiation")

    def start_countdown(self, seconds: int = 3):
        self.countdown_active = True
        self.countdown_end_time = time.time() + max(1, seconds)

    def update_trigger_icons(self, now: float) -> None:
        if now < getattr(self, "human_icon_until", 0.0):
            return
        if self.human_cross_img_base is not None:
            self.human_cross_img = self.human_cross_img_base
        if not self.human_signal_allowed():
            return
        keys = pg.key.get_pressed()
        kx_pressed = keys[pg.K_x]
        kc_pressed = keys[pg.K_c]
        if kx_pressed and not self.kx_latched:
            self.trigger_human_icon_left_right()
        if kc_pressed and not self.kc_latched:
            self.trigger_human_icon_my()
        self.kx_latched = kx_pressed
        self.kc_latched = kc_pressed
        if self.joystick:
            lt_pressed, rt_pressed = self.read_trigger_buttons()
            if lt_pressed and not self.lt_latched:
                self.trigger_human_icon_left_right()
            if rt_pressed and not self.rt_latched:
                self.trigger_human_icon_my()
            self.lt_latched = lt_pressed
            self.rt_latched = rt_pressed

    def process_voice_events(self, now: float) -> None:
        if not self.voice_listener:
            return
        for event in self.voice_listener.poll():
            if event == "human_my":
                self.trigger_human_icon_my()
            elif event == "human_your":
                self.trigger_human_icon_left_right()

    def update_agent_icon(self, now: float) -> None:
        if now < getattr(self, "agent_icon_until", 0.0):
            return
        if self.ai_cross_img_base is not None:
            self.ai_cross_img = self.ai_cross_img_base

    def read_trigger_buttons(self):
        if not self.joystick:
            return False, False
        try:
            threshold = 0.35
            num_axes = self.joystick.get_numaxes()
            lt_axis = None
            rt_axis = None
            if num_axes >= 6:
                lt_candidates = [2, 4]
                rt_candidates = [5, 3]
            elif num_axes >= 4:
                lt_candidates = [2]
                rt_candidates = [3]
            else:
                lt_candidates = []
                rt_candidates = []

            for idx in lt_candidates:
                if idx < num_axes:
                    val = self.joystick.get_axis(idx)
                    if lt_axis is None or abs(val) > abs(lt_axis):
                        lt_axis = val
            for idx in rt_candidates:
                if idx < num_axes:
                    val = self.joystick.get_axis(idx)
                    if rt_axis is None or abs(val) > abs(rt_axis):
                        rt_axis = val

            if lt_axis is None:
                lt_axis = 0.0
            if rt_axis is None:
                rt_axis = 0.0
            lt_axis = max(-1.0, min(1.0, lt_axis))
            rt_axis = max(-1.0, min(1.0, rt_axis))
            lt_threshold = 0.03
            lt_pressed = abs(lt_axis) > lt_threshold
            rt_pressed = abs(rt_axis) > threshold
            if not lt_pressed and not rt_pressed:
                for idx, val in enumerate(self.joystick_axes):
                    if idx in (0, 1):
                        continue
                    if abs(val) > 0.5:
                        if val < 0:
                            lt_pressed = True
                        else:
                            rt_pressed = True
                        break

            if self.lt_rest is None and lt_axis is not None:
                if lt_axis <= -0.8:
                    self.lt_rest = -1.0
                elif abs(lt_axis) <= 0.2:
                    self.lt_rest = 0.0
                else:
                    self.lt_rest = lt_axis
            if self.rt_rest is None and rt_axis is not None:
                if rt_axis <= -0.8:
                    self.rt_rest = -1.0
                elif abs(rt_axis) <= 0.2:
                    self.rt_rest = 0.0
                else:
                    self.rt_rest = rt_axis
            lt_pressed = False
            rt_pressed = False
            if lt_axis is not None and self.lt_rest is not None:
                lt_pressed = (lt_axis - self.lt_rest) > 0.6 or (self.lt_rest - lt_axis) > 0.6
            if rt_axis is not None and self.rt_rest is not None:
                rt_pressed = (rt_axis - self.rt_rest) > 0.6 or (self.rt_rest - rt_axis) > 0.6

            try:
                num_buttons = self.joystick.get_numbuttons()
                if num_buttons >= 8:
                    lt_pressed = lt_pressed or self.joystick.get_button(6)
                    rt_pressed = rt_pressed or self.joystick.get_button(7)
                elif num_buttons >= 6:
                    lt_pressed = lt_pressed or self.joystick.get_button(4)
                    rt_pressed = rt_pressed or self.joystick.get_button(5)
                # Xbox Y (button 3) -> LT 行為
                if num_buttons > 3:
                    lt_pressed = lt_pressed or self.joystick.get_button(3)
            except Exception:
                pass

            if self.joystick_debug_axes and (lt_pressed or rt_pressed):
                print(f"LT/RT axis: {lt_axis:.3f}/{rt_axis:.3f} btn6/7: {self.joystick.get_button(6) if self.joystick.get_numbuttons() > 6 else 'NA'} {self.joystick.get_button(7) if self.joystick.get_numbuttons() > 7 else 'NA'}")
            if not lt_pressed and lt_axis is not None and self.lt_rest is not None:
                self.lt_rest = self.lt_rest * 0.8 + lt_axis * 0.2
            if not rt_pressed and rt_axis is not None and self.rt_rest is not None:
                self.rt_rest = self.rt_rest * 0.8 + rt_axis * 0.2
            self.lt_prev = lt_axis
            self.rt_prev = rt_axis

            return lt_pressed, rt_pressed
        except Exception:
            return False, False

    def trigger_human_icon_left_right(self):
        if not self.human_active():
            return
        if not self.human_signal_allowed():
            return
        now = time.time()
        if now < getattr(self, "human_icon_until", 0.0):
            return
        if self.agent_x < self.human_x:
            img = self.human_cross_img_left
        else:
            img = self.human_cross_img_right
        if img is not None:
            self.human_cross_img = img
            self.human_icon_until = now + SIGNAL_ICON_DURATION
            self.ai_aggressive_until = max(getattr(self, "ai_aggressive_until", 0.0), now + 3.0)

    def trigger_human_icon_my(self):
        if not self.human_active():
            return
        if not self.human_signal_allowed():
            return
        now = time.time()
        if now < getattr(self, "human_icon_until", 0.0):
            return
        if self.human_cross_img_my is not None:
            self.human_cross_img = self.human_cross_img_my
            self.human_icon_until = now + SIGNAL_ICON_DURATION
            self.apply_agent_slow(now, 3.0, factor=0.25)
            self.ai_aggressive_until = 0.0
            self.human_my_block_until = now + 2.5
            self.round_signal_sent += 1
            self.log_event("signal_sent", triggered_by="human", signal_type="human_my")

    def trigger_agent_icon(self, signal_type: str, now: float) -> None:
        if now < getattr(self, "agent_icon_until", 0.0):
            return
        img = None
        if signal_type == "agent_my":
            img = self.ai_cross_img_my
        elif signal_type == "agent_your_left":
            img = self.ai_cross_img_left
        elif signal_type == "agent_your_right":
            img = self.ai_cross_img_right
        if img is not None:
            self.ai_cross_img = img
            self.agent_icon_until = now + 1.0
        # 播放 Agent 訊號音效
        try:
            sound_path = None
            if signal_type == "agent_my":
                sound_path = self.base_dir / "source" / "agent_mysound.mp3"
                if hasattr(self.audio, "snd_agent_my"):
                    self.audio.play(self.audio.snd_agent_my)
                    sound_path = None
            elif signal_type in ("agent_your_left", "agent_your_right"):
                sound_path = self.base_dir / "source" / "agent_yoursound.mp3"
                if hasattr(self.audio, "snd_agent_your"):
                    self.audio.play(self.audio.snd_agent_your)
                    sound_path = None
            if sound_path is not None:
                try:
                    s = pg.mixer.Sound(str(sound_path))
                    if hasattr(self.audio, "play"):
                        self.audio.play(s)
                    else:
                        s.play()
                except Exception:
                    try:
                        pg.mixer.Sound(str(sound_path)).play()
                    except Exception:
                        pass
        except Exception:
            pass

    def attempt_human_shot(self):
        if not self.human_active():
            return
        now = time.time()
        # 判斷是否冷卻完成
        if now - getattr(self, "last_human_shot", 0.0) <= getattr(self, "human_shot_cooldown", 0.25):
            return
        # 計算準心圖片半徑（若有圖片用圖片尺寸，否則用 explosion_radius）
        if getattr(self, "human_cross_img", None):
            img_radius = self.human_cross_img.get_width() / 2.0
        else:
            img_radius = getattr(self, "explosion_radius", 48)
        # 只有當 ball 進入準心圖片區域才允許開火
        dist_to_ball = math.hypot(self.ball_x - self.human_x, self.ball_y - self.human_y)
        if dist_to_ball <= img_radius * 1.1:
            # 建立爆炸（實際命中仍由 create_explosion 判定 inner 1/3）
            self.create_explosion(self.human_x, self.human_y, "human", now)
            self.last_human_shot = now
            # 若另一方太靠近則會誤傷 -> 施加干擾
            dist_to_agent = math.hypot(self.agent_x - self.human_x, self.agent_y - self.human_y)
            if dist_to_agent <= FRIENDLY_FIRE_RADIUS:
                # 友軍在爆炸預估視覺範圍內，施加誤傷效果（閃頻 + 暫停）
                self.apply_friendly_penalty("agent", now, FRIENDLY_FIRE_PENALTY_SEC)
                self.log_event("friendly_fire", triggered_by="human")

    def apply_agent_slow(self, now: float, duration: float = 2.0, factor: float = 0.5) -> None:
        self.ai_slow_until = max(getattr(self, "ai_slow_until", 0.0), now + duration)
        self.ai_slow_factor = min(getattr(self, "ai_slow_factor", 1.0), factor)

    def maybe_send_agent_signal(self, now: float) -> None:
        if self.signal_sent_for_ball or not self.agent_active():
            return
        if not self.agent_signal_allowed():
            return
        # 只在畫面略高於 1/2 到 2/3 高度範圍內才隨機判斷是否發送
        if self.ball_y < HEIGHT * 0.46 or self.ball_y > HEIGHT * 2 / 3:
            return
        if random.random() > 0.5:
            return
        dist_agent = math.hypot(self.ball_x - self.agent_x, self.ball_y - self.agent_y)
        dist_human = math.hypot(self.ball_x - self.human_x, self.ball_y - self.human_y)
        denom = max(1e-6, dist_agent + dist_human)
        dir_ratio = dist_agent / denom
        jitter = random.uniform(0.85, 1.15)
        dir_ratio = max(0.0, min(1.0, dir_ratio * jitter))
        signal_type = None
        if dir_ratio < 0.4:
            signal_type = "agent_my"
        elif dir_ratio > 0.6:
            signal_type = "agent_your_left" if self.human_x < self.agent_x else "agent_your_right"
        else:
            if random.random() < 0.5:
                signal_type = "agent_your_left" if self.human_x < self.agent_x else "agent_your_right"
            else:
                signal_type = None
        if signal_type:
            self.signal_sent_for_ball = True
            self.round_signal_sent += 1
            self.log_event("signal_sent", triggered_by="agent", signal_type=signal_type, dir_ratio=dir_ratio)
            self.trigger_agent_icon(signal_type, now)
            if signal_type == "agent_my":
                self.ai_aggressive_until = now + 3.0
            if signal_type in ("agent_your_left", "agent_your_right"):
                self.apply_agent_slow(now, 2.0, factor=0.5)

    def update_agent_dir_behavior(self, now: float) -> None:
        if not self.agent_active():
            return
        if self.ball_y < HEIGHT * 0.46 or self.ball_y > HEIGHT * 2 / 3:
            return
        dist_agent = math.hypot(self.ball_x - self.agent_x, self.ball_y - self.agent_y)
        dist_human = math.hypot(self.ball_x - self.human_x, self.ball_y - self.human_y)
        denom = max(1e-6, dist_agent + dist_human)
        dir_ratio = dist_agent / denom
        if dir_ratio < 0.4:
            self.ai_aggressive_until = max(getattr(self, "ai_aggressive_until", 0.0), now + 1.5)
        elif dir_ratio > 0.6:
            self.ai_passive_until = max(getattr(self, "ai_passive_until", 0.0), now + 1.5)

    def try_start_experiment(self):
        # 使用預設值啟動（已移除輸入欄位）
        self.current_user_id = 0
        self.condition_code = CONDITION_BY_MODE.get(self.signal_mode, 1)
        self.current_round = 1
        # 重置總成績
        self.total_score = 0
        self.total_errors = 0
        self.start_experiment_api()
        # 進入第一回合
        self.reset_round_stats()
        self.start_round_api()
        self.state = GameState.ROUND
        print(
            f"Start experiment: user_id={self.current_user_id}, "
            f"condition={self.condition_code} ({CONDITIONS[self.condition_code][0]})"
        )

    def reset_ball_random(self):
        # 生成一個從上方下落的目標（不反彈，水平有隨機漂移）
        import random
        self.ball_x = random.uniform(40, WIDTH - 40)
        self.ball_y = -20
        self.ball_spawn_y = self.ball_y
        self.signal_sent_for_ball = False
        self.ai_aim_offset_x = random.uniform(-15.0, 15.0)
        self.ai_aim_offset_y = random.uniform(-15.0, 15.0)
        self.ball_vx = random.uniform(-1.5, 1.5)
        self.ball_vy = random.uniform(1.4, 3.0)  # 始終往下移動
        self.clamp_ball_speed()
        self.round_ball_spawn += 1
        self.log_event("ball_spawn", triggered_by="system")

    def clamp_ball_speed(self):
        """避免速度過低或過高，控制在合理範圍。"""
        max_speed = 12
        min_speed = 2.0
        self.ball_vx = max(-max_speed, min(max_speed, self.ball_vx))
        self.ball_vy = max(-max_speed, min(max_speed, self.ball_vy))
        if 0 < abs(self.ball_vx) < min_speed:
            self.ball_vx = min_speed if self.ball_vx >= 0 else -min_speed
        if 0 < abs(self.ball_vy) < min_speed:
            self.ball_vy = min_speed if self.ball_vy >= 0 else -min_speed

    def rotate_velocity(self, deg_min: float = 30, deg_max: float = 50) -> None:
        """將速度向量旋轉一個隨機角度（deg_min~deg_max），增加角度變化。"""
        angle_deg = random.uniform(deg_min, deg_max)
        angle_deg *= 1 if random.choice([True, False]) else -1
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        vx, vy = self.ball_vx, self.ball_vy
        self.ball_vx = vx * cos_a - vy * sin_a
        self.ball_vy = vx * sin_a + vy * cos_a

    # --- API / LOGGING ---
    def _agent_human_flags(self) -> tuple[bool, bool]:
        if self.condition_code == 1:
            return False, False
        if self.condition_code == 2:
            return False, True
        if self.condition_code == 3:
            return True, False
        if self.condition_code == 4:
            return True, True
        return False, False

    def log_event(
        self,
        event_type: str,
        triggered_by: str = "system",
        signal_type: str = "NA",
        dir_ratio: Optional[float] = None,
    ) -> None:
        if self.current_user_id is None or self.condition_code is None or self.current_round is None:
            return
        speed = math.sqrt(self.ball_vx ** 2 + self.ball_vy ** 2)
        angle = math.degrees(math.atan2(self.ball_vy, self.ball_vx))
        payload = {
            "user_id": self.current_user_id,
            "condition": self.condition_code,
            "round_id": self.current_round,
            "timestamp": dt.datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "ball_x": int(self.ball_x),
            "ball_y": int(self.ball_y),
            "human_x": int(self.human_x),
            "human_y": int(self.human_y),
            "agent_x": int(self.agent_x),
            "agent_y": int(self.agent_y),
            "triggered_by": triggered_by,
            "signal_type": signal_type,
            "dir_ratio": dir_ratio,
            "ball_speed": round(speed, 3),
            "ball_angle": round(angle, 3),
        }
        api_client.log_event(payload)

    def start_experiment_api(self):
        if self.current_user_id is None or self.condition_code is None:
            return
        self.exp_start_iso = dt.datetime.utcnow().isoformat() + "Z"
        self.exp_logged = False
        api_client.start_experiment(
            self.current_user_id,
            self.condition_code,
            self.total_rounds,
            notes="",
            exp_start_time=self.exp_start_iso,
        )

    def end_experiment_api(self):
        if self.current_user_id is None or self.condition_code is None or self.exp_start_iso is None:
            return
        exp_end = dt.datetime.utcnow().isoformat() + "Z"
        api_client.end_experiment(
            self.current_user_id,
            self.condition_code,
            self.exp_start_iso,
            exp_end,
            self.total_rounds,
            notes="",
        )
        self.exp_logged = True

    def start_round_api(self):
        if self.current_user_id is None or self.condition_code is None or self.round_start_iso is None:
            return
        agent_active, human_active = self._agent_human_flags()
        api_client.start_round(
            self.current_user_id,
            self.condition_code,
            self.current_round,
            agent_active,
            human_active,
            self.round_start_iso,
        )

    def end_round_api(self):
        if self.current_user_id is None or self.condition_code is None or self.round_start_iso is None:
            return
        agent_active, human_active = self._agent_human_flags()
        round_end = dt.datetime.utcnow().isoformat() + "Z"
        api_client.end_round(
            self.current_user_id,
            self.condition_code,
            self.current_round,
            self.round_start_iso,
            round_end,
            self.round_score,
            self.round_errors,
            self.round_collisions,
            self.round_ball_spawn,
            self.round_signal_sent,
            self.round_ball_catch,
            self.round_ball_miss,
            agent_active,
            human_active,
        )

    def handle_events_round(self, event):
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            if self.mode_selector.handle_event(event):
                self.control_mode = self.mode_selector.selected
                return
            if self.signal_selector.handle_event(event):
                self.signal_mode = self.signal_selector.selected
                self.condition_code = CONDITION_BY_MODE[self.signal_mode]
                return
            if self.info_button_rect.collidepoint(event.pos):
                self.intro_overlay.index = 0
                self.show_intro = True
                return
            mic_center = (WIDTH // 2, 18)
            if (event.pos[0] - mic_center[0]) ** 2 + (event.pos[1] - mic_center[1]) ** 2 <= 12 ** 2:
                self.toggle_voice_listener()
                return

        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                self.go_home()

            # 人類按空白鍵發射（只有當目標進入準心圖片區域才可發射）
            if event.key == pg.K_SPACE:
                self.attempt_human_shot()
            if event.key == pg.K_x:
                self.trigger_human_icon_left_right()
            if event.key == pg.K_c:
                self.trigger_human_icon_my()

        if event.type == pg.JOYBUTTONDOWN:
            if getattr(self, "joystick_debug_buttons", False):
                print(f"Joystick button pressed: {event.button}")
            # Xbox A 鍵發射（通常 button 0）
            if event.button == 0:
                self.attempt_human_shot()
            # LT/RT 有些裝置會回報為按鈕
            if event.button in (6, 4, 3):
                self.trigger_human_icon_left_right()
            if event.button in (7, 5):
                self.trigger_human_icon_my()
        if event.type == pg.JOYAXISMOTION:
            if getattr(self, "joystick_debug_axes", False):
                print(f"Joystick axis {event.axis}: {event.value:.3f}")
        if event.type == pg.JOYHATMOTION:
            if getattr(self, "joystick_debug_axes", False):
                print(f"Joystick hat {event.hat}: {event.value}")

    def handle_events_break(self, event):
        if event.type == pg.KEYDOWN:
            # 下一回合 / 結束
            if event.key == pg.K_SPACE:
                self.go_next_round_or_done()
            elif event.key == pg.K_h:
                self.go_home()

        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            # 在 BREAK 畫面中，簡單把畫面中間的文字當「按鈕」
            center_rect = pg.Rect(0, 0, 400, 60)
            center_rect.center = (WIDTH // 2, HEIGHT // 2 + 80)
            if center_rect.collidepoint(event.pos):
                self.go_next_round_or_done()

    def handle_events_done(self, event):
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_h:
                self.go_home()

    def go_home(self):
        # 回首頁時重置狀態，但保留已輸入的 user_id / condition（你要清空也可以改這裡）
        if self.state == GameState.ROUND:
            self.finish_round()
        if self.exp_start_iso and not self.exp_logged:
            self.end_experiment_api()
        self.state = GameState.HOME
        self.current_user_id = None
        self.condition_code = None
        self.current_round = 0
        self.round_start_ms = None
        self.total_score = 0
        self.total_errors = 0
        print("Return to HOME")

    def go_next_round_or_done(self):
        if self.current_round < self.total_rounds:
            self.current_round += 1
            self.reset_round_stats()
            self.start_round_api()
            self.state = GameState.ROUND
            print(f"Start round {self.current_round}")
        else:
            # 結束實驗
            if not self.exp_logged and self.exp_start_iso:
                self.end_experiment_api()
            self.state = GameState.DONE
            print("Experiment DONE")

    def finish_round(self):
        self.round_end_iso = dt.datetime.utcnow().isoformat() + "Z"
        self.total_score += self.round_score
        self.total_errors += self.round_errors
        self.end_round_api()

    # --- 更新邏輯 ---

    def update(self, dt):
        if getattr(self, "show_intro", False) and self.intro_overlay:
            try:
                self.intro_overlay.update(dt, self.joystick, WIDTH, HEIGHT)
            except Exception:
                pass
        if getattr(self, "countdown_active", False):
            if time.time() >= getattr(self, "countdown_end_time", 0.0):
                self.countdown_active = False
                if self.pending_start:
                    self.pending_start = False
                    self.try_start_experiment()
            else:
                return
        if self.state == GameState.ROUND:
            self.update_round(dt)

    def update_round(self, dt):
        import random
        if getattr(self, "show_intro", False):
            return
        if getattr(self, "countdown_active", False):
            return

        # 更新 freeze/flash 計時（ms）
        if getattr(self, "conflict_freeze_ms", 0) > 0:
            self.conflict_freeze_ms = max(0, self.conflict_freeze_ms - dt * 1000)
        if getattr(self, "human_flash_ms", 0) > 0:
            self.human_flash_ms = max(0, self.human_flash_ms - dt * 1000)
        if getattr(self, "ai_flash_ms", 0) > 0:
            self.ai_flash_ms = max(0, self.ai_flash_ms - dt * 1000)
        if getattr(self, "post_conflict_guard_ms", 0) > 0:
            self.post_conflict_guard_ms = max(0, self.post_conflict_guard_ms - dt * 1000)

        # 若衝突 freeze 正在進行，則略過移動/射擊行為
        if getattr(self, "conflict_freeze_ms", 0) > 0:
            return

        # 人類準心移動（箭頭或 WASD）
        keys = pg.key.get_pressed()
        # 若處在被動干擾期間則減速
        now = time.time()
        human_penalty_active = now < getattr(self, "human_penalty_until", 0.0)
        ai_penalty_active = now < getattr(self, "ai_penalty_until", 0.0)
        human_speed = 2.0 * (0.4 if human_penalty_active else 1.0)
        if self.human_active():
            if keys[pg.K_LEFT] or keys[pg.K_a]:
                self.human_x -= human_speed
            if keys[pg.K_RIGHT] or keys[pg.K_d]:
                self.human_x += human_speed
            if keys[pg.K_UP] or keys[pg.K_w]:
                self.human_y -= human_speed
            if keys[pg.K_DOWN] or keys[pg.K_s]:
                self.human_y += human_speed
            joy_dx, joy_dy = self.read_joystick_move()
            if joy_dx or joy_dy:
                self.human_x += joy_dx * human_speed
                self.human_y += joy_dy * human_speed
            if self.joystick:
                try:
                    if self.joystick.get_button(0):
                        self.attempt_human_shot()
                except Exception:
                    pass
            if self.joystick:
                try:
                    self.joystick_axes = [self.joystick.get_axis(i) for i in range(self.joystick.get_numaxes())]
                except Exception:
                    self.joystick_axes = []
            self.update_trigger_icons(now)
            self.process_voice_events(now)
            self.human_x = max(0, min(WIDTH, self.human_x))
            self.human_y = max(HEIGHT // 2, min(HEIGHT - 10, self.human_y))

        # 目標下落
        self.ball_x += self.ball_vx
        self.ball_y += self.ball_vy
        # 下落時加入水平隨機漂移（y 軸維持往下）
        self.ball_x += random.uniform(-0.8, 0.8)
        if random.random() < 0.06:
            self.ball_vx += random.uniform(-0.7, 0.7)
            self.ball_vx = max(-3.2, min(3.2, self.ball_vx))
        if self.ball_x < 20:
            self.ball_x = 20
            self.ball_vx = abs(self.ball_vx) * 0.6
        if self.ball_x > WIDTH - 20:
            self.ball_x = WIDTH - 20
            self.ball_vx = -abs(self.ball_vx) * 0.6

        # 代理人訊號判斷（目標接近下半區）
        if self.human_active():
            self.update_agent_dir_behavior(now)
            self.maybe_send_agent_signal(now)

        # AI 對齊並在條件下引爆
        dist_agent_to_ball = math.hypot(self.ball_x - self.agent_x, self.ball_y - self.agent_y)
        ai_active = False
        if now < getattr(self, "ai_idle_until", 0.0):
            ai_active = False
        elif now < getattr(self, "ai_track_until", 0.0):
            ai_active = True
        else:
            if dist_agent_to_ball < 220:
                self.ai_track_until = now + random.uniform(1.0, 1.8)
                ai_active = True
            elif random.random() < 0.8:
                self.ai_track_until = now + random.uniform(0.8, 1.6)
                ai_active = True
            else:
                self.ai_idle_until = now + random.uniform(0.6, 1.2)
                ai_active = False
        aggressive = now < getattr(self, "ai_aggressive_until", 0.0) and now >= getattr(
            self, "human_my_block_until", 0.0
        )
        passive = now < getattr(self, "ai_passive_until", 0.0) and not aggressive
        if aggressive:
            ai_active = True
        agent_speed = 1.7
        if now < getattr(self, "ai_slow_until", 0.0):
            agent_speed *= getattr(self, "ai_slow_factor", 0.5)
        else:
            self.ai_slow_factor = 1.0
        if aggressive:
            agent_speed *= 1.25
        ball_spawn_y = getattr(self, "ball_spawn_y", -20.0)
        ball_travel_total = max(1.0, HEIGHT - ball_spawn_y)
        ball_travel_progress = (self.ball_y - ball_spawn_y) / ball_travel_total
        if self.agent_active() and ai_active and ball_travel_progress >= 0.25:
            self.ai_aim_offset_x = getattr(self, "ai_aim_offset_x", 0.0)
            self.ai_aim_offset_y = getattr(self, "ai_aim_offset_y", 0.0)
            jitter_scale = 0.55 if aggressive else 1.0
            self.ai_aim_offset_x += random.uniform(-0.08, 0.08) * jitter_scale
            self.ai_aim_offset_y += random.uniform(-0.08, 0.08) * jitter_scale
            self.ai_aim_offset_x = max(-18.0, min(18.0, self.ai_aim_offset_x))
            self.ai_aim_offset_y = max(-18.0, min(18.0, self.ai_aim_offset_y))
            target_x = self.ball_x + self.ai_aim_offset_x
            target_y = self.ball_y + self.ai_aim_offset_y
            if self.agent_x < target_x - 6:
                self.agent_x += agent_speed
            elif self.agent_x > target_x + 6:
                self.agent_x -= agent_speed
            if self.agent_y < target_y - 6:
                self.agent_y += agent_speed
            elif self.agent_y > target_y + 6:
                self.agent_y -= agent_speed
            self.agent_x = max(0, min(WIDTH, self.agent_x))
            self.agent_y = max(HEIGHT // 2, min(HEIGHT - 10, self.agent_y))

        # AI 射擊：需在「AI 準心圖片區域」內才會引爆；若太靠近人類則會造成友火干擾
        if self.agent_active() and ai_active:
            # 用 AI 圖片半徑做為可發射判定（若沒有圖片退回 explosion_radius）
            if getattr(self, "ai_cross_img", None):
                ai_img_radius = self.ai_cross_img.get_width() / 2.0
            else:
                ai_img_radius = getattr(self, "explosion_radius", 48)
            if dist_agent_to_ball <= ai_img_radius:
                if now - getattr(self, "last_ai_shot", 0.0) > getattr(self, "ai_shot_cooldown", 0.5):
                    if aggressive:
                        shot_chance = 0.85
                    elif passive:
                        shot_chance = 0.65
                    else:
                        shot_chance = 0.8
                    if random.random() <= shot_chance:
                        self.create_explosion(self.agent_x, self.agent_y, "agent", now)
                        self.last_ai_shot = now
                        # 檢查友火（以視覺半徑做判定）
                        dist_to_human = math.hypot(self.human_x - self.agent_x, self.agent_y - self.human_y)
                        if dist_to_human <= FRIENDLY_FIRE_RADIUS:
                            self.apply_friendly_penalty("human", now, FRIENDLY_FIRE_PENALTY_SEC)
                            self.log_event("friendly_fire", triggered_by="agent")

        # 更新爆炸列表（移除過期）
        for e in list(self.explosions):
            if now - e["t"] > e["dur"]:
                try:
                    self.explosions.remove(e)
                except ValueError:
                    pass

        if self.agent_active():
            self.update_agent_icon(now)

        # 檢查目標通過底線
        ball_r = getattr(self, "ball_radius", BALL_R)
        if self.ball_y - ball_r > HEIGHT:
            self.round_errors = getattr(self, "round_errors", 0) + 1
            self.log_event("ball_miss", triggered_by="system")
            try:
                denied_path = self.base_dir / "source" / "denied.mp3"
                if hasattr(self, "audio") and getattr(self.audio, "play", None):
                    try:
                        if hasattr(self.audio, "snd_denied"):
                            self.audio.play(self.audio.snd_denied)
                        else:
                            s = pg.mixer.Sound(str(denied_path))
                            self.audio.play(s)
                    except Exception:
                        try:
                            pg.mixer.Sound(str(denied_path)).play()
                        except Exception:
                            pass
                else:
                    try:
                        pg.mixer.Sound(str(denied_path)).play()
                    except Exception:
                        pass
            except Exception:
                pass
            self.reset_ball_random()

        # 檢查準心重疊（靠太近會造成被動干擾）
        if self.human_active() and self.agent_active() and not getattr(self, "hide_mode_ui", False):
            cross_dist = math.hypot(self.human_x - self.agent_x, self.human_y - self.agent_y)
            overlap_thresh = PADDLE_W * 0.8
            if cross_dist < overlap_thresh:
                # 若正在護欄期（post_conflict_guard_ms），只做柔性分離（nudge），不重複計為衝突
                if getattr(self, "post_conflict_guard_ms", 0) > 0:
                    try:
                        dx = self.agent_x - self.human_x
                        if abs(dx) < 1e-3:
                            dx = 1.0
                        # nudge magnitude 根據重疊量，但限制在小值，避免瞬間推開
                        overlap_amount = max(0.0, overlap_thresh - cross_dist)
                        nudge = min(8.0, overlap_amount * 0.6)
                        nx = dx / math.hypot(dx, self.agent_y - self.human_y)
                        # 向左右各小幅移動
                        self.human_x = max(0, min(WIDTH, self.human_x - nx * nudge))
                        self.agent_x = max(0, min(WIDTH, self.agent_x + nx * nudge))
                    except Exception:
                        pass
                else:
                    # 正常第一次檢測到重疊 -> 記錄為衝突並觸發 penalty（將暫停 0.5s）
                    self.apply_friendly_penalty("human", now, OVERLAP_PENALTY_SEC)
                    self.apply_friendly_penalty("agent", now, OVERLAP_PENALTY_SEC)
                    self.round_collisions += 1
                    # 記錄事件（一次即可）
                    self.log_event("crosshair_overlap", triggered_by="system")

    def create_explosion(self, x: float, y: float, owner: str, now: float) -> None:
        """在 (x,y) 產生短暫爆炸並立即檢查命中（不產生移動子彈）"""
        if not hasattr(self, "explosions"):
            self.explosions = []

        exp = {"x": float(x), "y": float(y), "t": now, "dur": getattr(self, "explosion_duration", 0.28), "r": getattr(self, "explosion_radius", 48), "owner": owner}
        self.explosions.append(exp)
        # 立即檢查是否命中當前目標（ball）
        hit = False
        try:
            dist = math.hypot(self.ball_x - x, self.ball_y - y)
            # 命中條件：在爆炸半徑的 INNER_SHOOT_FACTOR（例如 1/3）內才算命中
            hit_radius = exp["r"] * INNER_SHOOT_FACTOR
            if owner == "human":
                hit_radius *= 1.8
            if owner == "agent":
                hit_radius = exp["r"] * 0.8
            if dist <= hit_radius:
                hit = True
                # 命中目標：加分、記錄事件、重生目標
                self.round_score = getattr(self, "round_score", 0) + 1
                self.log_event("ball_hit", triggered_by=owner)
                self.reset_ball_random()
            # 視覺半徑（用於友軍誤傷判定）：exp["r"] * EXPLOSION_VISUAL_SCALE
            visual_r = exp["r"] * EXPLOSION_VISUAL_SCALE
            if owner == "human":
                dist_to_agent = math.hypot(self.agent_x - x, self.agent_y - y)
                if dist_to_agent <= visual_r:
                    # 友軍誤傷：閃頻並暫停
                    self.apply_friendly_penalty("agent", now, FRIENDLY_FIRE_PENALTY_SEC)
                    self.ai_flash_ms = max(getattr(self, "ai_flash_ms", 0), int(FRIENDLY_FIRE_PENALTY_SEC * 1000))
                    self.log_event("friendly_fire", triggered_by="human")
            elif owner == "agent":
                dist_to_human = math.hypot(self.human_x - x, self.human_y - y)
                if dist_to_human <= visual_r:
                    self.apply_friendly_penalty("human", now, FRIENDLY_FIRE_PENALTY_SEC)
                    self.human_flash_ms = max(getattr(self, "human_flash_ms", 0), int(FRIENDLY_FIRE_PENALTY_SEC * 1000))
                    self.log_event("friendly_fire", triggered_by="agent")
        except AttributeError:
            # 若目前沒有 ball_x/ball_y，安全忽略
            pass
        # 播放射擊 / 命中音（優先 AudioManager，否則 pygame.mixer）
        try:
            sound_name = "rifle.mp3" if hit else "shoot.mp3"
            sound_path = self.base_dir / "source" / sound_name
            if hasattr(self, "audio") and getattr(self.audio, "play", None):
                try:
                    s = pg.mixer.Sound(str(sound_path))
                    self.audio.play(s)
                except Exception:
                    try:
                        pg.mixer.Sound(str(sound_path)).play()
                    except Exception:
                        pass
            else:
                try:
                    pg.mixer.Sound(str(sound_path)).play()
                except Exception:
                    pass
        except Exception:
            pass

    def apply_friendly_penalty(self, target: str, now: float, dur: float = FRIENDLY_FIRE_PENALTY_SEC) -> None:
        """
        對 human 或 agent 施加暫時干擾：
        - 設定 penalty_until（影響移動速度與射擊冷卻）
        - 觸發短暫停頓（conflict_freeze_ms）
        - 播放錯誤聲（game/source/wrong.mp3）
        """
        # 設定 penalty 時間與延長冷卻
        if target == "human":
            self.human_penalty_until = max(getattr(self, "human_penalty_until", 0.0), now + dur)
            self.human_shot_cooldown = max(getattr(self, "human_shot_cooldown", 0.25), dur)
            # human flash ms
            self.human_flash_ms = max(getattr(self, "human_flash_ms", 0), int(dur * 1000))
        elif target == "agent":
            self.ai_penalty_until = max(getattr(self, "ai_penalty_until", 0.0), now + dur)
            self.ai_shot_cooldown = max(getattr(self, "ai_shot_cooldown", 0.5), dur)
            # ai flash ms
            self.ai_flash_ms = max(getattr(self, "ai_flash_ms", 0), int(dur * 1000))

        # 衝突行為：暫停固定 0.5 秒（500 ms）
        # 暫停結束後開啟護欄期 1.0 秒（1000 ms），在此期間允許重疊但會做柔性分離，不會再算新衝突
        self.conflict_freeze_ms = max(getattr(self, "conflict_freeze_ms", 0.0), int(0.5 * 1000))
        self.post_conflict_guard_ms = max(getattr(self, "post_conflict_guard_ms", 0.0), int(1.0 * 1000))

        # 播放錯誤音（優先使用 AudioManager，失敗再用 pygame.mixer）
        try:
            wrong_path = self.base_dir / "source" / "wrong.mp3"
            if hasattr(self, "audio") and getattr(self.audio, "play", None):
                # 若 AudioManager 提供預載聲音屬性，優先使用
                try:
                    if hasattr(self.audio, "snd_wrong"):
                        self.audio.play(self.audio.snd_wrong)
                    else:
                        # 嘗試以 pygame.Sound 建立後交給 audio.play
                        s = pg.mixer.Sound(str(wrong_path))
                        self.audio.play(s)
                except Exception:
                    # fallback to direct pygame play
                    try:
                        pg.mixer.Sound(str(wrong_path)).play()
                    except Exception:
                        pass
            else:
                # 直接用 pygame 播放
                try:
                    pg.mixer.Sound(str(wrong_path)).play()
                except Exception:
                    pass
        except Exception:
            pass

        # 記錄事件（保留實驗日誌）
        try:
            # 使用統一 payload 格式
            self.log_event({"type": "friendly_penalty", "target": target, "time": now})
        except Exception:
            pass

    def check_collisions(self):
        # 子彈打中下落目標
        if not hasattr(self, "bullets"):
            return
        for b in list(self.bullets):
            if abs(b["x"] - self.ball_x) < 20 and abs(b["y"] - self.ball_y) < 20:
                # 擊中：加分、記錄事件，重生目標
                self.round_score = getattr(self, "round_score", 0) + 1
                self.log_event("ball_hit", triggered_by=b.get("owner", "human"))
                try:
                    self.bullets.remove(b)
                except ValueError:
                    pass
                self.reset_ball_random()

    # --- 繪圖 ---

    def draw(self):
        self.screen.fill(BG_COLOR)

        if self.state == GameState.HOME:
            self.draw_home()
        elif self.state == GameState.ROUND:
            self.draw_round()
        elif self.state == GameState.BREAK:
            self.draw_break()
        elif self.state == GameState.DONE:
            self.draw_done()

        if getattr(self, "show_intro", False):
            self.intro_overlay.draw(self.screen, self.font_small, WIDTH, HEIGHT)
        elif getattr(self, "countdown_active", False):
            self.draw_countdown()

        pg.display.flip()

    def draw_home(self):
        # 簡化首頁：只保留標題、說明與 Start 按鈕
        # 背景
        self.screen.fill(BG_COLOR)

        # 標題
        draw_text(self.screen, "Collaboration Game", self.font_large, WHITE, (WIDTH // 2, 150), center=True)

        # 簡短說明
        draw_text(
            self.screen,
            "This experiment uses default settings. Press START or ENTER to begin.",
            self.font_medium,
            LIGHT_GRAY,
            (WIDTH // 2, 240),
            center=True,
        )

        # Start 按鈕
        self.start_button_rect = pg.Rect(WIDTH // 2 - 130, 540, 260, 60)
        pg.draw.rect(self.screen, GRAY, self.start_button_rect, border_radius=8)
        draw_text(self.screen, "START", self.font_medium, WHITE, self.start_button_rect.center, center=True)

        # 輔助說明
        draw_text(
            self.screen,
            "Press A to start.",
            self.font_small,
            LIGHT_GRAY,
            (WIDTH // 2, 620),
            center=True,
        )

    def draw_round(self):
        import pygame as pg

        if WIDTH < 2 or HEIGHT < 2:
            return

        # 畫可移動範圍分界線（位於畫面高度的一半）
        line_y = HEIGHT // 2
        # 半透明橫線
        line_surf = pg.Surface((WIDTH, 3), flags=pg.SRCALPHA)
        line_surf.fill((180, 180, 180, 140))
        self.screen.blit(line_surf, (0, line_y - 1))
        # 模式下拉選單（左上角）
        self.mode_selector.draw(self.screen, GRAY, WHITE)
        # 訊號下拉選單（模式旁）
        self.signal_selector.draw(self.screen, GRAY, WHITE)
        # 右上角資訊按鈕
        self.draw_info_button()
        # 上方麥克風狀態
        self.draw_mic_status()
        # 畫下落目標
        if getattr(self, "target_img", None):
            rect = self.target_img.get_rect(center=(int(self.ball_x), int(self.ball_y)))
            self.screen.blit(self.target_img, rect)
        else:
            pg.draw.circle(self.screen, WHITE, (int(self.ball_x), int(self.ball_y)), BALL_R)

        # 人類準心（圖片或 fallback）
        if self.human_active():
            if getattr(self, "human_cross_img", None):
                rect = self.human_cross_img.get_rect(center=(int(self.human_x), int(self.human_y)))
                self.screen.blit(self.human_cross_img, rect)
            else:
                cx, cy = int(self.human_x), int(self.human_y)
                pg.draw.line(self.screen, BLUE, (cx - 25, cy), (cx + 25, cy), 4)
                pg.draw.line(self.screen, BLUE, (cx, cy - 25), (cx, cy + 25), 4)

        # AI 準心（圖片或 fallback）
        if self.agent_active():
            if getattr(self, "ai_cross_img", None):
                rect = self.ai_cross_img.get_rect(center=(int(self.agent_x), int(self.agent_y)))
                self.screen.blit(self.ai_cross_img, rect)
            else:
                cx, cy = int(self.agent_x), int(self.agent_y)
                pg.draw.line(self.screen, ORANGE, (cx - 25, cy), (cx + 25, cy), 4)
                pg.draw.line(self.screen, ORANGE, (cx, cy - 25), (cx, cy + 25), 4)

        # 繪製爆炸效果（半透明擴散圈）
        for e in getattr(self, "explosions", []):
            life = (time.time() - e["t"]) / e["dur"]
            # 視覺放大 EXPLOSION_VISUAL_SCALE 倍
            base_r = int(e["r"] * (0.6 + 0.8 * (1 - life)))
            r = max(1, int(base_r * EXPLOSION_VISUAL_SCALE))
            alpha = int(220 * max(0.0, (1 - life)))
            surf = pg.Surface((r * 2 + 4, r * 2 + 4), flags=pg.SRCALPHA)
            color = (255, 200, 80) if e["owner"] == "agent" else (255, 90, 90)
            surf.fill((0, 0, 0, 0))
            pg.draw.circle(surf, color + (alpha,), (r + 2, r + 2), r)
            self.screen.blit(surf, (int(e["x"] - r - 2), int(e["y"] - r - 2 + VISUAL_Y_OFFSET)))

        # 準心閃頻覆蓋（human / ai）
        if getattr(self, "human_flash_ms", 0) > 0:
            fx = int(self.human_x)
            fy = int(self.human_y + VISUAL_Y_OFFSET)
            radius = 40
            surf = pg.Surface((radius * 2, radius * 2), flags=pg.SRCALPHA)
            alpha = int(180 * min(1.0, self.human_flash_ms / 1000.0))
            pg.draw.circle(surf, (255, 220, 60, alpha), (radius, radius), radius)
            self.screen.blit(surf, (fx - radius, fy - radius))
        if getattr(self, "ai_flash_ms", 0) > 0:
            if self.agent_active():
                fx = int(self.agent_x)
                fy = int(self.agent_y + VISUAL_Y_OFFSET)
                radius = 40
                surf = pg.Surface((radius * 2, radius * 2), flags=pg.SRCALPHA)
                alpha = int(180 * min(1.0, self.ai_flash_ms / 1000.0))
                pg.draw.circle(surf, (255, 120, 120, alpha), (radius, radius), radius)
                self.screen.blit(surf, (fx - radius, fy - radius))

        # 右上角顯示實驗統計：衝突次數 / 得分 / 失誤（使用回合內變數）
        stats_text = f"Conflicts: {self.round_collisions}   Score: {self.round_score}   Errors: {self.round_errors}"
        stats_surf = self.font_small.render(stats_text, True, WHITE)
        stats_right = WIDTH - 20
        if self.info_button_rect:
            stats_right = min(stats_right, self.info_button_rect.left - 12)
        stats_y = self.mode_selector.rect.top + (self.mode_selector.rect.height - stats_surf.get_height()) // 2
        self.screen.blit(stats_surf, (stats_right - stats_surf.get_width(), stats_y))

        # 左下角顯示 round（移除 condition）
        info_text = f"User: {self.current_user_id} | Round {self.current_round}/{self.total_rounds}"
        draw_text(self.screen, info_text, self.font_small, LIGHT_GRAY, (20, HEIGHT - 30))

    def draw_break(self):
        # 回合結果畫面
        draw_text(
            self.screen,
            f"Round {self.current_round} completed",
            self.font_large,
            WHITE,
            (WIDTH // 2, HEIGHT // 2 - 60),
            center=True,
        )
        draw_text(
            self.screen,
            f"Score: {self.round_score}   Errors: {self.round_errors}",
            self.font_medium,
            WHITE,
            (WIDTH // 2, HEIGHT // 2),
            center=True,
        )

        if self.current_round < self.total_rounds:
            msg = "Press SPACE or click below to start next round"
            btn_text = "[ Next Round ]"
        else:
            msg = "All rounds completed. Press SPACE or click below to see summary"
            btn_text = "[ Finish ]"

        draw_text(
            self.screen,
            msg,
            self.font_small,
            LIGHT_GRAY,
            (WIDTH // 2, HEIGHT // 2 + 40),
            center=True,
        )

        # 中間當作「按鈕」的區域
        center_rect = pg.Rect(0, 0, 400, 60)
        center_rect.center = (WIDTH // 2, HEIGHT // 2 + 80)
        pg.draw.rect(self.screen, GRAY, center_rect, border_radius=8)
        draw_text(
            self.screen,
            btn_text,
            self.font_medium,
            WHITE,
            center_rect.center,
            center=True,
        )

        draw_text(
            self.screen,
            "Press H to go Home",
            self.font_small,
            LIGHT_GRAY,
            (WIDTH // 2, HEIGHT - 60),
            center=True,
        )

    def draw_done(self):
        draw_text(
            self.screen,
            "Experiment Finished",
            self.font_large,
            WHITE,
            (WIDTH // 2, HEIGHT // 2 - 80),
            center=True,
        )
        draw_text(
            self.screen,
            f"Total Score: {self.total_score}",
            self.font_medium,
            WHITE,
            (WIDTH // 2, HEIGHT // 2 - 20),
            center=True,
        )
        draw_text(
            self.screen,
            f"Total Errors: {self.total_errors}",
            self.font_medium,
            WHITE,
            (WIDTH // 2, HEIGHT // 2 + 20),
            center=True,
        )

        draw_text(
            self.screen,
            "Press H to return Home",
            self.font_small,
            LIGHT_GRAY,
            (WIDTH // 2, HEIGHT // 2 + 80),
            center=True,
        )

    def draw_countdown(self):
        remaining = max(0, int(math.ceil(self.countdown_end_time - time.time())))
        if remaining <= 0:
            return
        overlay = pg.Surface((WIDTH, HEIGHT), flags=pg.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))
        text = self.font_large.render(str(remaining), True, WHITE)
        rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self.screen.blit(text, rect)

    def draw_info_button(self):
        rect = self.info_button_rect
        pg.draw.circle(self.screen, (240, 240, 240), rect.center, rect.width // 2)
        pg.draw.circle(self.screen, (150, 150, 150), rect.center, rect.width // 2, 1)
        icon_text = self.font_tiny.render("i", True, (60, 60, 60))
        icon_rect = icon_text.get_rect(center=rect.center)
        self.screen.blit(icon_text, icon_rect)
        self.screen.blit(icon_text, icon_rect.move(1, 0))

    def draw_mic_status(self):
        active = False
        if self.voice_listener is not None:
            active = self.voice_listener.is_active()
        center = (WIDTH // 2, 18)
        radius = 12
        bg = (240, 240, 240) if active else (220, 220, 220)
        fg = (60, 60, 60) if active else (120, 120, 120)
        pg.draw.circle(self.screen, bg, center, radius)
        pg.draw.circle(self.screen, (150, 150, 150), center, radius, 1)
        # mic body
        body = pg.Rect(0, 0, 8, 12)
        body.center = center
        pg.draw.rect(self.screen, fg, body, border_radius=3)
        # mic stem
        pg.draw.line(self.screen, fg, (center[0], center[1] + 7), (center[0], center[1] + 11), 2)
        # mic base
        pg.draw.line(self.screen, fg, (center[0] - 5, center[1] + 11), (center[0] + 5, center[1] + 11), 2)
        if not active:
            pg.draw.line(self.screen, (180, 80, 80), (center[0] - 9, center[1] - 9), (center[0] + 9, center[1] + 9), 2)

    def toggle_voice_listener(self):
        if not self.voice_listener:
            return
        enabled = not self.voice_listener.is_active()
        self.voice_listener.set_enabled(enabled)


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
