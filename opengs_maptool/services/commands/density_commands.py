from __future__ import annotations
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from opengs_maptool.context import ApplicationContext

from opengs_maptool.controllers.task_controller import ThreadTaskSlot, ThreadSlotOccupiedError
from opengs_maptool.logic.density_generator import normalize_density_image, equator_density_image, remove_density_image
from opengs_maptool.services.command_core import register_command, CommandArgSpec
from opengs_maptool.models.command_response import CommandResponse
from opengs_maptool.models.message import MessageType

@register_command("density.image.remove", args=[])
def cmd_density_image_remove(context: ApplicationContext) -> CommandResponse:
    """Removes the current density image."""
    able, message = context.project.get_density_image_remove_status(context)
    if not able:
        return CommandResponse(message, MessageType.ERROR)
    return run_density_task(
        context=context,
        task_function=remove_density_image,
        task_title="Removing Density Image",
        lowercase_title="removing density image",
    )

@register_command("density.image.normalize", args=[])
def cmd_density_image_normalize(context: ApplicationContext) -> CommandResponse:
    """Normalizes density image."""
    able, message = context.project.get_density_image_generate_status(context)
    if not able:
        return CommandResponse(message, MessageType.ERROR)
    return run_density_task(
        context=context,
        task_function=normalize_density_image,
        task_title="Normalizing Density Image",
        lowercase_title="normalizing density image",
    )

@register_command("density.image.equator_distribute", args=[])
def cmd_density_image_equator_distribute(context: ApplicationContext) -> CommandResponse:
    """Generates equator-based density distribution."""
    able, message = context.project.get_density_image_generate_status(context)
    if not able:
        return CommandResponse(message, MessageType.ERROR)
    return run_density_task(
        context=context,
        task_function=equator_density_image,
        task_title="Generating equator-based Density Image",
        lowercase_title="generating equator-based density image",
    )

@register_command("density.exclude_ocean_territories", args=[
    CommandArgSpec(
        "activate", arg_type=bool,
        description="Whether to exclude ocean territories from the effect of density.",
    )
])
def cmd_density_exclude_ocean_territories(context: ApplicationContext, activate: bool) -> CommandResponse:
    """Sets whether density applies to ocean territories."""
    context.project_controller.set_territory_exclude_ocean(activate)
    return CommandResponse(f"Density will from now on {'not ' if activate else ''}apply to ocean territories.", MessageType.NORMAL)

@register_command("density.exclude_ocean_provinces", args=[
    CommandArgSpec(
        "activate", arg_type=bool,
        description="Whether to exclude ocean provinces from the effect of density.",
    )
])
def cmd_density_exclude_ocean_provinces(context: ApplicationContext, activate: bool) -> CommandResponse:
    """Sets whether density applies to ocean provinces."""
    context.project_controller.set_province_exclude_ocean(activate)
    return CommandResponse(f"Density will from now on {'not ' if activate else ''}apply to ocean provinces.", MessageType.NORMAL)

def run_density_task(context: ApplicationContext, task_function: Callable, task_title: str, lowercase_title: str):
    try:
        # Run in the proper ThreadTaskSlot that was created for the function
        # -> proper UI notification & task slot management
        context.task_controller.start_task(
            function=task_function,
            title=task_title,
            slot=ThreadTaskSlot.change_density_image,
            provide_progress_controller=True,
            pos_args=[],
            kw_args={
                "task_ctx": context,
            },
            before_start_callback=None,
        )
        return CommandResponse(f"Started {lowercase_title}...", MessageType.NORMAL)
    except ThreadSlotOccupiedError:
        return CommandResponse(f"A task to change the density image is already running.", MessageType.ERROR)
    except Exception as error:
        # There is no known possible error.
        return CommandResponse(f"Failed {lowercase_title}: {str(error)}", MessageType.ERROR)
