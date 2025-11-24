import sys
import random
import math
import pygame as pg
from enum import Enum, auto

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

        # 狀態相關
        self.state = GameState.HOME
        self.running = True

        # Home 畫面輸入
        self.user_id_input = ""          # 只接受數字
        self.condition_input = ""        # 只接受 1~4
        self.start_button_rect = pg.Rect(WIDTH // 2 - 100, 540, 200, 60)

        # 實驗與回合資料
        self.current_user_id = None      # 真的開始實驗後才設定
        self.condition_code = None       # 1~4
        self.current_round = 0
        self.total_rounds = TOTAL_ROUNDS

        # 回合內的統計
        self.round_score = 0
        self.round_errors = 0
        self.total_score = 0
        self.total_errors = 0

        # 計時與暫停
        self.round_start_ms = None
        self.round_paused = False
        self.round_pause_start_ms = None
        self.round_total_paused_ms = 0

        # 球與 paddle
        self.reset_round_objects()
        self.conflict_flash_ms = 0  # paddles 衝突後的閃爍計時

        # UI 按鈕（回合中）
        self.pause_button_rect = pg.Rect(20, 20, 120, 40)
        self.home_button_rect = pg.Rect(160, 20, 120, 40)

    # --- 共用邏輯 ---

    def reset_round_objects(self):
        """重置球與 paddle 的位置與速度"""
        # 球位置與速度改為隨機，避免每次都相同
        self.reset_ball_random()

        # paddle 起始位置：人類在下半，代理在上半
        self.human_x = WIDTH // 2 - PADDLE_W // 2
        self.human_y = int(HEIGHT * 0.82)

        self.agent_x = WIDTH // 2 - PADDLE_W // 2
        self.agent_y = int(HEIGHT * 0.72)

    def reset_round_stats(self):
        self.round_score = 0
        self.round_errors = 0
        self.round_start_ms = pg.time.get_ticks()
        self.round_total_paused_ms = 0
        self.round_paused = False
        self.round_pause_start_ms = None
        self.reset_round_objects()
        self.conflict_flash_ms = 0

    def get_elapsed_ms(self):
        """回傳本回合已經過的毫秒數（扣掉暫停時間）"""
        if self.round_start_ms is None:
            return 0
        now = pg.time.get_ticks()
        if self.round_paused and self.round_pause_start_ms is not None:
            paused_duration = now - self.round_pause_start_ms
        else:
            paused_duration = 0
        return now - self.round_start_ms - self.round_total_paused_ms - paused_duration

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
        pg.quit()
        sys.exit()

    # --- 事件處理 ---

    def handle_events(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.running = False
            elif event.type == pg.VIDEORESIZE:
                self.handle_resize(event)

            if self.state == GameState.HOME:
                self.handle_events_home(event)
            elif self.state == GameState.ROUND:
                self.handle_events_round(event)
            elif self.state == GameState.BREAK:
                self.handle_events_break(event)
            elif self.state == GameState.DONE:
                self.handle_events_done(event)

    def handle_events_home(self, event):
        if event.type == pg.KEYDOWN:
            # user_id / condition 輸入：只接受數字與 Backspace
            if event.key == pg.K_BACKSPACE:
                # Shift + Backspace → 刪 condition；一般 Backspace → 刪 user_id
                #（你可以改成用 Tab 切換 focus，這裡先用簡單版規則）
                if pg.key.get_mods() & pg.KMOD_SHIFT:
                    self.condition_input = self.condition_input[:-1]
                else:
                    self.user_id_input = self.user_id_input[:-1]
            else:
                if event.unicode.isdigit():
                    # 如果按的是 1~4，而且 condition 還沒填，就優先當作 condition
                    if event.unicode in "1234" and len(self.condition_input) < 1:
                        self.condition_input += event.unicode
                    else:
                        self.user_id_input += event.unicode

            # Enter 啟動實驗
            if event.key == pg.K_RETURN:
                self.try_start_experiment()

        elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            # 目前僅保留 Enter 啟動，按鈕已移除
            pass

    def handle_resize(self, event):
        """視窗縮放時重新取得尺寸，讓 UI 保持置中。"""
        global WIDTH, HEIGHT
        WIDTH, HEIGHT = event.w, event.h
        self.screen = pg.display.set_mode((WIDTH, HEIGHT), pg.RESIZABLE)

    def try_start_experiment(self):
        user_id_str = self.user_id_input.strip()
        cond_str = self.condition_input.strip()

        if not user_id_str:
            print("user_id is empty, cannot start.")
            return

        if not cond_str:
            print("condition is empty, cannot start.")
            return

        try:
            user_id_val = int(user_id_str)
        except ValueError:
            print("user_id must be integer.")
            return

        try:
            cond_val = int(cond_str)
        except ValueError:
            print("condition must be 1-4.")
            return

        if cond_val not in CONDITIONS:
            print("condition must be between 1 and 4.")
            return

        self.current_user_id = user_id_val
        self.condition_code = cond_val
        self.current_round = 1
        # 重置總成績
        self.total_score = 0
        self.total_errors = 0
        # 進入第一回合
        self.reset_round_stats()
        self.state = GameState.ROUND
        print(
            f"Start experiment: user_id={self.current_user_id}, "
            f"condition={self.condition_code} ({CONDITIONS[self.condition_code][0]})"
        )

    def reset_ball_random(self):
        """球落地或回合開始時，隨機重生球的位置與速度。"""
        self.ball_x = random.randint(BALL_R + 10, WIDTH - BALL_R - 10)
        self.ball_y = random.randint(HEIGHT // 6, HEIGHT // 3)
        # 隨機速度與方向，確保 vy 往下（整體慢一些）
        speed_x = random.randint(2, 7)
        speed_y = random.randint(2, 6)
        self.ball_vx = speed_x if random.choice([True, False]) else -speed_x
        self.ball_vy = speed_y
        self.clamp_ball_speed()

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

    def rotate_velocity(self, deg_min: float = 20, deg_max: float = 35) -> None:
        """將速度向量旋轉一個隨機角度（deg_min~deg_max），增加角度變化。"""
        angle_deg = random.uniform(deg_min, deg_max)
        angle_deg *= 1 if random.choice([True, False]) else -1
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        vx, vy = self.ball_vx, self.ball_vy
        self.ball_vx = vx * cos_a - vy * sin_a
        self.ball_vy = vx * sin_a + vy * cos_a

    def handle_events_round(self, event):
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            # Pause / Resume
            if self.pause_button_rect.collidepoint(event.pos):
                self.toggle_pause()
            # Home
            elif self.home_button_rect.collidepoint(event.pos):
                self.go_home()

        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                self.go_home()

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

    def toggle_pause(self):
        if not self.round_paused:
            # 進入暫停
            self.round_paused = True
            self.round_pause_start_ms = pg.time.get_ticks()
        else:
            # 結束暫停，補償時間
            now = pg.time.get_ticks()
            if self.round_pause_start_ms is not None:
                self.round_total_paused_ms += now - self.round_pause_start_ms
            self.round_pause_start_ms = None
            self.round_paused = False

    def go_home(self):
        # 回首頁時重置狀態，但保留已輸入的 user_id / condition（你要清空也可以改這裡）
        self.state = GameState.HOME
        self.current_user_id = None
        self.condition_code = None
        self.current_round = 0
        self.round_start_ms = None
        self.round_paused = False
        self.round_pause_start_ms = None
        self.round_total_paused_ms = 0
        self.total_score = 0
        self.total_errors = 0
        print("Return to HOME")

    def go_next_round_or_done(self):
        if self.current_round < self.total_rounds:
            self.current_round += 1
            self.reset_round_stats()
            self.state = GameState.ROUND
            print(f"Start round {self.current_round}")
        else:
            self.state = GameState.DONE
            print("Experiment DONE")

    # --- 更新邏輯 ---

    def update(self, dt):
        if self.state == GameState.ROUND:
            self.update_round(dt)

    def update_round(self, dt):
        # 回合暫停時不更新物理也不結束計時
        if self.round_paused:
            return

        # 衝突暫停：只凍結 paddle，球照常運動
        freeze_active = getattr(self, "conflict_freeze_ms", 0) > 0
        if freeze_active:
            self.conflict_freeze_ms = max(0, self.conflict_freeze_ms - dt * 1000)

        # 衝突閃爍倒數
        if self.conflict_flash_ms > 0:
            self.conflict_flash_ms = max(0, self.conflict_flash_ms - dt * 1000)

        # 更新球
        self.ball_x += self.ball_vx
        self.ball_y += self.ball_vy

        # 邊界反彈
        if self.ball_x - BALL_R <= 0 or self.ball_x + BALL_R >= WIDTH:
            self.ball_vx *= -1
            # 每次反彈旋轉角度 20~35 度
            self.rotate_velocity(20, 35)
            self.clamp_ball_speed()
        if self.ball_y - BALL_R <= 0:
            self.ball_vy *= -1
            self.rotate_velocity(20, 35)
            # 反彈後仍確保往下
            self.ball_vy = abs(self.ball_vy)
            self.clamp_ball_speed()

        if not freeze_active:
            keys = pg.key.get_pressed()
            # 人類 paddle 控制：上下左右
            speed = 3.5
            if keys[pg.K_LEFT]:
                self.human_x -= speed
            if keys[pg.K_RIGHT]:
                self.human_x += speed
            if keys[pg.K_UP]:
                self.human_y -= speed
            if keys[pg.K_DOWN]:
                self.human_y += speed

            # 代理簡單 AI：朝球靠近，限制在下半部，增加 y 軸隨機性
            agent_speed = 3
            if self.ball_x > self.agent_x + PADDLE_W / 2:
                self.agent_x += agent_speed
            elif self.ball_x < self.agent_x + PADDLE_W / 2:
                self.agent_x -= agent_speed

            jitter = random.uniform(-1.5, 1.5)
            target_y = self.ball_y + jitter * 40
            if target_y > self.agent_y + PADDLE_H / 2:
                self.agent_y += agent_speed
            elif target_y < self.agent_y + PADDLE_H / 2:
                self.agent_y -= agent_speed

        # 限制在人類/代理的工作區域（下半部）
        self.human_x = max(0, min(WIDTH - PADDLE_W, self.human_x))
        self.human_y = max(HEIGHT // 2, min(HEIGHT - PADDLE_H, self.human_y))

        min_agent_y = int(HEIGHT * 0.55)  # 讓代理更貼近下方，不要卡在頂端
        self.agent_x = max(0, min(WIDTH - PADDLE_W, self.agent_x))
        self.agent_y = max(min_agent_y, min(HEIGHT - PADDLE_H, self.agent_y))

        # Agent 暫時固定不動（之後換成 DIR + rule-based 移動）
        # self.agent_x += 4
        # if self.agent_x <= 0 or self.agent_x + PADDLE_W >= WIDTH:
        #     self.agent_x = max(0, min(WIDTH - PADDLE_W, self.agent_x))

        # 碰撞檢查（簡單版）
        self.check_collisions()

        # 檢查回合時間是否結束
        elapsed = self.get_elapsed_ms()
        if elapsed >= ROUND_DURATION_MS:
            # 回合結束，累計總成績
            self.total_score += self.round_score
            self.total_errors += self.round_errors
            self.state = GameState.BREAK
            print(
                f"End round {self.current_round}: score={self.round_score}, "
                f"errors={self.round_errors}"
            )

    def check_collisions(self):
        # 球和人類、代理人 paddle
        human_rect = pg.Rect(self.human_x, self.human_y, PADDLE_W, PADDLE_H)
        agent_rect = pg.Rect(self.agent_x, self.agent_y, PADDLE_W, PADDLE_H)
        ball_rect = pg.Rect(
            self.ball_x - BALL_R, self.ball_y - BALL_R, BALL_R * 2, BALL_R * 2
        )

        caught = False

        if ball_rect.colliderect(human_rect):
            self.ball_vy = -abs(self.ball_vy)  # 向上彈
            self.rotate_velocity(20, 35)
            self.ball_vy = -abs(self.ball_vy)
            self.clamp_ball_speed()
            self.round_score += 1
            caught = True

        if ball_rect.colliderect(agent_rect):
            self.ball_vy = -abs(self.ball_vy)  # 同樣往上打
            self.rotate_velocity(20, 35)
            self.ball_vy = -abs(self.ball_vy)
            self.clamp_ball_speed()
            if not caught:
                self.round_score += 1
                caught = True

        # 球落出畫面底部 → 失誤一次（paddle 不重置，球隨機重生）
        if self.ball_y - BALL_R > HEIGHT:
            self.round_errors += 1
            self.reset_ball_random()

        # paddle 互相碰撞：彈開 + 閃爍
        if human_rect.colliderect(agent_rect):
            overlap = human_rect.clip(agent_rect)
            push = overlap.height / 2 + 2
            # 兩個都在下半部，往上下推開
            self.human_y += push
            self.agent_y -= push
            self.human_y = max(HEIGHT // 2, min(HEIGHT - PADDLE_H, self.human_y))
            self.agent_y = max(HEIGHT // 2, min(HEIGHT - PADDLE_H, self.agent_y))
            # 衝突視為一次錯誤
            self.round_errors += 1
            self.conflict_flash_ms = 300
            self.conflict_freeze_ms = 300

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

        pg.display.flip()

    def draw_home(self):
        # 標題
        draw_text(self.screen, "Collaboration Game", self.font_large, WHITE, (WIDTH // 2, 150), center=True)

        # 統一欄寬、靠左對齊的輸入列
        base_y = 260
        row_gap = 70
        label_x = WIDTH // 2 - 260
        box_width = 300
        box_height = 44
        box_x = label_x + 200  # 左側留給標籤

        # condition 列
        cond_label = self.font_medium.render("condition (1~4):", True, WHITE)
        cond_y = base_y
        self.screen.blit(cond_label, (label_x, cond_y - cond_label.get_height() // 2))
        cond_box = pg.Rect(box_x, cond_y - box_height // 2, box_width, box_height)
        pg.draw.rect(self.screen, WHITE, cond_box, width=2, border_radius=6)
        draw_text(
            self.screen,
            self.condition_input or "plz input 1~4",
            self.font_small,
            LIGHT_GRAY,
            (cond_box.x + 10, cond_box.y + 10),
        )

        # user_id 列
        user_label = self.font_medium.render("user_id:", True, WHITE)
        user_y = base_y + row_gap
        self.screen.blit(user_label, (label_x, user_y - user_label.get_height() // 2))
        user_box = pg.Rect(box_x, user_y - box_height // 2, box_width, box_height)
        pg.draw.rect(self.screen, WHITE, user_box, width=2, border_radius=6)
        draw_text(
            self.screen,
            self.user_id_input or "plz input user_id",
            self.font_small,
            LIGHT_GRAY,
            (user_box.x + 10, user_box.y + 10),
        )

        # Condition 說明列表（先隱藏，需要時可取消註解）
        # y = 330
        # for code, (_, label) in CONDITIONS.items():
        #     text = f"{code} - {label}"
        #     draw_text(self.screen, text, self.font_small, LIGHT_GRAY, (WIDTH // 2, y), center=True)
        #     y += 22

        draw_text(
            self.screen,
            "Press ENTER to start",
            self.font_small,
            LIGHT_GRAY,
            (WIDTH // 2, 420),
            center=True,
        )

    def draw_round(self):
        # 上方 UI
        # Pause / Home 按鈕
        pg.draw.rect(self.screen, GRAY, self.pause_button_rect, border_radius=6)
        draw_text(
            self.screen,
            "Resume" if self.round_paused else "Pause",
            self.font_small,
            WHITE,
            self.pause_button_rect.center,
            center=True,
        )

        pg.draw.rect(self.screen, GRAY, self.home_button_rect, border_radius=6)
        draw_text(
            self.screen,
            "Home",
            self.font_small,
            WHITE,
            self.home_button_rect.center,
            center=True,
        )

        # Score / Errors
        score_text = f"Score: {self.round_score}"
        error_text = f"Errors: {self.round_errors}"
        draw_text(
            self.screen,
            score_text,
            self.font_small,
            WHITE,
            (WIDTH // 2 - 80, 20),
        )
        draw_text(
            self.screen,
            error_text,
            self.font_small,
            WHITE,
            (WIDTH // 2 - 80, 45),
        )

        # 計時
        elapsed = self.get_elapsed_ms()
        remaining_sec = max(0, int((ROUND_DURATION_MS - elapsed) / 1000))
        time_text = f"Time left: {remaining_sec}s"
        draw_text(
            self.screen,
            time_text,
            self.font_small,
            WHITE,
            (WIDTH // 2 + 120, 20),
        )

        # 畫球
        pg.draw.circle(
            self.screen,
            WHITE,
            (int(self.ball_x), int(self.ball_y)),
            BALL_R,
        )

        # paddles（衝突時閃爍）
        flash = self.conflict_flash_ms > 0
        human_color = (255, 90, 90) if flash else BLUE
        agent_color = (255, 200, 90) if flash else ORANGE

        pg.draw.rect(
            self.screen,
            human_color,
            (int(self.human_x), int(self.human_y), PADDLE_W, PADDLE_H),
            border_radius=6,
        )

        pg.draw.rect(
            self.screen,
            agent_color,
            (int(self.agent_x), int(self.agent_y), PADDLE_W, PADDLE_H),
            border_radius=6,
        )

        # 顯示 round 與 condition
        cond_label = CONDITIONS[self.condition_code][1] if self.condition_code else "N/A"
        info_text = (
            f"User: {self.current_user_id} | "
            f"Round {self.current_round}/{self.total_rounds} | "
            f"Condition: {cond_label}"
        )
        draw_text(
            self.screen,
            info_text,
            self.font_small,
            LIGHT_GRAY,
            (20, HEIGHT - 30),
        )

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


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
