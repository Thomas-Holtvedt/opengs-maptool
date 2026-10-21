from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opengs_maptool.context import ApplicationContext

from opengs_maptool.services.command_core import register_command, get_command_description, get_all_command_ids, _SORT_PRIORITY_PREFIXES
import opengs_maptool.config as config
from opengs_maptool.models.command_response import CommandResponse
from opengs_maptool.models.message import MessageType

@register_command("link.help", args=[], aliases=["?", "h", "help"])
def cmd_link_help(context: ApplicationContext) -> CommandResponse:
    """Displays the link for the command documentation."""
    # TODO: make this a <a></a> html link
    help_text = (
        "You can find an explanation of the console and commands here:\n"
        + config.CONSOLE_HELP_URL
    )
    return CommandResponse(help_text, MessageType.INFO)

@register_command("link.discord", args=[])
def cmd_link_discord(context: ApplicationContext) -> CommandResponse:
    """Displays the link to the OpenGS Discord server."""
    # TODO: make this a <a></a> html link
    return CommandResponse(config.DISCORD_URL, MessageType.INFO)

@register_command("link.github", args=[])
def cmd_link_github(context: ApplicationContext) -> CommandResponse:
    """Displays the link to the editor's GitHub repository."""
    # TODO: make this a <a></a> html link
    return CommandResponse(config.GITHUB_URL, MessageType.INFO)

@register_command("console.commands.list", args=[])
def cmd_console_commands_list(context: ApplicationContext) -> CommandResponse:
    """Display a simplified list of commands."""
    # Group by first word of command
    sub_commands = dict[str, list[str]]() # "a" -> ["a.b", "a.c"] / "b" -> ["b.c.d", "b.e"]
    for command_id in get_all_command_ids():
        segments = command_id.split(".")
        prefix = segments[0]
        if prefix not in sub_commands:
            sub_commands[prefix] = []
        sub_commands[prefix].append(command_id)

    # Pull some prefixes to the front of the list for better visibility
    sorted_commands = dict[str, str]() # "a" -> "Does thing a"
    for prefix in _SORT_PRIORITY_PREFIXES:
        if prefix not in sub_commands:
            continue

        # Dicts remember insertion order (this is Python 3.12+)
        for command_id in sub_commands[prefix]:
            sorted_commands[command_id] = get_command_description(command_id)
        sub_commands.pop(prefix)

    for prefix, command_ids in sub_commands.items():
        for command_id in command_ids:
            sorted_commands[command_id] = get_command_description(command_id)

    text = "\n".join(
        f"{index + 1}. {key}: {value}" for index, (key, value) in enumerate(sorted_commands.items())
    ) + "\n\nFor more information, type 'link.help'."
    return CommandResponse(text, MessageType.NORMAL)

@register_command("console.history.list", args=[])
def cmd_console_history_list(context: ApplicationContext) -> CommandResponse:
    """Displays the history of console commands entered by the user."""
    history = context.console_service.get_command_history(context.console)
    if not history:
        return CommandResponse("No history", MessageType.NORMAL)

    text = "\n".join(
        f"{index + 1}. {value.text}" for index, value in enumerate(history)
    )
    return CommandResponse(text, MessageType.NORMAL)

@register_command("console.history.clear", args=[])
def cmd_console_history_clear(context: ApplicationContext) -> CommandResponse:
    """Clears the console message history."""
    context.console_service.clear_console(context.console)
    return CommandResponse("History cleared", MessageType.NORMAL)
