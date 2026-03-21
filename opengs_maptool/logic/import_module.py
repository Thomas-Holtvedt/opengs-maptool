from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from opengs_maptool.logic.map_tool_protocol import MapToolProtocol

import opengs_maptool.config as config
from PIL import Image
from PyQt6.QtWidgets import QFileDialog


def import_land_image(map_tool: MapToolProtocol) -> None:
    Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS
    path, _ = QFileDialog.getOpenFileName(
        map_tool,
        "Import Land Image",
        "",
        "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
    )
    if not path:
        return
    imported_image = Image.open(path)
    map_tool.set_land_image(imported_image)

    # Reset density and enable density editing
    map_tool.set_density_image(None)
    map_tool.set_edit_density_available(True)
    map_tool.check_territory_ready()


def import_boundary_image(map_tool: MapToolProtocol) -> None:
    Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS
    path, _ = QFileDialog.getOpenFileName(
        map_tool,
        "Import Boundary Image",
        "",
        "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
    )
    if not path:
        return
    imported_image = Image.open(path)
    map_tool.set_boundary_image(imported_image.convert("RGBA"))


def import_terrain_image(map_tool: MapToolProtocol) -> None:
    Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS
    path, _ = QFileDialog.getOpenFileName(
        map_tool,
        "Import Terrain Image",
        "",
        "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
    )
    if not path:
        return

    terrain = Image.open(path)
    map_tool.set_terrain_image(terrain.convert("RGBA"))


def import_density_image(map_tool: MapToolProtocol) -> None:
    Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS
    path, _ = QFileDialog.getOpenFileName(
        map_tool,
        "Import Density Image",
        "",
        "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
    )
    if not path:
        return

    density = Image.open(path)
    map_tool.set_density_image(density)
    map_tool.check_territory_ready()
