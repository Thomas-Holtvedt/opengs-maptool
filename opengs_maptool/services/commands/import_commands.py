from __future__ import annotations
from typing import TYPE_CHECKING
import webcolors

if TYPE_CHECKING:
    from opengs_maptool.context import ApplicationContext

from opengs_maptool.services.command_core import register_command
from opengs_maptool.models.command_response import CommandResponse
from opengs_maptool.models.message import MessageType
from opengs_maptool.services.parser_service import CommandArgSpec

@register_command(
    "land.image.import",
    args=[CommandArgSpec("path", arg_type=str, description="The path to the land image file to import.")],
)
def cmd_land_image_import(context: ApplicationContext, path: str) -> CommandResponse:
    """Imports a land image into the project."""
    error = context.import_service.import_land_image(path)
    if error is None:
        return CommandResponse(f"Image imported from {path}", MessageType.NORMAL)
    else: # Error is already well formatted
        return CommandResponse(str(error), MessageType.ERROR)

class LandTypeChoice:
    LAND = "land"
    OCEAN = "ocean"
    LAKE = "lake"

@register_command(
    "land.color_settings.set",
    args=[
        CommandArgSpec(
            "land_type",
            arg_type=str,
            description="The land type to change the color for.",
            choices=[LandTypeChoice.LAND, LandTypeChoice.OCEAN, LandTypeChoice.LAKE]
        ),
        CommandArgSpec("new_color", arg_type=str, description="The new color in #RRGGBB format."),
    ],
)
def cmd_land_color_settings_set(context: ApplicationContext, land_type: str, new_color: str) -> CommandResponse:
    """Changes the colors expected in the land image for land, oceans and lakes."""
    from opengs_maptool.services.command_service import wrap_in_single_quotes
    try: # validation and parsing
        int_rgb = webcolors.hex_to_rgb(new_color)
        rgb = (int_rgb.red, int_rgb.green, int_rgb.blue)
    except ValueError:
        return CommandResponse(f"Cannot use invalid color: {wrap_in_single_quotes(new_color)} Please use a hexadecimal color in the format of #RRGGBB", MessageType.ERROR)

    # land_type is guaranteed to be one of the choices by the parser
    if land_type == LandTypeChoice.LAND:
        context.project_controller.set_land_color(rgb)
    elif land_type == LandTypeChoice.OCEAN:
        context.project_controller.set_ocean_color(rgb)
    elif land_type == LandTypeChoice.LAKE:
        context.project_controller.set_lake_color(rgb)
    else:
        return CommandResponse(f"Unknown land type: {wrap_in_single_quotes(land_type)}", MessageType.ERROR)
    return CommandResponse(f"{land_type.capitalize()} color settings set to {wrap_in_single_quotes(new_color)}", MessageType.NORMAL)

@register_command(
"boundary.image.import",
    args=[CommandArgSpec("path", arg_type=str, description="The path to the boundary image file to import.")],
)
def cmd_boundary_image_import(context: ApplicationContext, path: str) -> CommandResponse:
    """Imports the boundary image from a file."""
    error = context.import_service.import_boundary_image(path)
    if error is None:
        return CommandResponse(f"Image imported from {path}", MessageType.NORMAL)
    else: # Error is already well formatted
        return CommandResponse(str(error), MessageType.ERROR)

@register_command("density.image.import",
    args=[CommandArgSpec("path", arg_type=str, description="The path to the density image file to import.")],
)
def cmd_density_image_import(context: ApplicationContext, path: str) -> CommandResponse:
    """Imports the density image from a file."""
    error = context.import_service.import_density_image(path)
    if error is None:
        return CommandResponse(f"Image imported from {path}", MessageType.NORMAL)
    else: # Error is already well formatted
        return CommandResponse(str(error), MessageType.ERROR)

@register_command("terrain.image.import",
    args=[CommandArgSpec("path", arg_type=str, description="The path to the terrain image file to import.")],
)
def cmd_terrain_image_import(context: ApplicationContext, path: str) -> CommandResponse:
    """Imports the terrain image from a file."""
    error = context.import_service.import_terrain_image(path)
    if error is None:
        return CommandResponse(f"Image imported from {path}", MessageType.NORMAL)
    else: # Error is already well formatted
        return CommandResponse(str(error), MessageType.ERROR)

