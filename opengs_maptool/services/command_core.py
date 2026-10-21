from __future__ import annotations
from dataclasses import dataclass
from difflib import get_close_matches
from enum import Enum
import mslex
from promise import Promise
import re
import traceback
from typing import Callable, TypeAlias, TYPE_CHECKING
from PyQt6.QtCore import QEventLoop, QObject, pyqtSignal

if TYPE_CHECKING:
    from opengs_maptool.context import ApplicationContext

from opengs_maptool.controllers.task_controller import ThreadTaskSlot, ThreadTask
from opengs_maptool.models.command_response import CommandResponse
from opengs_maptool.models.message import MessageType
from opengs_maptool.services.parser_service import (
    CommandArgSpec,
    CommandArgumentParseError,
    CommandParserConfigurationError,
    deserialize_command_arguments,
)
from opengs_maptool.services.logging_service import LOGGING_SERVICE

#####################################################
#                Base Infrastructure                #
#####################################################

# Principle: The @decorator registers a command and the function docstring is used as the command description.

# command.this.format.id -> implementation function
CommandImplementation: TypeAlias = Callable[..., CommandResponse]


class CommandDevStatus(Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"


@dataclass(frozen=True)
class CommandDocumentation:
    command_id: str
    description: str
    arguments: tuple[CommandArgSpec, ...]
    aliases: tuple[str, ...]
    examples: tuple[str, ...]
    status: CommandDevStatus | None = None


_commands: dict[
    str,
    tuple[CommandImplementation, str, list[CommandArgSpec], list[str], CommandDevStatus | None],
] = {}
_command_aliases = (dict[str, str])() # alias -> real command
_SORT_PRIORITY_PREFIXES = [
    "link", "console", "project",
    "land", "boundary", "density", "terrain",
    "territory", "province",
    "wait",
]
# /\ above: imported by other module

def register_command(
    command_id: str,
    args: list[CommandArgSpec],
    aliases: list[str] | None = None,
    examples: list[str] | None = None,
    status: CommandDevStatus | None = None,
):
    """Decorator to register a command function with a given command ID."""
    def decorator[T: CommandImplementation](func: T) -> T:
        if command_exists(command_id):
            raise ValueError(f"Please report this. Command {command_id} is already registered.")

        doc = func.__doc__ or "No description provided"
        if status is not None and not isinstance(status, CommandDevStatus):
            raise ValueError("Command status must be a CommandDevStatus value or None.")

        _commands[command_id] = (func, doc, args, examples or [], status)

        if aliases:
            for alias in aliases:
                if not command_exists(command_id): # Practically unreachable as command is created above.
                    raise ValueError(f"Please report this. Cannot create alias '{alias}' for unknown command '{command_id}'")
                _command_aliases[alias] = command_id
        return func
    return decorator

def command_exists(command_id: str) -> bool:
    return command_id in _commands or command_id in _command_aliases

def get_command_implementation(command_id: str) -> CommandImplementation:
    command_id = _command_aliases.get(command_id, command_id)
    return _commands[command_id][0]

def get_command_description(command_id: str) -> str:
    command_id = _command_aliases.get(command_id, command_id)
    return _commands[command_id][1]

def get_command_arg_specs(command_id: str) -> list[CommandArgSpec]:
    command_id = _command_aliases.get(command_id, command_id)
    return _commands[command_id][2]

def get_command_examples(command_id: str) -> list[str]:
    command_id = _command_aliases.get(command_id, command_id)
    return _commands[command_id][3]

def get_command_documentation() -> list[CommandDocumentation]:
    return [
        CommandDocumentation(
            command_id=command_id,
            description=description.strip(),
            arguments=tuple(arguments),
            aliases=tuple(alias for alias, target in _command_aliases.items() if target == command_id),
            examples=tuple(examples),
            status=status,
        )
        for command_id, (_, description, arguments, examples, status) in _commands.items()
    ]

def get_all_command_ids() -> list[str]:
    return list(_commands.keys())

def get_all_command_aliases() -> list[str]:
    return list(_command_aliases.keys())

def _error_res_promise(message: str) -> Promise[CommandResponse]:
    return Promise.resolve(CommandResponse(message, MessageType.ERROR))

def execute_command_string(context: ApplicationContext, command_str: str) -> Promise[CommandResponse]:
    """Process a console command from a string and return a promise to a system response message."""
    try:
        command_id, arguments = split_command(command_str)
    except ValueError as err:
        return _error_res_promise(f"Invalid command syntax: {err}")

    if not command_id:
        return _error_res_promise("No command provided.")

    if not command_exists(command_id):
        return _handle_unknown_command(command_id)

    try:
        parsed_arguments = deserialize_command(command_id, arguments)
    except CommandArgumentParseError as err:
        return _error_res_promise(f"Invalid arguments: {err}")
    except CommandParserConfigurationError as err:
        return _error_res_promise(f"Internal command configuration error: {err}")

    if context.task_controller.is_thread_slot_occupied(ThreadTaskSlot.execute_command):
        # Handle the case where the thread slot is already occupied
        return _error_res_promise("A command is already being executed.")

    promise = _create_command_execution_promise(context, command_id, parsed_arguments)
    return promise

def _create_command_execution_promise(context: ApplicationContext, command_id: str, parsed_arguments: list[str|int|float|bool]) -> Promise[CommandResponse]:
    def promise_executor(resolve: Callable[[CommandResponse], None], reject: Callable[[Exception], None]):
        # In callbacks: Set the result on the future to unblock the await
        def on_error(error):
            # This should actually never happen as
            # _run_command_func_with_args handles exceptions and returns a CommandResponse.
            resolve(CommandResponse(f"Command execution failed: {error}", MessageType.ERROR))

        def on_success(result):
            resolve(result)

        def on_cancelled():
            # This can only happen on application close as this task won't show as a task notification.
            resolve(CommandResponse("Command execution was cancelled.", MessageType.ERROR))

        def connect_signals(task: ThreadTask):
            task.signals.task_error.connect(on_error)
            task.signals.task_successful.connect(on_success)
            task.signals.task_cancelled.connect(on_cancelled)

        command_func = get_command_implementation(command_id)
        context.task_controller.start_task( # Can not raise as slot is checked above
            function=_run_command_func_with_args,
            title=f"Executing command: {command_id}",
            slot=ThreadTaskSlot.execute_command,
            provide_progress_controller=False,
            pos_args=[context, command_id, command_func, parsed_arguments],
            kw_args={},
            before_start_callback=connect_signals,
        )

    return Promise(promise_executor)

def _run_command_func_with_args(
        context: ApplicationContext,
        command_id: str,
        command_func: CommandImplementation,
        parsed_arguments: list[str|int|float|bool],
    ) -> CommandResponse:

    def log_error_msg() -> str:
        header = ">>> UNEXPECTED ERROR IN COMMAND FUNCTION <<<\n"
        exception_text = traceback.format_exc()
        indented_text = "\n".join(">\t" + line for line in exception_text.splitlines())
        LOGGING_SERVICE.loggers.command.send(header + indented_text)

    try:
        response = command_func(context, *parsed_arguments)

    except TypeError as error:
        log_error_msg()
        if _is_wrong_argument_count_error(error):
            response = CommandResponse(
                f"Internal Error: registered and implemented arguments of command {_single_quotes(command_id)} do not match: {error}",
                MessageType.ERROR
            )
        else:
            raise

    except Exception as error:
        log_error_msg()
        response = CommandResponse(f"Unexpected error executing command {_single_quotes(command_id)}: {error}", MessageType.ERROR)
    return response

def _is_wrong_argument_count_error(error: TypeError) -> bool:
    if ("expected at most" in str(error)) or ("expected at least" in str(error)):
        return True

    pattern = re.compile(
        r"takes\s+(\d+)\s+positional\s+argument(?:s)?\s+but\s+(\d+)\s+were\s+given"
    )
    match = pattern.search(str(error))
    return bool(match)

def _handle_unknown_command(command_id: str) -> Promise[CommandResponse]:
    # When input is close to a known command or alias, show a hint
    # instead of a plain "unknown command" message.
    closest_command = _get_closest_command_name(command_id)
    if closest_command:
        if closest_command in _command_aliases:
            target_command = _command_aliases[closest_command]
            return _error_res_promise(
                (
                    f"Unknown command {_single_quotes(command_id)}. "
                    f"Did you mean {_single_quotes(closest_command)} "
                    f"(alias of {_single_quotes(target_command)})?"
                )
            )
        else:
            return _error_res_promise(
                f"Unknown command {_single_quotes(command_id)}. Did you mean {_single_quotes(closest_command)}?",
            )
    else:
        return _error_res_promise(f"Unknown command {_single_quotes(command_id)} (run 'link.help' for more info).")

def serialize_command(command_list: list[str|int|float|bool]) -> str:
    """Convert a list of command segments into a single string, quoting properly as necessary."""
    # The console is not cmd.exe, so use Windows argument quoting without cmd shell rules.
    result = " ".join(mslex.quote(str(arg), for_cmd=False) for arg in command_list)
    return result

def split_command(command_string: str) -> tuple[str|None, list[str]]:
    """
    Split a command string into the command ID and its arguments, respecting quotes.
    Raises:
        ValueError: When the command string is malformed (e.g., unbalanced quotes)
    """
    # The console is not cmd.exe, so use Windows argument parsing without cmd shell rules.
    segments = mslex.split(command_string, like_cmd=False)
    if len(segments) >= 1:
        return segments[0], segments[1:]
    return None, []

def deserialize_command(command_id: str, argument_values: list[str]) -> list[str|int|float|bool]:
    """
    Convert a split command into a list of typed arguments based on the command's argument specifications.
    Given command should exists.
    Raises:
        ValueError: When given invalid arguments
    """
    return deserialize_command_arguments(
        command_id,
        command_description=get_command_description(command_id),
        argument_values=argument_values,
        argument_specs=get_command_arg_specs(command_id),
    )

def _single_quotes(text: str) -> str:
    """Wraps a string in single quotes."""
    return f"'{text.replace('\'', '\\\'')}'"

def _get_closest_command_name(command_id: str) -> str | None:
    """Find the closest command ID or alias to a user-provided command."""
    candidates = get_all_command_ids() + get_all_command_aliases()
    matches = get_close_matches(command_id, candidates, n=1, cutoff=0.3)
    return matches[0] if matches else None
