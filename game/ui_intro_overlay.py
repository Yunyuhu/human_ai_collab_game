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
        if event.type == pg.JOYBUTTONDOWN:
            if event.button == 2:
                self.prev()
                return "nav"
            if event.button == 1:
                self.next()
                return "nav"
            if event.button == 0:
                return "close"
        return None

    def prev(self):
        if self.index > 0:
            self.index -= 1

    def next(self):
        if self.index < len(self.images) - 1:
            self.index += 1

    def draw(self, surface, font, screen_w, screen_h):
        overlay = pg.Surface((screen_w, screen_h), flags=pg.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        surface.blit(overlay, (0, 0))

        panel_w = int(screen_w * 0.82 * 0.8)
        panel_h = int(screen_h * 0.82 * 0.8)
        self.panel_rect = pg.Rect(0, 0, panel_w, panel_h)
        self.panel_rect.center = (screen_w // 2, screen_h // 2)
        shadow = self.panel_rect.move(4, 4)
        pg.draw.rect(surface, (20, 20, 28), shadow, border_radius=14)
        pg.draw.rect(surface, (245, 245, 245), self.panel_rect, border_radius=14)

        # Image area
        img = self.images[self.index] if self.images else None
        if img:
            max_w = int(panel_w * 0.90)
            max_h = int(panel_h * 0.90)
            scale = min(max_w / img.get_width(), max_h / img.get_height())
            scaled = pg.transform.smoothscale(
                img,
                (max(1, int(img.get_width() * scale)), max(1, int(img.get_height() * scale))),
            )
            img_rect = scaled.get_rect(center=self.panel_rect.center)
            surface.blit(scaled, img_rect)

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
        self._draw_nav_button(surface, self.next_rect, ">", enabled=self.index < len(self.images) - 1)

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
