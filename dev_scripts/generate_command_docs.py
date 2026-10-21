from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Sequence

try:
    from opengs_maptool.services.command_service import (
        CommandDocumentation,
        get_command_documentation,
    )
    from opengs_maptool.services.parser_service import CommandArgSpec
except ImportError as error:
	raise RuntimeError("The script should be run from the repository root.") from error


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "command_list.md"


def _format_default(value: object) -> str:
	if isinstance(value, bool):
		return str(value).lower()
	return str(value)


def _format_usage(command: CommandDocumentation) -> str:
	tokens = [command.command_id]
	for argument in command.arguments:
		if argument.required:
			tokens.append(f"<{argument.name}>")
		elif argument.arg_type is bool:
			tokens.append(f"[--{argument.name} | --no-{argument.name}]")
		else:
			tokens.append(f"[--{argument.name} {argument.name.upper()}]")
	return " ".join(tokens)


def _render_argument(argument: CommandArgSpec) -> list[str]:
	if argument.required:
		heading = f"#### `<{argument.name}>`"
		requirement = "Required positional argument"
	elif argument.arg_type is bool:
		heading = f"#### `--{argument.name}` / `--no-{argument.name}`"
		requirement = f"Optional; default: `{_format_default(argument.default)}`"
	else:
		heading = f"#### `--{argument.name}`"
		requirement = f"Optional; default: `{_format_default(argument.default)}`"

	lines = [
		heading,
		"",
		f"- Type: `{argument.arg_type.__name__}`",
		f"- {requirement}",
	]
	if argument.choices is not None:
		choices = ", ".join(f"`{choice}`" for choice in argument.choices)
		lines.append(f"- Accepted values: {choices}")
	lines.extend((f"- Description: {argument.description}", ""))
	return lines


def _render_command(command: CommandDocumentation) -> str:
	lines = [
		f"### `{command.command_id}`",
		"",
		command.description,
		"",
	]
	if command.status is not None:
		status_label = {
			"planned": "Planned",
			"in_progress": "Work in progress",
		}[command.status.value]
		lines.extend((f"**Status:** {status_label}", ""))

	lines.extend((
		"**Usage**",
		"",
		"```text",
		_format_usage(command),
		"```",
		"",
		"**Arguments**",
		"",
	))

	if command.arguments:
		for argument in command.arguments:
			lines.extend(_render_argument(argument))
	else:
		lines.extend(("None.", ""))

	if command.aliases:
		aliases = ", ".join(f"`{alias}`" for alias in command.aliases)
		lines.extend(("**Aliases**", "", aliases, ""))

	if command.examples:
		lines.extend(("**Examples**", "", "```text"))
		lines.extend(command.examples)
		lines.extend(("```", ""))

	lines.extend(("---", ""))
	return "\n".join(lines)


def render_command_reference(commands: Sequence[CommandDocumentation]) -> str:
	grouped_commands: dict[str, list[CommandDocumentation]] = defaultdict(list)
	for command in commands:
		namespace = command.command_id.split(".", maxsplit=1)[0]
		grouped_commands[namespace].append(command)

	lines = [
		"# Console Command Reference",
		"",
		"> **Generated documentation:** This file is generated from command registrations. "
		"Update the command definitions and rerun `uv run python dev_scripts/generate_command_docs.py`; "
		"do not edit this generated file directly.",
		"",
		"Append `-h` or `--help` to any command to display its built-in help in the console.",
		"",
	]

	for namespace in sorted(grouped_commands):
		lines.extend((f"## {namespace.capitalize()}", ""))
		for command in sorted(grouped_commands[namespace], key=lambda item: item.command_id):
			lines.append(_render_command(command))

	return "\n".join(lines).rstrip() + "\n"


def main(argv: Sequence[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description="Generate the console command reference.")
	parser.add_argument(
		"--output",
		type=Path,
		default=DEFAULT_OUTPUT,
		help=f"Output Markdown path (default: {DEFAULT_OUTPUT.relative_to(PROJECT_ROOT)}).",
	)
	options = parser.parse_args(argv)

	output_path = options.output
	if not output_path.is_absolute():
		output_path = Path.cwd() / output_path
	output_path.parent.mkdir(parents=True, exist_ok=True)
	output_path.write_text(
		render_command_reference(get_command_documentation()),
		encoding="utf-8",
	)
	print(f"Generated command reference: {output_path}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
