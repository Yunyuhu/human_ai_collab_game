import pygame as pg


class ModeSelector:
    def __init__(self, rect, font, options, initial_key):
        self.rect = pg.Rect(rect)
        self.font = font
        self.options = options
        self.selected = initial_key if initial_key in options else list(options.keys())[0]
        self.open = False
        self.item_height = self.rect.height
        self.border_radius = 6
        self.border_width = 1
        self.shadow_offset = (2, 2)

    def set_position(self, x, y):
        self.rect.topleft = (x, y)

    def handle_event(self, event):
        if event.type != pg.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if self.rect.collidepoint(event.pos):
            self.open = not self.open
            return True
        if self.open:
            for idx, key in enumerate(self.options.keys()):
                item_rect = self._item_rect(idx + 1)
                if item_rect.collidepoint(event.pos):
                    self.selected = key
                    self.open = False
                    return True
            self.open = False
        return False

    def draw(self, surface, bg_color, text_color):
        shadow_rect = self.rect.move(*self.shadow_offset)
        pg.draw.rect(surface, (30, 30, 40), shadow_rect, border_radius=self.border_radius)
        pg.draw.rect(surface, bg_color, self.rect, border_radius=self.border_radius)
        pg.draw.rect(surface, (200, 200, 200), self.rect, self.border_width, border_radius=self.border_radius)
        label = self.options[self.selected]
        text_surf = self.font.render(f"MODE: {label}", True, text_color)
        text_rect = text_surf.get_rect()
        text_rect.midleft = (self.rect.x + 10, self.rect.centery)
        max_right = self.rect.right - 22
        if text_rect.right > max_right:
            text_rect.right = max_right
        surface.blit(text_surf, text_rect)
        self._draw_chevron(surface, text_color)
        if self.open:
            for idx, key in enumerate(self.options.keys()):
                item_rect = self._item_rect(idx + 1)
                pg.draw.rect(surface, (45, 45, 60), item_rect, border_radius=self.border_radius)
                pg.draw.rect(surface, (200, 200, 200), item_rect, self.border_width, border_radius=self.border_radius)
                item_surf = self.font.render(self.options[key], True, text_color)
                item_text_rect = item_surf.get_rect(center=item_rect.center)
                surface.blit(item_surf, item_text_rect)

    def _item_rect(self, index):
        return pg.Rect(self.rect.x, self.rect.y + self.item_height * index, self.rect.width, self.item_height)

    def _draw_chevron(self, surface, color):
        cx = self.rect.right - 14
        cy = self.rect.centery + 1
        pts = [(cx - 4, cy - 3), (cx + 4, cy - 3), (cx, cy + 3)]
        pg.draw.polygon(surface, color, pts)
