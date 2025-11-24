import pygame as pg
import sys
import time
import requests

API_BASE = "http://127.0.0.1:8000"

WIDTH, HEIGHT = 1280, 720
PADDLE_W, PADDLE_H = 160, 18
BALL_R = 10

FPS = 60

def safe_health_check():
    try:
        r = requests.get(f"{API_BASE}/health", timeout=0.2)
        print("Backend:", r.json())
    except Exception as e:
        print("Backend not reachable:", e)


def main():
    pg.init()
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    pg.display.set_caption("Human-AI Collaborative Game (Prototype)")
    clock = pg.time.Clock()

    # 初始位置
    ball_x, ball_y = WIDTH // 2, HEIGHT // 3
    ball_vx, ball_vy = 5, 4

    human_x = WIDTH // 3
    agent_x = WIDTH * 2 // 3
    paddle_y = HEIGHT - 60

    safe_health_check()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0  # 秒

        # --- 處理事件 ---
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False

        keys = pg.key.get_pressed()
        # 人類用左右鍵控制
        if keys[pg.K_LEFT]:
            human_x -= 8
        if keys[pg.K_RIGHT]:
            human_x += 8

        # 簡單限制邊界
        human_x = max(0, min(WIDTH - PADDLE_W, human_x))

        # --- 更新球 ---
        ball_x += ball_vx
        ball_y += ball_vy

        if ball_x - BALL_R <= 0 or ball_x + BALL_R >= WIDTH:
            ball_vx *= -1
        if ball_y - BALL_R <= 0:
            ball_vy *= -1
        if ball_y + BALL_R >= HEIGHT:
            # 掉地上，重置
            ball_x, ball_y = WIDTH // 2, HEIGHT // 3

        # --- 繪圖 ---
        screen.fill((20, 20, 30))

        # 球
        pg.draw.circle(screen, (230, 230, 230), (int(ball_x), int(ball_y)), BALL_R)

        # 人類 paddle
        pg.draw.rect(
            screen,
            (100, 180, 255),
            (int(human_x), paddle_y, PADDLE_W, PADDLE_H),
            border_radius=6,
        )

        # 代理人 paddle（暫時固定）
        pg.draw.rect(
            screen,
            (255, 160, 120),
            (int(agent_x), paddle_y - 80, PADDLE_W, PADDLE_H),
            border_radius=6,
        )

        pg.display.flip()

    pg.quit()
    sys.exit()


if __name__ == "__main__":
    main()
