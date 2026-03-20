from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from opengs_maptool.logic.map_tool_protocol import MapToolProtocol

import opengs_maptool.config as config
import numpy as np
from PIL import Image


def normalize_density(map_tool: MapToolProtocol) -> None:
    land_image = map_tool.get_land_image()
    if land_image is None:
        return

    w, h = land_image.size
    density = Image.new("L", (w, h), config.DEFAULT_DENSITY_GREY)
    map_tool.set_density_image(density)
    map_tool.check_territory_ready()


def equator_density(map_tool: MapToolProtocol) -> None:
    land_image = map_tool.get_land_image()
    if land_image is None:
        return

    w, h = land_image.size
    # Black (0) at equator (middle row), white (255) at top/bottom poles
    rows = np.linspace(0, 1, h)
    gradient = np.abs(rows - 0.5) * 2.0  # 0 at center, 1 at edges
    pixel_values = (gradient * 255).astype(np.uint8)
    arr = np.tile(pixel_values[:, np.newaxis], (1, w))

    density = Image.fromarray(arr, mode="L")
    map_tool.set_density_image(density)
    map_tool.check_territory_ready()
