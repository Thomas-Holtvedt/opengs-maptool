import pytest
from opengs_maptool.services.parser_service import (
    CommandArgSpec,
    CommandArgumentParseError,
    CommandParserConfigurationError,
    deserialize_command_arguments,
)


# =====================================================================
# 1. Spec Validation Tests (_validate_argument_specs)
# =====================================================================

def test_validate_specs_duplicate_argument_names():
    specs = [
        CommandArgSpec("path", str, "Path 1"),
        CommandArgSpec("path", str, "Path 2"),
    ]
    with pytest.raises(CommandParserConfigurationError, match="declares argument 'path' more than once"):
        deserialize_command_arguments("test.cmd", "desc", ["value"], specs)


def test_validate_specs_invalid_identifier_name():
    specs = [CommandArgSpec("invalid-name!", str, "Invalid identifier")]
    with pytest.raises(CommandParserConfigurationError, match="has an invalid argument name"):
        deserialize_command_arguments("test.cmd", "desc", ["value"], specs)


def test_validate_specs_leading_underscore_name():
    specs = [CommandArgSpec("_private", str, "Private name")]
    with pytest.raises(CommandParserConfigurationError, match="has an invalid argument name"):
        deserialize_command_arguments("test.cmd", "desc", ["value"], specs)


def test_validate_specs_unsupported_type():
    specs = [CommandArgSpec("data", dict, "Unsupported dict type")]  # type: ignore[arg-type]
    with pytest.raises(CommandParserConfigurationError, match="uses an unsupported type"):
        deserialize_command_arguments("test.cmd", "desc", ["value"], specs)


def test_validate_specs_invalid_default_type():
    # Argument expected to be int, but default is str
    specs = [CommandArgSpec("count", int, "Count option", default="ten")]
    with pytest.raises(CommandParserConfigurationError, match="has an invalid default"):
        deserialize_command_arguments("test.cmd", "desc", [], specs)


# =====================================================================
# 2. Command Deserialization Tests (Positional & Optional Flags)
# =====================================================================

def test_deserialize_zero_arguments_expected_and_given():
    result = deserialize_command_arguments("test.cmd", "desc", [], [])
    assert result == []


def test_deserialize_zero_arguments_expected_but_given_some():
    with pytest.raises(CommandArgumentParseError, match="expects 0 param\(s\)"):
        deserialize_command_arguments("test.cmd", "desc", ["extra_arg"], [])


def test_deserialize_positional_string_arguments():
    specs = [
        CommandArgSpec("src", str, "Source path"),
        CommandArgSpec("dst", str, "Destination path"),
    ]
    result = deserialize_command_arguments("test.cmd", "desc", ["file1.txt", "file2.txt"], specs)
    assert result == ["file1.txt", "file2.txt"]


def test_deserialize_missing_required_positional_arguments():
    specs = [CommandArgSpec("path", str, "Required path")]
    with pytest.raises(CommandArgumentParseError, match="Missing required argument\(s\): path"):
        deserialize_command_arguments("test.cmd", "desc", [], specs)


def test_deserialize_optional_flag_defaults():
    specs = [
        CommandArgSpec("path", str, "Required path"),
        CommandArgSpec("force", bool, "Force overwrite", default=False),
    ]
    result = deserialize_command_arguments("test.cmd", "desc", ["my_file.txt"], specs)
    assert result == ["my_file.txt", False]


def test_deserialize_optional_boolean_flags():
    specs = [
        CommandArgSpec("force", bool, "Force switch", default=False),
    ]

    # Enabling flag
    result = deserialize_command_arguments("test.cmd", "desc", ["--force"], specs)
    assert result == [True]

    # Disabling flag via argparse BooleanOptionalAction (--no-force)
    result = deserialize_command_arguments("test.cmd", "desc", ["--no-force"], specs)
    assert result == [False]


def test_deserialize_optional_string_and_numeric_settings():
    specs = [
        CommandArgSpec("path", str, "Required path"),
        CommandArgSpec("format", str, "Format setting", default="png"),
        CommandArgSpec("scale", int, "Scale factor", default=1),
    ]

    args = ["output.png", "--format", "jpeg", "--scale", "2"]
    result = deserialize_command_arguments("test.cmd", "desc", args, specs)
    assert result == ["output.png", "jpeg", 2]


# =====================================================================
# 3. Type Conversion & Validation Tests (_convert_value & _parse_bool)
# =====================================================================

def test_type_conversion_valid_integers_and_floats():
    specs = [
        CommandArgSpec("count", int, "Count"),
        CommandArgSpec("ratio", float, "Ratio"),
    ]
    result = deserialize_command_arguments("test.cmd", "desc", ["42", "3.14159"], specs)
    assert result == [42, 3.14159]


def test_type_conversion_invalid_integer():
    specs = [CommandArgSpec("count", int, "Count")]
    with pytest.raises(CommandArgumentParseError, match="Argument 'count' \(position 0\) must be an integer, got 'abc'"):
        deserialize_command_arguments("test.cmd", "desc", ["abc"], specs)


def test_type_conversion_invalid_float():
    specs = [CommandArgSpec("ratio", float, "Ratio")]
    with pytest.raises(CommandArgumentParseError, match="Argument 'ratio' \(position 0\) must be a float, got 'xyz'"):
        deserialize_command_arguments("test.cmd", "desc", ["xyz"], specs)


@pytest.mark.parametrize("truthy_value", ["1", "true", "TRUE", "yes", "on"])
def test_parse_bool_truthy_variations(truthy_value: str):
    specs = [CommandArgSpec("flag", bool, "Flag")]
    result = deserialize_command_arguments("test.cmd", "desc", [truthy_value], specs)
    assert result == [True]


@pytest.mark.parametrize("falsy_value", ["0", "false", "FALSE", "no", "off"])
def test_parse_bool_falsy_variations(falsy_value: str):
    specs = [CommandArgSpec("flag", bool, "Flag")]
    result = deserialize_command_arguments("test.cmd", "desc", [falsy_value], specs)
    assert result == [False]


def test_parse_bool_invalid_string():
    specs = [CommandArgSpec("flag", bool, "Flag")]
    with pytest.raises(CommandArgumentParseError, match="Argument 'flag' \(position 0\) must be a boolean, got 'maybe'"):
        deserialize_command_arguments("test.cmd", "desc", ["maybe"], specs)


# =====================================================================
# 4. Built-in Help & Unrecognized Arguments Tests
# =====================================================================

@pytest.mark.parametrize("help_flag", ["-h", "--help"])
def test_help_flag_raises_formatted_help(help_flag: str):
    specs = [CommandArgSpec("path", str, "Target file path")]
    with pytest.raises(CommandArgumentParseError) as exc_info:
        deserialize_command_arguments("project.open", "Opens a project file", [help_flag], specs)

    error_msg = str(exc_info.value)
    assert "project.open" in error_msg
    assert "Target file path" in error_msg


def test_unrecognized_arguments_error_formatting():
    specs = [CommandArgSpec("path", str, "Path")]
    with pytest.raises(CommandArgumentParseError, match="Unknown argument\(s\) or optional flag\(s\): --unknown"):
        deserialize_command_arguments("test.cmd", "desc", ["file.txt", "--unknown"], specs)


def test_validate_specs_choices_type_mismatch():
    specs = [CommandArgSpec("fmt", int, "Format", choices=["png", "jpeg"]) ]  # choices are strings, type is int
    with pytest.raises(CommandParserConfigurationError, match="has an invalid choice"):
        deserialize_command_arguments("test.cmd", "desc", [], specs)


def test_deserialize_with_choices_valid_and_invalid():
    specs = [
        CommandArgSpec("path", str, "Required path"),
        CommandArgSpec("format", str, "Format setting", default="png", choices=["png", "jpeg"]),
    ]

    # valid choice
    args = ["output.png", "--format", "jpeg"]
    result = deserialize_command_arguments("test.cmd", "desc", args, specs)
    assert result == ["output.png", "jpeg"]

    # invalid choice
    args = ["output.png", "--format", "gif"]
    with pytest.raises(CommandArgumentParseError, match="Invalid value for argument 'format'"):
        deserialize_command_arguments("test.cmd", "desc", args, specs)


def test_deserialize_required_positional_argument_with_choices():
    specs = [CommandArgSpec("format", str, "Output format", choices=["json", "csv"])]

    assert deserialize_command_arguments("test.cmd", "desc", ["csv"], specs) == ["csv"]
    with pytest.raises(CommandArgumentParseError, match="Invalid value for argument 'format'"):
        deserialize_command_arguments("test.cmd", "desc", ["xml"], specs)


@pytest.mark.parametrize(
    "arg_type, default, choices, error_message, required",
    [
        (str, None, [], "has invalid choices", True),
        (bool, False, [True], "cannot use choices for boolean argument", False),
        (str, "xml", ["json", "csv"], "has an invalid default", False),
    ],
)
def test_validate_choice_specifications(arg_type, default, choices, error_message, required):
    if required:
        spec = CommandArgSpec("format", arg_type, "Output format", choices=choices)
    else:
        spec = CommandArgSpec("format", arg_type, "Output format", default=default, choices=choices)
    with pytest.raises(CommandParserConfigurationError, match=error_message):
        deserialize_command_arguments("test.cmd", "desc", [], [spec])
