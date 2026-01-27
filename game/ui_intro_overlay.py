import math
import random
import time
import pygame as pg


class IntroOverlay:
    def __init__(self, image_paths):
        self.images = []
        for path in image_paths:
            try:
                self.images.append(pg.image.load(str(path)).convert_alpha())
            except Exception:
                self.images.append(None)
        self.index = 0
        self.panel_rect = pg.Rect(0, 0, 100, 100)
        self.prev_rect = pg.Rect(0, 0, 40, 40)
        self.next_rect = pg.Rect(0, 0, 40, 40)
        self.close_rect = pg.Rect(0, 0, 28, 28)
        self.practice_rect = pg.Rect(0, 0, 0, 0)
        self.practice_cross_pos = None
        self.practice_target_pos = None
        self.practice_target_vel = None
        self.practice_cross_img = None
        self.practice_target_img = None
        self.practice_signal_img_my = None
        self.practice_signal_img_left = None
        self.practice_signal_img_right = None
        self.practice_enabled = False
        self.lt_axis_latched = False
        self.rt_axis_latched = False
        self.practice_explosions = []
        self.explosion_visual_scale = 1.25
        self.visual_y_offset = -2
        self.practice_snd_hit = None
        self.practice_snd_shoot = None
        self.practice_sound_loaded = False
        self.practice_signal_img = None
        self.practice_signal_until = 0.0
        self.page_limit = None
        self.practice_speed_px_per_sec = 180.0
        self.practice_hit_count = 0
        self._last_index = 0

    def set_practice_assets(self, cross_img, target_img):
        self.practice_cross_img = cross_img
        self.practice_target_img = target_img
        self.practice_enabled = cross_img is not None or target_img is not None
        self.practice_sound_loaded = False
        self.practice_hit_count = 0

    def set_practice_signal_assets(self, my_img, left_img, right_img):
        self.practice_signal_img_my = my_img
        self.practice_signal_img_left = left_img
        self.practice_signal_img_right = right_img

    def set_practice_speed(self, speed_px_per_sec: float) -> None:
        if speed_px_per_sec > 0:
            self.practice_speed_px_per_sec = float(speed_px_per_sec)

    def set_images(self, image_paths):
        self.images = []
        for path in image_paths:
            try:
                self.images.append(pg.image.load(str(path)).convert_alpha())
            except Exception:
                self.images.append(None)
        self.practice_hit_count = 0

    def _ensure_practice_sound(self):
        if self.practice_sound_loaded:
            return
        self.practice_sound_loaded = True
        try:
            if not pg.mixer.get_init():
                pg.mixer.init()
        except Exception:
            return
        try:
            import os
            base_dir = os.path.dirname(__file__)
            hit_path = os.path.join(base_dir, "source", "rifle.mp3")
            shoot_path = os.path.join(base_dir, "source", "shoot.mp3")
            try:
                self.practice_snd_hit = pg.mixer.Sound(hit_path)
            except Exception:
                self.practice_snd_hit = None
            try:
                self.practice_snd_shoot = pg.mixer.Sound(shoot_path)
            except Exception:
                self.practice_snd_shoot = None
        except Exception:
            self.practice_snd_hit = None
            self.practice_snd_shoot = None

    def handle_event(self, event):
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect.collidepoint(event.pos):
                return None
            if self.prev_rect.collidepoint(event.pos):
                self.prev()
                return "nav"
            if self.next_rect.collidepoint(event.pos):
                self.next()
                return "nav"
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_x:
                self.prev()
                return "nav"
            if event.key == pg.K_b:
                self.next()
                return "nav"
            if self.index == 3 and event.key == pg.K_c:
                self.practice_signal_left_right()
                return "practice"
            if self.index == 3 and event.key == pg.K_v:
                self.practice_signal_my()
                return "practice"
        if event.type == pg.JOYBUTTONDOWN:
            if event.button == 2:
                self.prev()
                return "nav"
            if event.button == 1:
                self.next()
                return "nav"
            if event.button in (6, 4):
                return "start"
            if event.button == 0:
                self.practice_shoot()
                return "practice"
            if self.index == 3 and event.button == 3:
                self.practice_signal_left_right()
                return "practice"
            if self.index == 3 and event.button in (7, 5):
                self.practice_signal_my()
                return "practice"
        if event.type == pg.JOYAXISMOTION:
            if event.axis in (2, 4):
                if event.value > 0.6 and not self.lt_axis_latched:
                    self.lt_axis_latched = True
                    return "start"
                if event.value < 0.2:
                    self.lt_axis_latched = False
            if self.index == 3 and event.axis in (5, 3):
                if event.value > 0.6 and not self.rt_axis_latched:
                    self.rt_axis_latched = True
                    self.practice_signal_my()
                    return "practice"
                if event.value < 0.2:
                    self.rt_axis_latched = False
        return None

    def set_page_limit(self, limit):
        if limit is not None and limit < 1:
            limit = 1
        self.page_limit = limit
        total_pages = self._page_count()
        if total_pages > 0 and self.index >= total_pages:
            self.index = total_pages - 1

    def _page_count(self):
        total = len(self.images)
        if self.page_limit is not None:
            total = min(total, self.page_limit)
        return total

    def prev(self):
        if self.index > 0:
            self.index -= 1

    def next(self):
        if self.index < self._page_count() - 1:
            self.index += 1

    def update(self, dt, joystick, screen_w, screen_h):
        if self.index != self._last_index:
            if self._last_index == 2:
                self.practice_hit_count = 0
            self._last_index = self.index
        if not self.practice_enabled or self.index != 2:
            return
        self._layout(screen_w, screen_h)
        if self.practice_rect.width <= 0 or self.practice_rect.height <= 0:
            return

        if self.practice_cross_pos is None:
            self.practice_cross_pos = [self.practice_rect.centerx, self.practice_rect.bottom]

        move_x = 0.0
        move_y = 0.0
        if joystick:
            try:
                ax = joystick.get_axis(0)
                ay = joystick.get_axis(1)
                if abs(ax) < 0.2:
                    ax = 0.0
                if abs(ay) < 0.2:
                    ay = 0.0
                move_x += ax
                move_y += ay
            except Exception:
                pass

        speed = self.practice_speed_px_per_sec
        self.practice_cross_pos[0] += move_x * speed * dt
        self.practice_cross_pos[1] += move_y * speed * dt
        self.practice_cross_pos[0] = max(
            self.practice_rect.left, min(self.practice_rect.right, self.practice_cross_pos[0])
        )
        self.practice_cross_pos[1] = max(
            self.practice_rect.top, min(self.practice_rect.bottom, self.practice_cross_pos[1])
        )

        if self.practice_target_pos is None or self.practice_target_vel is None:
            self._spawn_practice_target()

        self.practice_target_pos[0] += self.practice_target_vel[0] * dt
        self.practice_target_pos[1] += self.practice_target_vel[1] * dt
        if random.random() < 0.06:
            self.practice_target_vel[0] += random.uniform(-35.0, 35.0)
            self.practice_target_vel[0] = max(-80.0, min(80.0, self.practice_target_vel[0]))
        if self.practice_target_pos[0] < self.practice_rect.left + 8:
            self.practice_target_pos[0] = self.practice_rect.left + 8
            self.practice_target_vel[0] = abs(self.practice_target_vel[0])
        if self.practice_target_pos[0] > self.practice_rect.right - 8:
            self.practice_target_pos[0] = self.practice_rect.right - 8
            self.practice_target_vel[0] = -abs(self.practice_target_vel[0])
        if self.practice_target_pos[1] > self.practice_rect.bottom + 20:
            self._spawn_practice_target()
        if self.practice_explosions:
            now = time.time()
            self.practice_explosions = [e for e in self.practice_explosions if now - e["t"] <= e["dur"]]

    def practice_shoot(self):
        if self.index != 2 or self.practice_target_pos is None:
            return
        self._ensure_practice_sound()
        cx, cy = self.practice_cross_pos or (0.0, 0.0)
        tx, ty = self.practice_target_pos
        dist = math.hypot(tx - cx, ty - cy)
        if self.practice_cross_img is not None:
            cross_r = self.practice_cross_img.get_width() / 2.0
        else:
            cross_r = 22.0
        inner_r = cross_r * 0.35
        if dist <= inner_r:
            now = time.time()
            self.practice_explosions.append(
                {"x": tx, "y": ty, "t": now, "dur": 0.28, "r": cross_r}
            )
            try:
                if self.practice_snd_hit:
                    self.practice_snd_hit.play()
            except Exception:
                pass
            self.practice_hit_count += 1
            if self.practice_hit_count >= 20:
                self.practice_target_pos = None
                self.practice_target_vel = None
                self.practice_cross_pos = None
                self.index = min(3, self._page_count() - 1)
                return
            self._spawn_practice_target()
        else:
            try:
                if self.practice_snd_shoot:
                    self.practice_snd_shoot.play()
            except Exception:
                pass

    def practice_signal_my(self):
        if self.index != 3:
            return
        self.practice_signal_img = self.practice_signal_img_my
        self.practice_signal_until = time.time() + 0.8

    def practice_signal_left_right(self):
        if self.index != 3 or not self.practice_cross_pos:
            return
        center_x = self.practice_rect.centerx
        if self.practice_cross_pos[0] < center_x:
            self.practice_signal_img = self.practice_signal_img_left
        else:
            self.practice_signal_img = self.practice_signal_img_right
        self.practice_signal_until = time.time() + 0.8

    def _spawn_practice_target(self):
        x = random.uniform(self.practice_rect.left + 12, self.practice_rect.right - 12)
        y = self.practice_rect.top - 20
        vx = random.uniform(-18.0, 18.0)
        vy = random.uniform(40.0, 60.0)
        self.practice_target_pos = [x, y]
        self.practice_target_vel = [vx, vy]
        if self.practice_rect.width > 0 and self.practice_rect.height > 0:
            self.practice_cross_pos = [self.practice_rect.centerx, self.practice_rect.bottom]

    def draw(self, surface, font, screen_w, screen_h):
        self._layout(screen_w, screen_h)
        overlay = pg.Surface((screen_w, screen_h), flags=pg.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        surface.blit(overlay, (0, 0))

        shadow = self.panel_rect.move(4, 4)
        pg.draw.rect(surface, (20, 20, 28), shadow, border_radius=14)
        pg.draw.rect(surface, (245, 245, 245), self.panel_rect, border_radius=14)

        total_pages = self._page_count()
        img = self.images[self.index] if self.images and self.index < total_pages else None
        if img:
            max_w = int(self.panel_rect.width * 0.90)
            max_h = int(self.panel_rect.height * 0.90)
            scale = min(max_w / img.get_width(), max_h / img.get_height())
            scaled = pg.transform.smoothscale(
                img,
                (max(1, int(img.get_width() * scale)), max(1, int(img.get_height() * scale))),
            )
            img_rect = scaled.get_rect(center=self.panel_rect.center)
            surface.blit(scaled, img_rect)

        if self.practice_enabled and self.practice_rect.width > 0 and self.index == 2:
            pg.draw.rect(surface, (50, 55, 70), self.practice_rect, border_radius=10)
            pg.draw.rect(surface, (120, 120, 120), self.practice_rect, 2, border_radius=10)
            label = f"Hits: {self.practice_hit_count}/20"
            label_surf = font.render(label, True, (20, 20, 20))
            label_rect = label_surf.get_rect()
            label_y = max(8, self.practice_rect.top - label_rect.height - 6)
            label_rect.topright = (self.practice_rect.right, label_y)
            bg_rect = label_rect.inflate(10, 6)
            pg.draw.rect(surface, (255, 255, 255, 220), bg_rect, border_radius=6)
            pg.draw.rect(surface, (120, 120, 120), bg_rect, 1, border_radius=6)
            surface.blit(label_surf, label_rect)
            if self.practice_explosions:
                now = time.time()
                for e in self.practice_explosions:
                    life = (now - e["t"]) / e["dur"]
                    base_r = int(e["r"] * (0.5 + 0.5 * (1 - life)))
                    r = max(1, int(base_r * 0.7))
                    alpha = int(220 * max(0.0, (1 - life)))
                    surf = pg.Surface((r * 2 + 4, r * 2 + 4), flags=pg.SRCALPHA)
                    surf.fill((0, 0, 0, 0))
                    pg.draw.circle(surf, (255, 90, 90, alpha), (r + 2, r + 2), r)
                    surface.blit(
                        surf,
                        (int(e["x"] - r - 2), int(e["y"] - r - 2 + self.visual_y_offset)),
                    )
            if self.practice_target_pos:
                tx, ty = self.practice_target_pos
                if self.practice_target_img:
                    rect = self.practice_target_img.get_rect(center=(int(tx), int(ty)))
                    surface.blit(self.practice_target_img, rect)
                else:
                    pg.draw.circle(surface, (40, 40, 40), (int(tx), int(ty)), 10)
            if self.practice_cross_pos:
                cx, cy = self.practice_cross_pos
                if self.practice_cross_img:
                    rect = self.practice_cross_img.get_rect(center=(int(cx), int(cy)))
                    surface.blit(self.practice_cross_img, rect)
                else:
                    pg.draw.line(surface, (50, 120, 255), (cx - 12, cy), (cx + 12, cy), 3)
                    pg.draw.line(surface, (50, 120, 255), (cx, cy - 12), (cx, cy + 12), 3)
        # Close button
        self.close_rect = pg.Rect(0, 0, 28, 28)
        self.close_rect.topright = (self.panel_rect.right - 10, self.panel_rect.top + 10)
        pg.draw.rect(surface, (240, 240, 240), self.close_rect, border_radius=8)
        pg.draw.rect(surface, (160, 160, 160), self.close_rect, 1, border_radius=8)
        cx, cy = self.close_rect.center
        pg.draw.line(surface, (60, 60, 60), (cx - 6, cy - 6), (cx + 6, cy + 6), 2)
        pg.draw.line(surface, (60, 60, 60), (cx + 6, cy - 6), (cx - 6, cy + 6), 2)

        # Prev/Next buttons
        btn_y = self.panel_rect.centery - 20
        self.prev_rect = pg.Rect(self.panel_rect.left + 10, btn_y, 40, 40)
        self.next_rect = pg.Rect(self.panel_rect.right - 50, btn_y, 40, 40)
        self._draw_nav_button(surface, self.prev_rect, "<", enabled=self.index > 0)
        self._draw_nav_button(surface, self.next_rect, ">", enabled=self.index < total_pages - 1)

        # Page indicator
        if total_pages > 0:
            page_text = f"{self.index + 1}/{total_pages}"
            text_surf = font.render(page_text, True, (80, 80, 80))
            text_rect = text_surf.get_rect()
            text_rect.midbottom = (self.panel_rect.centerx, self.panel_rect.bottom - 12)
            surface.blit(text_surf, text_rect)
            hint_parts = []
            if self.index > 0:
                hint_parts.append("X: Prev")
            if self.index < total_pages - 1:
                hint_parts.append("B: Next")
            hint_parts.append("LT: Start")
            hint_text = "   ".join(hint_parts)
            hint_surf = font.render(hint_text, True, (255, 255, 255))
            hint_rect = hint_surf.get_rect()
            hint_rect.midtop = (self.panel_rect.centerx, self.panel_rect.bottom + 6)
            surface.blit(hint_surf, hint_rect)

    def _draw_nav_button(self, surface, rect, label, enabled=True):
        bg = (235, 235, 235) if enabled else (210, 210, 210)
        fg = (70, 70, 70) if enabled else (130, 130, 130)
        pg.draw.rect(surface, bg, rect, border_radius=10)
        pg.draw.rect(surface, (150, 150, 150), rect, 1, border_radius=10)
        font = pg.font.SysFont("arial", 22)
        text = font.render(label, True, fg)
        text_rect = text.get_rect(center=rect.center)
        surface.blit(text, text_rect)

    def _layout(self, screen_w, screen_h):
        panel_w = int(screen_w * 0.82 * 0.8)
        panel_h = int(screen_h * 0.82 * 0.8)
        self.panel_rect = pg.Rect(0, 0, panel_w, panel_h)
        self.panel_rect.center = (screen_w // 2, screen_h // 2)
        if self.practice_enabled and self.index in (2, 3):
            gap = 14
            size = int(min(panel_w, panel_h) * 0.5)
            size = max(180, min(size, self.panel_rect.width - gap * 2))
            width_extra = 60 if self.index == 2 else 0
            rect_w = size + width_extra
            right_x = self.panel_rect.right - gap - rect_w - 60
            center_y = self.panel_rect.centery + 60
            height = int(size * 0.9)
            self.practice_rect = pg.Rect(0, 0, rect_w, height)
            self.practice_rect.topleft = (right_x, center_y - size // 2)
        else:
            self.practice_rect = pg.Rect(0, 0, 0, 0)
