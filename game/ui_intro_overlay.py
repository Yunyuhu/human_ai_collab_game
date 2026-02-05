import math
import random
import time
import pygame as pg


class IntroOverlay:
    def __init__(self, image_paths):
        self.images = []
        self._load_images(image_paths)
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
        self.practice_hit_goal = 20
        self.practice_hit_count = 0
        self.practice_signal_goal = 20
        self.practice_signal_count = 0
        self.practice_signal_variant = "none"
        self.practice_signal_prompt = None
        self.practice_signal_prompt_until = 0.0
        self.practice_signal_next_time = 0.0
        self.practice_signal_expected = None
        self.practice_signal_feedback_img = None
        self.practice_signal_feedback_until = 0.0
        self.signal_img_passown = None
        self.signal_img_passyour = None
        self.signal_img_right = None
        self.signal_img_wrong = None
        self.signal_snd_right = None
        self.signal_snd_false = None
        self.signal_snd_wrong = None
        self.signal_assets_loaded = False
        self.last_screen_w = 0
        self.last_screen_h = 0
        self.last_index = 0

    def _load_images(self, image_paths):
        self.images = []
        for path in image_paths:
            try:
                self.images.append(pg.image.load(str(path)).convert_alpha())
            except Exception:
                self.images.append(None)

    def set_images(self, image_paths):
        self._load_images(image_paths)
        self.index = 0

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

    def set_signal_variant(self, variant: str):
        self.practice_signal_variant = variant
        self.practice_signal_count = 0
        self.practice_signal_prompt = None
        self.practice_signal_expected = None
        self.practice_signal_next_time = 0.0
        self.practice_signal_feedback_img = None
        self.practice_signal_feedback_until = 0.0

    def _ensure_signal_assets(self):
        if self.signal_assets_loaded:
            return
        self.signal_assets_loaded = True
        try:
            if not pg.mixer.get_init():
                pg.mixer.init()
        except Exception:
            pass
        try:
            import os
            base_dir = os.path.dirname(__file__)
            passown_path = os.path.join(base_dir, "source", "passown.png")
            passyour_path = os.path.join(base_dir, "source", "passyour.png")
            right_img_path = os.path.join(base_dir, "source", "right.png")
            wrong_img_path = os.path.join(base_dir, "source", "wrong.png")
            right_snd_path = os.path.join(base_dir, "source", "right.mp3")
            false_snd_path = os.path.join(base_dir, "source", "false.mp3")
            wrong_snd_path = os.path.join(base_dir, "source", "wrong.mp3")
            try:
                self.signal_img_passown = pg.image.load(passown_path).convert_alpha()
            except Exception:
                self.signal_img_passown = None
            try:
                self.signal_img_passyour = pg.image.load(passyour_path).convert_alpha()
            except Exception:
                self.signal_img_passyour = None
            try:
                self.signal_img_right = pg.image.load(right_img_path).convert_alpha()
            except Exception:
                self.signal_img_right = None
            try:
                self.signal_img_wrong = pg.image.load(wrong_img_path).convert_alpha()
            except Exception:
                self.signal_img_wrong = None
            if self.signal_img_right:
                self.signal_img_right = pg.transform.smoothscale(
                    self.signal_img_right,
                    (
                        max(1, self.signal_img_right.get_width() // 2),
                        max(1, self.signal_img_right.get_height() // 2),
                    ),
                )
            if self.signal_img_wrong:
                self.signal_img_wrong = pg.transform.smoothscale(
                    self.signal_img_wrong,
                    (
                        max(1, self.signal_img_wrong.get_width() // 2),
                        max(1, self.signal_img_wrong.get_height() // 2),
                    ),
                )
            try:
                self.signal_snd_right = pg.mixer.Sound(right_snd_path)
            except Exception:
                self.signal_snd_right = None
            try:
                self.signal_snd_false = pg.mixer.Sound(false_snd_path)
            except Exception:
                self.signal_snd_false = None
            try:
                self.signal_snd_wrong = pg.mixer.Sound(wrong_snd_path)
            except Exception:
                self.signal_snd_wrong = None
        except Exception:
            self.signal_img_passown = None
            self.signal_img_passyour = None
            self.signal_img_right = None
            self.signal_img_wrong = None
            self.signal_snd_right = None
            self.signal_snd_false = None
            self.signal_snd_wrong = None

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
                return "close"
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
            if event.button == 0:
                self.practice_shoot()
                return "practice"
            if self.index == 3 and event.button == 3:
                self._handle_signal_input("Y")
                return "practice"
            if self.index == 3 and event.button in (7, 5):
                self._handle_signal_input("TR")
                return "practice"
        if event.type == pg.JOYAXISMOTION:
            if self.index == 3 and event.axis in (5, 3):
                if event.value > 0.6 and not self.rt_axis_latched:
                    self.rt_axis_latched = True
                    self._handle_signal_input("TR")
                    return "practice"
                if event.value < 0.2:
                    self.rt_axis_latched = False
        return None

    def prev(self):
        if self.index > 0:
            self.index -= 1

    def next(self):
        if self.index < len(self.images) - 1:
            self.index += 1
            if self.index == 2:
                self.practice_hit_count = 0
                self.practice_cross_pos = None
                self.practice_target_pos = None
                self.practice_target_vel = None

    def update(self, dt, joystick, screen_w, screen_h):
        if not self.practice_enabled:
            return
        if self.index == 3 and self.practice_signal_variant not in ("H", "A"):
            return
        if self.index not in (2, 3):
            return
        self.last_screen_w = screen_w
        self.last_screen_h = screen_h
        self._layout(screen_w, screen_h)
        if self.practice_rect.width <= 0 or self.practice_rect.height <= 0:
            return
        if self.last_index != self.index:
            if self.index == 2:
                self.practice_hit_count = 0
                self.practice_cross_pos = None
                self.practice_target_pos = None
                self.practice_target_vel = None
            if self.index == 3:
                self.practice_signal_count = 0
                self.practice_signal_prompt = None
                self.practice_signal_expected = None
                self.practice_signal_next_time = 0.0
                self.practice_signal_feedback_img = None
                self.practice_signal_feedback_until = 0.0
        self.last_index = self.index

        if self.practice_cross_pos is None:
            self.practice_cross_pos = [self.practice_rect.centerx, self.practice_rect.bottom]

        if self.index == 3 and self.practice_signal_variant in ("H", "A"):
            self._ensure_signal_assets()
            self.practice_cross_pos = [self.practice_rect.centerx, self.practice_rect.bottom - 20]
            self._update_signal_practice()
            if self.practice_signal_count >= self.practice_signal_goal:
                self.next()
            return

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

        speed = 100.0
        self.practice_cross_pos[0] += move_x * speed * dt
        self.practice_cross_pos[1] += move_y * speed * dt
        self.practice_cross_pos[0] = max(
            self.practice_rect.left, min(self.practice_rect.right, self.practice_cross_pos[0])
        )
        self.practice_cross_pos[1] = max(
            self.practice_rect.top, min(self.practice_rect.bottom, self.practice_cross_pos[1])
        )

        if self.practice_hit_count >= self.practice_hit_goal:
            self.next()
            return

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
            if self.practice_rect.width > 0 and self.practice_rect.height > 0:
                self.practice_cross_pos = [self.practice_rect.centerx, self.practice_rect.bottom]
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
        vx = random.uniform(-30.0, 30.0)
        vy = random.uniform(70.0, 95.0)
        self.practice_target_pos = [x, y]
        self.practice_target_vel = [vx, vy]

    def draw(self, surface, font, screen_w, screen_h):
        self._layout(screen_w, screen_h)
        overlay = pg.Surface((screen_w, screen_h), flags=pg.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        surface.blit(overlay, (0, 0))

        shadow = self.panel_rect.move(4, 4)
        pg.draw.rect(surface, (20, 20, 28), shadow, border_radius=14)
        pg.draw.rect(surface, (245, 245, 245), self.panel_rect, border_radius=14)

        img = self.images[self.index] if self.images else None
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
            hits_text = f"Hits: {self.practice_hit_count}/{self.practice_hit_goal}"
            hits_surf = font.render(hits_text, True, (40, 40, 40))
            hits_rect = hits_surf.get_rect()
            hits_rect.midbottom = (self.practice_rect.right - 50, self.practice_rect.top - 6)
            surface.blit(hits_surf, hits_rect)
        if self.practice_enabled and self.practice_rect.width > 0 and self.index == 3 and self.practice_signal_variant in ("H", "A"):
            pg.draw.rect(surface, (50, 55, 70), self.practice_rect, border_radius=10)
            pg.draw.rect(surface, (120, 120, 120), self.practice_rect, 2, border_radius=10)
            split_y = int(self.practice_rect.top + self.practice_rect.height * 0.5)
            pg.draw.line(
                surface,
                (120, 120, 120),
                (self.practice_rect.left, split_y),
                (self.practice_rect.right, split_y),
                2,
            )
            hits_text = f"Hits: {self.practice_signal_count}/{self.practice_signal_goal}"
            hits_surf = font.render(hits_text, True, (40, 40, 40))
            hits_rect = hits_surf.get_rect()
            hits_rect.midbottom = (self.practice_rect.right - 50, self.practice_rect.top - 6)
            surface.blit(hits_surf, hits_rect)
            if self.practice_cross_pos and self.practice_signal_variant != "A":
                cx, cy = self.practice_cross_pos
                img = None
                if self.practice_signal_until > time.time():
                    img = self.practice_signal_img
                if img is None:
                    img = self.practice_cross_img
                if img:
                    rect = img.get_rect(center=(int(cx), int(cy)))
                    surface.blit(img, rect)
                else:
                    pg.draw.line(surface, (50, 120, 255), (cx - 12, cy), (cx + 12, cy), 3)
                    pg.draw.line(surface, (50, 120, 255), (cx, cy - 12), (cx, cy + 12), 3)
            self._draw_signal_prompt(surface, font, split_y)
            self._draw_signal_feedback(surface, split_y)

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
        can_advance = self.index < len(self.images) - 1
        self._draw_nav_button(surface, self.next_rect, ">", enabled=can_advance)

        # Page indicator
        if self.images:
            page_text = f"{self.index + 1}/{len(self.images)}"
            text_surf = font.render(page_text, True, (80, 80, 80))
            text_rect = text_surf.get_rect()
            text_rect.midbottom = (self.panel_rect.centerx, self.panel_rect.bottom - 12)
            surface.blit(text_surf, text_rect)

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
        if self.practice_enabled and (self.index == 2 or (self.index == 3 and self.practice_signal_variant in ("H", "A"))):
            gap = 14
            size = int(min(panel_w, panel_h) * 0.55)
            size = max(180, min(size, self.panel_rect.width - gap * 2))
            right_x = self.panel_rect.right - gap - size - 60
            center_y = self.panel_rect.centery + 60
            height = int(size * 0.9)
            self.practice_rect = pg.Rect(0, 0, size, height)
            self.practice_rect.topleft = (right_x, center_y - size // 2)
        else:
            self.practice_rect = pg.Rect(0, 0, 0, 0)

    def _update_signal_practice(self):
        if self.practice_signal_variant not in ("H", "A"):
            return
        now = time.time()
        if self.practice_signal_prompt is None and now >= self.practice_signal_next_time:
            if self.practice_signal_variant == "H":
                if random.random() < 0.5:
                    self.practice_signal_prompt = "passown"
                    self.practice_signal_expected = "TR"
                else:
                    self.practice_signal_prompt = "passyour"
                    self.practice_signal_expected = "Y"
            else:
                if random.random() < 0.5:
                    self.practice_signal_prompt = "agent_my"
                    self.practice_signal_expected = "TR"
                else:
                    self.practice_signal_prompt = random.choice(["agent_your_left", "agent_your_right"])
                    self.practice_signal_expected = "Y"
            self.practice_signal_prompt_until = now + 2.0
        if self.practice_signal_prompt is not None and now > self.practice_signal_prompt_until:
            self.practice_signal_prompt = None
            self.practice_signal_expected = None
            self.practice_signal_next_time = now + 2.0

    def _handle_signal_input(self, key_name: str):
        if self.index != 3 or self.practice_signal_variant not in ("H", "A"):
            return
        if self.practice_signal_variant == "H":
            if key_name == "TR":
                self.practice_signal_img = self.practice_signal_img_my
            elif key_name == "Y":
                self.practice_signal_img = self.practice_signal_img_right or self.practice_signal_img_left
            self.practice_signal_until = time.time() + 0.8
        if self.practice_signal_prompt is None:
            return
        if self.practice_signal_expected == key_name:
            self.practice_signal_count += 1
            self.practice_signal_prompt = None
            self.practice_signal_expected = None
            self.practice_signal_next_time = time.time() + 2.0
            try:
                if self.signal_snd_right:
                    self.signal_snd_right.play()
            except Exception:
                pass
            if self.practice_signal_variant == "A":
                self.practice_signal_feedback_img = self.signal_img_right
                self.practice_signal_feedback_until = time.time() + 1.0
        else:
            self.practice_signal_prompt = None
            self.practice_signal_expected = None
            self.practice_signal_next_time = time.time() + 2.0
            try:
                if self.signal_snd_wrong:
                    self.signal_snd_wrong.play()
            except Exception:
                pass
            if self.practice_signal_variant == "A":
                self.practice_signal_feedback_img = self.signal_img_wrong
                self.practice_signal_feedback_until = time.time() + 1.0

    def _draw_signal_prompt(self, surface, font, split_y):
        if self.practice_signal_variant not in ("H", "A"):
            return
        if self.practice_signal_prompt is None:
            return
        top_center = (
            self.practice_rect.centerx,
            self.practice_rect.top + (split_y - self.practice_rect.top) * 0.5,
        )
        if self.practice_signal_variant == "H":
            if self.practice_signal_prompt == "passown":
                img = self.signal_img_passown
            else:
                img = self.signal_img_passyour
            if img:
                half = pg.transform.smoothscale(img, (max(1, img.get_width() // 2), max(1, img.get_height() // 2)))
                rect = half.get_rect(center=top_center)
                surface.blit(half, rect)
        else:
            if self.practice_signal_prompt == "agent_my":
                img = self.practice_signal_img_my
            elif self.practice_signal_prompt == "agent_your_left":
                img = self.practice_signal_img_left
            else:
                img = self.practice_signal_img_right
            if img:
                rect = img.get_rect(center=top_center)
                surface.blit(img, rect)

    def _draw_signal_feedback(self, surface, split_y):
        if self.practice_signal_variant != "A":
            return
        if self.practice_signal_feedback_img is None:
            return
        if time.time() > self.practice_signal_feedback_until:
            self.practice_signal_feedback_img = None
            return
        bottom_center = (
            self.practice_rect.centerx,
            split_y + (self.practice_rect.bottom - split_y) * 0.5,
        )
        rect = self.practice_signal_feedback_img.get_rect(center=bottom_center)
        surface.blit(self.practice_signal_feedback_img, rect)
