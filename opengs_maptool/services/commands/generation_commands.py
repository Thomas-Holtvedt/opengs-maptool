from __future__ import annotations
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from opengs_maptool.context import ApplicationContext

from opengs_maptool.controllers.task_controller import ThreadTaskSlot, ThreadSlotOccupiedError
from opengs_maptool.services.command_core import register_command, CommandArgSpec
import opengs_maptool.logic.datastructure as ds
from opengs_maptool.logic.export_module import (
    export_image, export_territory_definitions, export_territory_history,
    export_province_definitions, ExportFormat,
)
from opengs_maptool.logic.territory_generator import generate_territory_map
from opengs_maptool.logic.province_generator import generate_province_map
from opengs_maptool.models.command_response import CommandResponse
from opengs_maptool.models.message import MessageType

@register_command("territory.image.generate", args=[])
def cmd_territory_image_generate(context: ApplicationContext) -> CommandResponse:
    """Generates the territory map."""
    able, message = context.project.get_territory_image_generate_status(context, ignore_locked=False)
    if not able:
        return CommandResponse(message, MessageType.ERROR)
    return run_generation_task(
        context=context,
        task_function=generate_territory_map,
        task_slot=ThreadTaskSlot.generate_territory_map,
        task_title="Generating territory map",
        lowercase_title="generating territory map",
    )

@register_command("province.image.generate", args=[])
def cmd_province_image_generate(context: ApplicationContext) -> CommandResponse:
    """Generates the province map."""
    able, message = context.project.get_province_image_generate_status(context, ignore_locked=False)
    if not able:
        return CommandResponse(message, MessageType.ERROR)
    return run_generation_task(
        context=context,
        task_function=generate_province_map,
        task_slot=ThreadTaskSlot.generate_province_map,
        task_title="Generating province map",
        lowercase_title="generating province map",
    )


@register_command("territory.image.export", args=[
    CommandArgSpec("path", arg_type=str, description="The path to export the territory image to."),
])
def cmd_territory_image_export(context: ApplicationContext, path: str) -> CommandResponse:
    """Exports the territory image."""
    return export_generated_image(context.project.territory_image, context.project.territory_data, path, "territory image")

@register_command("province.image.export", args=[
    CommandArgSpec("path", arg_type=str, description="The path to export the province image to."),
])
def cmd_province_image_export(context: ApplicationContext, path: str) -> CommandResponse:
    """Exports the province image."""
    return export_generated_image(context.project.province_image, context.project.province_data, path, "province image")


@register_command("territory.definitions.export", args=[
    CommandArgSpec("path", arg_type=str, description="The path to export the territory definitions to. Format is automatically detected"),
])
def cmd_territory_definitions_export(context: ApplicationContext, path: str) -> CommandResponse:
    """Exports territory definitions. Accepted formats: JSON, CSV, YAML, XML."""
    try:
        file_format = ExportFormat.get_by_path(path, raise_on_unknown=True)
        export_territory_definitions(context.project, path, file_format)
        return CommandResponse(f"Exported territory definitions to {path}.", MessageType.NORMAL)
    except (ValueError, Exception) as error:
        return CommandResponse(f"Failed exporting territory definitions: {str(error)}", MessageType.ERROR)

@register_command("province.definitions.export", args=[
    CommandArgSpec("path", arg_type=str, description="The path to export the province definitions to. Format is automatically detected"),
])
def cmd_province_definitions_export(context: ApplicationContext, path: str) -> CommandResponse:
    """Exports province definitions. Accepted formats: JSON, CSV, YAML, XML."""
    try:
        file_format = ExportFormat.get_by_path(path, raise_on_unknown=True)
        export_province_definitions(context.project, path, file_format)
        return CommandResponse(f"Exported province definitions to {path}.", MessageType.NORMAL)
    except (ValueError, Exception) as error:
        return CommandResponse(f"Failed exporting province definitions: {str(error)}", MessageType.ERROR)

@register_command("territory.history.export", args=[
    CommandArgSpec("path", arg_type=str, description="The path to export the territory history to. Format is automatically detected"),
])
def cmd_territory_history_export(context: ApplicationContext, path: str) -> CommandResponse:
    """Exports territory history. Accepted formats: JSON, CSV, YAML, XML."""
    try:
        file_format = ExportFormat.get_by_path(path, raise_on_unknown=True)
        export_territory_history(context.project, path, file_format)
        return CommandResponse(f"Exported territory history to {path}.", MessageType.NORMAL)
    except (ValueError, Exception) as error:
        return CommandResponse(f"Failed exporting territory history: {str(error)}", MessageType.ERROR)


@register_command("territory.land_density.set", args=[
    CommandArgSpec("value", arg_type=int, description="The land density to set for territories."),
])
def cmd_territory_land_density_set(context: ApplicationContext, value: int) -> CommandResponse:
    """Sets land territory density."""
    context.project_controller.set_land_territory_density(value)
    return CommandResponse(f"Territory land density set to {value}.", MessageType.NORMAL)

@register_command("province.land_density.set", args=[
    CommandArgSpec("value", arg_type=int, description="The land density to set for territories."),
])
def cmd_province_land_density_set(context: ApplicationContext, value: int) -> CommandResponse:
    """Sets land province density."""
    context.project_controller.set_land_province_density(value)
    return CommandResponse(f"Province land density set to {value}.", MessageType.NORMAL)

@register_command("territory.oceanic_density.set", args=[
    CommandArgSpec("value", arg_type=int, description="The oceanic density to set for territories."),
])
def cmd_territory_oceanic_density_set(context: ApplicationContext, value: int) -> CommandResponse:
    """Sets oceanic territory density."""
    context.project_controller.set_oceanic_territory_density(value)
    return CommandResponse(f"Territory oceanic density set to {value}.", MessageType.NORMAL)

@register_command("province.oceanic_density.set", args=[
    CommandArgSpec("value", arg_type=int, description="The oceanic density to set for territories."),
])
def cmd_province_oceanic_density_set(context: ApplicationContext, value: int) -> CommandResponse:
    """Sets oceanic province density."""
    context.project_controller.set_oceanic_province_density(value)
    return CommandResponse(f"Province oceanic density set to {value}.", MessageType.NORMAL)


@register_command("territory.density_strength.set", args=[
    CommandArgSpec("factor", arg_type=float, description="The density strength to set for territories."),
])
def cmd_territory_density_strength_set(context: ApplicationContext, factor: float) -> CommandResponse:
    """Sets territory density strength."""
    context.project_controller.set_territory_density_strength(factor)
    return CommandResponse(f"Territory density strength set to {factor}.", MessageType.NORMAL)

@register_command("province.density_strength.set", args=[
    CommandArgSpec("factor", arg_type=float, description="The density strength to set for provinces."),
])
def cmd_province_density_strength_set(context: ApplicationContext, factor: float) -> CommandResponse:
    """Sets province density strength."""
    context.project_controller.set_province_density_strength(factor)
    return CommandResponse(f"Province density strength set to {factor}.", MessageType.NORMAL)


@register_command("territory.jagged_land.set", args=[
    CommandArgSpec("strength", arg_type=float, description="The jaggedness amplitude to set for territories."),
])
def cmd_territory_jagged_land_set(context: ApplicationContext, strength: float) -> CommandResponse:
    """Sets how strongly jagged the land borders of territories should be."""
    context.project_controller.set_territory_jagged_land_amplitude(strength)
    return CommandResponse(f"Territory jagged land amplitude set to {strength}.", MessageType.NORMAL)

@register_command("province.jagged_land.set", args=[
    CommandArgSpec("strength", arg_type=float, description="The jaggedness amplitude to set for provinces."),
])
def cmd_province_jagged_land_set(context: ApplicationContext, strength: float) -> CommandResponse:
    """Sets how strongly jagged the land borders of provinces should be."""
    context.project_controller.set_province_jagged_land_amplitude(strength)
    return CommandResponse(f"Province jagged land amplitude set to {strength}.", MessageType.NORMAL)

@register_command("territory.jagged_oceanic.set", args=[
    CommandArgSpec("strength", arg_type=float, description="The jaggedness amplitude to set for territories."),
])
def cmd_territory_jagged_oceanic_set(context: ApplicationContext, strength: float) -> CommandResponse:
    """Sets how strongly jagged the oceanic borders of territories should be."""
    context.project_controller.set_territory_jagged_ocean_amplitude(strength)
    return CommandResponse(f"Territory jagged oceanic amplitude set to {strength}.", MessageType.NORMAL)

@register_command("province.jagged_oceanic.set", args=[
    CommandArgSpec("strength", arg_type=float, description="The jaggedness amplitude to set for provinces."),
])
def cmd_province_jagged_oceanic_set(context: ApplicationContext, strength: float) -> CommandResponse:
    """Sets how strongly jagged the oceanic borders of provinces should be."""
    context.project_controller.set_province_jagged_ocean_amplitude(strength)
    return CommandResponse(f"Province jagged oceanic amplitude set to {strength}.", MessageType.NORMAL)


def run_generation_task(context: ApplicationContext, task_function: Callable, task_slot: ThreadTaskSlot, task_title: str, lowercase_title: str):
    try:
        # Run in the proper ThreadTaskSlot that was created for the function
        # -> proper UI notification & task slot management
        context.task_controller.start_task(
            function=task_function,
            title=task_title,
            slot=task_slot,
            provide_progress_controller=True,
            pos_args=[],
            kw_args={
                "task_ctx": context,
            },
            before_start_callback=None,
        )
        return CommandResponse(f"Started {lowercase_title}...", MessageType.NORMAL)
    except ThreadSlotOccupiedError:
        return CommandResponse(f"A task {lowercase_title} is already running.", MessageType.ERROR)
    except Exception as error:
        # There is no known possible error.
        return CommandResponse(f"Failed {lowercase_title}: {str(error)}", MessageType.ERROR)

def export_generated_image(
        image: ds.TerritoryImage|ds.ProvinceImage|None, data: list[ds.RegionMetadata]|None,
        path: str, name: str
        ) -> CommandResponse:
    if not image:
        return CommandResponse(f"No {name} to export.", MessageType.ERROR)
    try:
        export_image(path, image, data, raise_on_error=True)
        return CommandResponse(f"Exported {name} to {path}.", MessageType.NORMAL)
    except Exception as error:
        if isinstance(error, ValueError) and "unknown file extension" in str(error):
            return CommandResponse(f"Failed exporting {name}: Invalid file extension", MessageType.ERROR)
        return CommandResponse(f"Failed exporting {name}: {str(error)}", MessageType.ERROR)
