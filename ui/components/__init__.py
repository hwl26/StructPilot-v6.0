"""StructPilot UI component modules.

Modules:
    answer_cards      -- Card-based answer rendering (structured JSON or plain markdown)
    stage_workspace   -- Current-stage workspace with SOP/params/screenshots/QC tabs
    parameter_panel   -- Parameter cards with name, value, range, description
    image_gallery     -- Thumbnail grid with click-to-expand
"""

from .answer_cards import render_answer_cards, parse_answer_payload, ANSWER_CARD_TYPES, render_suppressed_cards
from .stage_workspace import render_stage_workspace
from .parameter_panel import render_parameter_panel
from .image_gallery import render_image_gallery

__all__ = [
    "render_answer_cards",
    "parse_answer_payload",
    "ANSWER_CARD_TYPES",
    "render_suppressed_cards",
    "render_stage_workspace",
    "render_parameter_panel",
    "render_image_gallery",
]
