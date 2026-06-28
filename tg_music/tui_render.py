from __future__ import annotations

import curses
import re
import time

from .cover import render_cover, render_graphics_cover, supports_graphics_cover
from .db import connect, get_track_tags, is_favorite
from .models import format_duration
from .render_base import RenderBaseMixin, clear_terminal_images, wrap, parse_ansi_sgr, CSI_RE
from .render_panels import RenderPanelsMixin
from .render_split import RenderSplitMixin
from .render_cover import RenderCoverMixin
from .render_help import RenderHelpMixin


class RenderMixin(RenderBaseMixin, RenderPanelsMixin, RenderSplitMixin, RenderCoverMixin, RenderHelpMixin):
    pass
