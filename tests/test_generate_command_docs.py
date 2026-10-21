from dev_scripts.generate_command_docs import render_command_reference
from opengs_maptool.services.command_core import CommandDocumentation, CommandDevStatus
from opengs_maptool.services.parser_service import CommandArgSpec


def test_renderer_formats_argument_metadata_and_omits_empty_optional_sections():
    command = CommandDocumentation(
        command_id="export.map",
        description="Exports a map.",
        arguments=(
            CommandArgSpec("format", str, "Output format.", choices=["png", "svg"]),
            CommandArgSpec("force", bool, "Overwrite the target.", default=False),
        ),
        aliases=(),
        examples=(),
    )

    documentation = render_command_reference([command])

    assert "## Export" in documentation
    assert "export.map <format> [--force | --no-force]" in documentation
    assert "Accepted values: `png`, `svg`" in documentation
    assert "Optional; default: `false`" in documentation
    assert "**Aliases**" not in documentation
    assert "**Examples**" not in documentation


def test_renderer_includes_aliases_and_examples_when_registered():
    command = CommandDocumentation(
        command_id="project.open",
        description="Opens a project.",
        arguments=(),
        aliases=("p.open",),
        examples=('project.open "map.gsmap"',),
    )

    documentation = render_command_reference([command])

    assert "**Aliases**\n\n`p.open`" in documentation
    assert '**Examples**\n\n```text\nproject.open "map.gsmap"' in documentation


def test_renderer_shows_declared_command_status_and_omits_unset_status():
    commands = [
        CommandDocumentation(
            command_id="planned.command",
            description="A planned command.",
            arguments=(),
            aliases=(),
            examples=(),
            status=CommandDevStatus.PLANNED,
        ),
        CommandDocumentation(
            command_id="in_progress.command",
            description="A command under development.",
            arguments=(),
            aliases=(),
            examples=(),
            status=CommandDevStatus.IN_PROGRESS,
        ),
        CommandDocumentation(
            command_id="implemented.command",
            description="An implemented command.",
            arguments=(),
            aliases=(),
            examples=(),
        ),
    ]

    documentation = render_command_reference(commands)

    assert "**Status:** Planned" in documentation
    assert "**Status:** Work in progress" in documentation
    implemented_entry = documentation.split("### `implemented.command`", maxsplit=1)[1]
    implemented_entry = implemented_entry.split("\n---", maxsplit=1)[0]
    assert "**Status:**" not in implemented_entry
