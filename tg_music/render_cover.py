from __future__ import annotations

from .cover import render_cover, render_graphics_cover, supports_graphics_cover
from .render_base import clear_terminal_images


class RenderCoverMixin:
    def draw_graphics_cover(self) -> None:
        if self.help_visible:
            if self.cover_graphics_draw_key is not None:
                clear_terminal_images()
                self.cover_graphics_draw_key = None
            return
        if not self.cover_graphics or self.cover_graphics_pos is None:
            if self.cover_graphics_draw_key is not None:
                clear_terminal_images()
                self.cover_graphics_draw_key = None
            return
        row, col = self.cover_graphics_pos
        draw_key = (self.cover_render_key, self.cover_graphics_pos)
        if draw_key == self.cover_graphics_draw_key:
            return
        try:
            clear_terminal_images()
            import sys
            sys.stdout.buffer.write(f"\x1b[{row + 1};{col + 1}H".encode("ascii"))
            sys.stdout.buffer.write(self.cover_graphics)
            sys.stdout.flush()
            self.cover_graphics_draw_key = draw_key
        except OSError:
            pass

    def refresh_cover_art(self, screen_height: int, screen_width: int) -> None:
        if self.cover_path is None:
            return

        cover_width, cover_height = self.cover_size(screen_height, screen_width)
        self.refresh_cover_art_size(cover_width, cover_height)

    def refresh_cover_art_size(self, cover_width: int, cover_height: int) -> None:
        if self.cover_path is None:
            return

        graphics_enabled = supports_graphics_cover() and __import__("shutil").which("chafa") is not None
        render_key = (str(self.cover_path), cover_width, cover_height, graphics_enabled)
        if render_key == self.cover_render_key:
            return

        self.cover_render_key = render_key
        self.cover_graphics_draw_key = None
        if graphics_enabled:
            self.cover_graphics = render_graphics_cover(
                self.cover_path,
                max_width=cover_width,
                max_height=cover_height,
            )
            self.cover_lines = []
            if self.cover_graphics is None:
                self.cover_lines = render_cover(
                    self.cover_path,
                    max_width=cover_width,
                    max_height=cover_height,
                )
        else:
            self.cover_graphics = None
            self.cover_lines = render_cover(
                self.cover_path,
                max_width=cover_width,
                max_height=cover_height,
            )
