from __future__ import annotations

# Import package to trigger decorator registrations
import opengs_maptool.services.commands  # noqa: F401

# Re-export only the public functions required by external modules
from opengs_maptool.services.command_core import (
    CommandDocumentation,
    CommandDevStatus,
    execute_command_string,
    get_command_documentation,
    serialize_command,
    _single_quotes,
)

def wrap_in_single_quotes(value: str) -> str:
    return _single_quotes(value)

__all__ = [
    "CommandDocumentation",
    "CommandDevStatus",
    "execute_command_string",
    "get_command_documentation",
    "serialize_command",
    "wrap_in_single_quotes",
]
