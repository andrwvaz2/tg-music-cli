from __future__ import annotations

from .render_base import RenderBaseMixin, clear_terminal_images, wrap
from .render_panels import RenderPanelsMixin
from .render_split import RenderSplitMixin
from .render_cover import RenderCoverMixin
from .render_help import RenderHelpMixin


class RenderMixin(RenderBaseMixin, RenderPanelsMixin, RenderSplitMixin, RenderCoverMixin, RenderHelpMixin):
    pass
