from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opengs_maptool.context import ApplicationContext

from opengs_maptool.services.command_core import register_command
from opengs_maptool.models.command_response import CommandResponse
from opengs_maptool.models.message import MessageType
from opengs_maptool.services.parser_service import CommandArgSpec

@register_command(
    "project.new",
    args=[CommandArgSpec("force", arg_type=bool, default=False, description="Ignore unsaved changes if enabled and create a new project.")],
)
def cmd_project_new(context: ApplicationContext, force: bool = False) -> CommandResponse:
    """Creates a new project."""
    if (not force) and context.project_controller.is_project_modified():
        return CommandResponse(
            "The current project has unsaved changes. Please save (command: project.save) or add the option --force to discard unsaved changes.",
            MessageType.ERROR
        )

    context.project_controller.create_project()
    return CommandResponse("New project created", MessageType.NORMAL)

@register_command(
    "project.open",
    args=[
        CommandArgSpec("path", arg_type=str, description="The path to the project file to open."),
        CommandArgSpec("force", arg_type=bool, default=False, description="Ignore unsaved changes if enabled and open the project file."),
    ],
    examples=['project.open "my-project.gsmap"', 'project.open "my-project.gsmap" --force'],
)
def cmd_project_open(context: ApplicationContext, path: str, force: bool = False) -> CommandResponse:
    """ Opens an existing project file."""
    if (not force) and context.project_controller.is_project_modified():
        return CommandResponse(
            "The current project has unsaved changes. Please save (command: project.save) or add the option --force to discard unsaved changes.",
            MessageType.ERROR
        )

    try:
        context.project_controller.load_project(path)
    except Exception as error:
        return CommandResponse(f"Failed to open project file, possibly because of an incompatible format: {error}", MessageType.ERROR)

    return CommandResponse("Project was opened", MessageType.NORMAL)

@register_command(
    "project.save",
    args=[CommandArgSpec("path", arg_type=str, default="", description="The path to save the project file to.")],
)
def cmd_project_save(context: ApplicationContext, path: str) -> CommandResponse:
    """Saves the current project to a target path if supplied or the already set path."""
    if path == "":
        try:
            successful = context.project_controller.save_project()
        except Exception as error:
            return CommandResponse(f"Failed to save project file: {error}", MessageType.ERROR)
        if not successful:
            return CommandResponse(
                "The current project has never been saved. Please provide a file path argument [--path PATH] the first time.",
                MessageType.ERROR
            )

    try:
        context.project_controller.save_project_as(path)
    except Exception as error:
        return CommandResponse(f"Failed to save project file: {error}", MessageType.ERROR)

    return CommandResponse("Project was saved", MessageType.NORMAL)

@register_command(
    "project.name.set",
    args=[CommandArgSpec("name", arg_type=str, description="The new name for the project.")],
)
def cmd_project_name_set(context: ApplicationContext, name: str) -> CommandResponse:
    """Sets the name in metadata of the current project."""
    from opengs_maptool.services.command_service import wrap_in_single_quotes
    context.project_controller.set_project_name(name)
    return CommandResponse(f"Project name set to {wrap_in_single_quotes(name)}", MessageType.NORMAL)

@register_command(
    "project.description.set",
    args=[CommandArgSpec("description", arg_type=str, description="The new description for the project.")],
)
def cmd_project_description_set(context: ApplicationContext, description: str) -> CommandResponse:
    """Sets the description in metadata of the current project."""
    from opengs_maptool.services.command_service import wrap_in_single_quotes
    context.project_controller.set_project_description(description)
    return CommandResponse(f"Project description set to {wrap_in_single_quotes(description)}", MessageType.NORMAL)

@register_command(
    "project.author.set",
    args=[CommandArgSpec("author", arg_type=str, description="The new author for the project.")],
)
def cmd_project_author_set(context: ApplicationContext, author: str) -> CommandResponse:
    """Sets the author in metadata of the current project."""
    from opengs_maptool.services.command_service import wrap_in_single_quotes
    context.project_controller.set_project_author(author)
    return CommandResponse(f"Project author set to {wrap_in_single_quotes(author)}", MessageType.NORMAL)
