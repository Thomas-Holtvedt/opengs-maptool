"""Configured parsing for console command arguments.

This module turns already-tokenized command arguments into values for a command
function.  It deliberately keeps all user-facing messages under OpenGS control.
"""

import argparse
from dataclasses import dataclass
import html
import re
from typing import Any, TypeAlias


CommandValue: TypeAlias = str | int | float | bool
_MISSING = object()


@dataclass(frozen=True)
class CommandArgSpec:
    """Declarative definition of one command-function argument."""

    name: str
    arg_type: type[str] | type[int] | type[float] | type[bool]
    description: str
    default: CommandValue | object = _MISSING
    choices: list[CommandValue] | None = None

    @property
    def required(self) -> bool:
        """Whether this argument is required and positional."""
        return self.default is _MISSING


class CommandArgumentParseError(ValueError):
    """An invalid command argument with an OpenGS-owned message."""


class CommandParserConfigurationError(RuntimeError):
    """A developer error in a command's registered argument specifications."""


class _SilentArgumentParser(argparse.ArgumentParser):
    """Use argparse for parsing without allowing it to print or terminate."""

    def error(self, message: str) -> None:
        raise CommandArgumentParseError(_format_argparse_error(message))

    def exit(self, status: int = 0, message: str | None = None) -> None:
        raise CommandArgumentParseError(f"Arguments do not match this command's syntax: {message or 'unknown error'}.")


def _clean_and_format_help_for_html(raw_text: str) -> str:
    """Removes terminal ANSI color codes and safely wraps text for an HTML console."""
    # Regular expression to catch ANSI escape sequences (e.g., [1;36m, [0m)
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    plain_text = ansi_escape.sub('', raw_text)

    # Escape special characters like < or > to keep HTML safe
    escaped_text = html.escape(plain_text)
    return escaped_text

def deserialize_command_arguments(
    command_id: str,
    command_description: str,
    argument_values: list[str],
    argument_specs: list[CommandArgSpec],
) -> list[CommandValue]:
    """Parse values for one command according to its registered specifications.

    ``argument_values`` must already have been split by the command tokenizer.
    Raises ``CommandArgumentParseError`` with an OpenGS-owned message on failure.
    """
    if "-h" in argument_values or "--help" in argument_values:
        parser = _build_argument_parser(command_id, command_description, argument_specs)
        # Return or raise the formatted text instead of printing it to stdout
        help_text = parser.format_help()
        formatted_help = _clean_and_format_help_for_html(help_text)
        raise CommandArgumentParseError(formatted_help)

    if (not argument_specs) and argument_values:
        raise CommandArgumentParseError(
            f"Got {len(argument_values)} arg(s) {argument_values}, but function expects 0 param(s) []."
        )

    _validate_argument_specs(command_id, argument_specs)
    try:
        parser = _build_argument_parser(command_id, command_description, argument_specs)
    except (AttributeError, TypeError, ValueError) as error:
        raise CommandParserConfigurationError(
            f"Please report this. Command {_single_quotes(command_id)} has an invalid argument configuration."
        ) from error

    try:
        namespace = parser.parse_args(argument_values)
    except argparse.ArgumentError as error:
        raise CommandArgumentParseError(_format_argparse_error(str(error), error.argument_name)) from error

    converted_arguments: list[CommandValue] = []
    for position, spec in enumerate(argument_specs):
        value = getattr(namespace, spec.name)
        converted_arguments.append(_convert_value(value, spec, position))

    return converted_arguments


def _build_argument_parser(
    command_id: str,
    command_description: str,
    argument_specs: list[CommandArgSpec],
) -> _SilentArgumentParser:
    parser = _SilentArgumentParser(
        description=command_description,
        prog=command_id,
        add_help=False,
        allow_abbrev=False,
        exit_on_error=False,
    )

    # Add the arguments
    for spec in argument_specs:
        arg_choices = None
        if spec.choices is not None:
            # argparse will compare parsed strings to choices, so stringify choices here
            arg_choices = [str(c) for c in spec.choices]

        if spec.required:
            parser.add_argument(spec.name, type=str, help=spec.description, choices=arg_choices)
        elif spec.arg_type is bool:
            parser.add_argument(
                f"--{spec.name}",
                action=argparse.BooleanOptionalAction,  # Example: adds --no-force automatically for a --force boolean flag
                default=spec.default,
                help=spec.description,
            )
        else:
            parser.add_argument(
                f"--{spec.name}",
                type=str,
                default=spec.default,
                help=spec.description,
                choices=arg_choices,
            )

    return parser


def _validate_argument_specs(command_id: str, argument_specs: list[CommandArgSpec]) -> None:
    """Fail early and clearly for invalid command registrations."""
    names: set[str] = set()
    supported_types = {str, int, float, bool}

    for spec in argument_specs:
        if not isinstance(spec, CommandArgSpec):
            raise CommandParserConfigurationError(
                f"Command {_single_quotes(command_id)} has an invalid argument specification."
            )
        if not spec.name.isidentifier() or spec.name.startswith("_"):
            raise CommandParserConfigurationError(
                f"Command {_single_quotes(command_id)} has an invalid argument name."
            )
        if spec.name in names:
            raise CommandParserConfigurationError(
                f"Command {_single_quotes(command_id)} declares argument {_single_quotes(spec.name)} more than once."
            )
        if spec.arg_type not in supported_types:
            raise CommandParserConfigurationError(
                f"Command {_single_quotes(command_id)} uses an unsupported type for argument {_single_quotes(spec.name)}."
            )
        if not spec.required and type(spec.default) is not spec.arg_type:
            raise CommandParserConfigurationError(
                f"Command {_single_quotes(command_id)} has an invalid default for argument {_single_quotes(spec.name)}."
            )

        # Validate choices if provided
        if spec.choices is not None:
            if spec.arg_type is bool:
                raise CommandParserConfigurationError(
                    f"Command {_single_quotes(command_id)} cannot use choices for boolean argument {_single_quotes(spec.name)}."
                )
            if not isinstance(spec.choices, (list, tuple)) or len(spec.choices) == 0:
                raise CommandParserConfigurationError(
                    f"Command {_single_quotes(command_id)} has invalid choices for argument {_single_quotes(spec.name)}."
                )
            for choice in spec.choices:
                if type(choice) is not spec.arg_type:
                    raise CommandParserConfigurationError(
                        f"Command {_single_quotes(command_id)} has an invalid choice for argument {_single_quotes(spec.name)}."
                    )
            # If a default is provided, ensure it's within choices
            if not spec.required and spec.default is not _MISSING:
                if spec.default not in spec.choices:
                    raise CommandParserConfigurationError(
                        f"Command {_single_quotes(command_id)} has an invalid default for argument {_single_quotes(spec.name)}."
                    )
        names.add(spec.name)


def _convert_value(value: Any, spec: CommandArgSpec, position: int) -> CommandValue:
    """Convert parsed values while retaining the current OpenGS error wording."""
    if spec.arg_type is str:
        return str(value)

    if spec.arg_type is bool:
        if isinstance(value, bool):
            return value
        return _parse_bool(str(value), spec, position)

    if spec.arg_type is int:
        try:
            return int(str(value))
        except ValueError as error:
            raise CommandArgumentParseError(
                f"Argument {_single_quotes(spec.name)} (position {position}) must be an integer, "
                f"got {_single_quotes(str(value))}."
            ) from error

    if spec.arg_type is float:
        try:
            return float(str(value))
        except ValueError as error:
            raise CommandArgumentParseError(
                f"Argument {_single_quotes(spec.name)} (position {position}) must be a float, "
                f"got {_single_quotes(str(value))}."
            ) from error

    raise CommandArgumentParseError(
        f"Internal error: unsupported type for argument {_single_quotes(spec.name)}."
    )


def _parse_bool(value: str, spec: CommandArgSpec, position: int) -> bool:
    lowered = value.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise CommandArgumentParseError(
        f"Argument {_single_quotes(spec.name)} (position {position}) must be a boolean, "
        f"got {_single_quotes(value)}. Possible boolean values: 1, 0, true, false, yes, no, on, off."
    )


def _single_quotes(text: str) -> str:
    """Wrap text in escaped single quotes for console errors."""
    return f"'{text.replace("'", "\\'")}'"


def _format_argparse_error(message: str, argument_name: str | None = None) -> str:
    """Translate every argparse error kind reachable by this parser configuration."""
    pattern = "unrecognized arguments: "
    if message.startswith(pattern):
        values = message.removeprefix(pattern)
        return f"Unknown argument(s) or optional flag(s): {values}."

    pattern = "the following arguments are required: "
    if message.startswith(pattern):
        return f"Missing required argument(s): {message.removeprefix(pattern)}."

    name = argument_name or _argument_name_from_message(message)
    detail = message.split(": ", 1)[-1]
    # Argparse invalid choice wording: "invalid choice: 'gif' (choose from 'png', 'jpeg')"
    if "invalid choice" in detail:
        # attempt to extract the offending value and the choice list
        m = re.search(r"invalid choice: '([^']+)' \(choose from (.+)\)", detail)
        if m:
            bad, choices_txt = m.groups()
            # normalize choices text
            choices_txt = choices_txt.strip()
            cleaned_name = (name or "unknown").lstrip("-")
            return f"Invalid value for argument {_single_quotes(cleaned_name)}: {_single_quotes(bad)}. Expected one of: {choices_txt}."
    if detail == "expected one argument":
        return f"Argument {_single_quotes(name or 'unknown')} requires a value."
    if detail.startswith("ignored explicit argument"):
        return f"Flag {_single_quotes(name or 'unknown')} does not accept a value."

    # TODO: Add a matching translation if future parser configuration introduces
    # choices, mutually-exclusive groups, subcommands, or variable-length arguments.
    return f"Arguments do not match this command's syntax: {detail}."


def _argument_name_from_message(message: str) -> str | None:
    """Extract argparse's optional argument name without exposing its wording."""
    match = re.match(r"argument ([^:]+): ", message)
    return match.group(1) if match else None
