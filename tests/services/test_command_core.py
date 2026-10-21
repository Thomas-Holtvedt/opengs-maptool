from unittest.mock import MagicMock
import pytest

from opengs_maptool.models.command_response import CommandResponse
from opengs_maptool.models.message import MessageType
from opengs_maptool.services.command_service import CommandDevStatus, get_command_documentation
from opengs_maptool.services.parser_service import CommandArgSpec
import opengs_maptool.services.command_core as command_core


# =====================================================================
# State Isolation Fixture
# =====================================================================

@pytest.fixture(autouse=True)
def reset_command_registry():
    """
    Backup and reset the global registries before and after every test. -> one test should not affect another test

    Explaination: pytest retains global module state (_commands, _command_aliases) across test runs.
    To prevent test pollution and cascading failures, the reset_command_registry fixture
    automatically backs up and resets the registries before each test, yielding execution control,
    and restores the original state during teardown regardless of test outcome.
    """
    original_commands = command_core._commands.copy()
    original_aliases = command_core._command_aliases.copy()

    command_core._commands.clear()
    command_core._command_aliases.clear()

    yield

    command_core._commands = original_commands
    command_core._command_aliases = original_aliases


# =====================================================================
# Registration & Lookup Tests
# =====================================================================

def test_register_command_and_lookup():
    @command_core.register_command(
        "test.ping",
        args=[CommandArgSpec("target", str, "Target host")],
        aliases=["ping"],
    )
    def cmd_ping(context, target: str) -> CommandResponse:
        """Pings a target host."""
        return CommandResponse(f"Pong {target}", MessageType.NORMAL)

    assert command_core.command_exists("test.ping")
    assert command_core.command_exists("ping")
    assert not command_core.command_exists("test.unknown")

    assert "test.ping" in command_core.get_all_command_ids()
    assert "ping"  not in command_core.get_all_command_ids()

    assert "ping"          in command_core.get_all_command_aliases()
    assert "test.ping" not in command_core.get_all_command_aliases()

    assert command_core.get_command_description("test.ping") == "Pings a target host."
    assert command_core.get_command_description("ping") == "Pings a target host."

    specs = command_core.get_command_arg_specs("ping")
    assert len(specs) == 1
    assert specs[0].name == "target"

    func = command_core.get_command_implementation("ping")
    assert func == cmd_ping


def test_command_documentation_api_includes_examples_and_aliases():
    @command_core.register_command(
        "test.documented",
        args=[CommandArgSpec("name", str, "Name to greet")],
        aliases=["documented"],
        examples=["test.documented Ada"],
        status=CommandDevStatus.PLANNED,
    )
    def cmd_documented(context, name: str) -> CommandResponse:
        """Greets a person."""
        return CommandResponse(f"Hello, {name}", MessageType.NORMAL)

    command = next(
        item for item in get_command_documentation()
        if item.command_id == "test.documented"
    )

    assert command.description == "Greets a person."
    assert command.arguments[0].name == "name"
    assert command.aliases == ("documented",)
    assert command.examples == ("test.documented Ada",)
    assert command.status is CommandDevStatus.PLANNED


def test_register_command_duplicate():
    # First time
    @command_core.register_command("duplicate.cmd", args=[], aliases=["alias.cmd"])
    def dummy_func(context): pass

    # Error on the second time
    with pytest.raises(ValueError, match="Command duplicate.cmd is already registered."):
        @command_core.register_command("duplicate.cmd", args=[], aliases=["alias.cmd"])
        def another_func(context): pass


# =====================================================================
# Parsing & Serialization Helper Tests
# =====================================================================

def test_split_command():
    cmd_id, args = command_core.split_command('project.open "C:\\My Maps\\project.gsmap" --force')
    assert cmd_id == "project.open"
    assert args == ["C:\\My Maps\\project.gsmap", "--force"]


def test_split_command_empty():
    cmd_id, args = command_core.split_command("   ")
    assert cmd_id is None
    assert args == []


def test_serialize_command():
    result = command_core.serialize_command(["project.open", "my folder/map.gsmap", 42, True])
    assert result == 'project.open "my folder/map.gsmap" 42 True'


# =====================================================================
# Command Execution Tests
# =====================================================================


class _Signal:
    def __init__(self):
        self._cb = None

    def connect(self, cb):
        self._cb = cb

    def emit(self, *args):
        if self._cb:
            self._cb(*args)


def make_mock_ctx():
    """Create a mock application context whose task_controller behaves like the real one
    for tests: `is_thread_slot_occupied` returns False and `start_task` runs the provided
    function synchronously, emitting the appropriate signals to resolve the Promise.
    """
    mock_ctx = MagicMock()
    mock_task_controller = MagicMock()
    mock_task_controller.is_thread_slot_occupied.return_value = False

    def start_task_side_effect(*args, **kwargs):
        # Create fake task with signals that support .connect and .emit
        class FakeTask:
            def __init__(self):
                class Signals:
                    def __init__(self):
                        self.task_error = _Signal()
                        self.task_successful = _Signal()
                        self.task_cancelled = _Signal()

                self.signals = Signals()

        fake_task = FakeTask()
        before_start = kwargs.get("before_start_callback")
        if before_start:
            before_start(fake_task)

        # Execute the provided function synchronously
        func = kwargs.get("function")
        pos_args = kwargs.get("pos_args", [])
        kw_args = kwargs.get("kw_args", {})
        try:
            result = func(*pos_args, **kw_args)
        except Exception as e:
            fake_task.signals.task_error.emit(e)
            return
        fake_task.signals.task_successful.emit(result)

    mock_task_controller.start_task.side_effect = start_task_side_effect
    mock_ctx.task_controller = mock_task_controller
    return mock_ctx

def test_execute_command_success():
    mock_ctx = make_mock_ctx()

    @command_core.register_command("echo.msg", args=[CommandArgSpec("message", str, "Message to display")])
    def cmd_echo(context, message: str) -> CommandResponse:
        return CommandResponse(f"Echo: {message}", MessageType.NORMAL)

    response = command_core.execute_command_string(mock_ctx, 'echo.msg "Hello World"').get()
    assert response.message == "Echo: Hello World"
    assert response.message_type == MessageType.NORMAL


def test_execute_command_via_list():
    mock_ctx = make_mock_ctx()

    @command_core.register_command("echo.msg", args=[CommandArgSpec("message", str, "Message")])
    def cmd_echo(context, message: str) -> CommandResponse:
        return CommandResponse(message, MessageType.NORMAL)

    cmd_str = command_core.serialize_command(["echo.msg", "Test Message"])
    response = command_core.execute_command_string(mock_ctx, cmd_str).get()
    assert response.message == "Test Message"
    assert response.message_type == MessageType.NORMAL


def test_execute_command_no_command_provided():
    mock_ctx = make_mock_ctx()
    response = command_core.execute_command_string(mock_ctx, "").get()
    assert response.message == "No command provided."
    assert response.message_type == MessageType.ERROR


def test_execute_unknown_command_with_close_match_suggestion():
    mock_ctx = make_mock_ctx()

    @command_core.register_command("project.open", args=[], aliases=["p.open"])
    def cmd_open(context) -> CommandResponse:
        return CommandResponse("Opened", MessageType.NORMAL)

    # Typo on main command
    res1 = command_core.execute_command_string(mock_ctx, "projct.open").get()
    assert res1.message_type == MessageType.ERROR
    assert "Unknown command 'projct.open'. Did you mean 'project.open'?" in res1.message

    # Typo on alias
    res2 = command_core.execute_command_string(mock_ctx, "p.opn").get()
    assert res2.message_type == MessageType.ERROR
    assert "Did you mean 'p.open' (alias of 'project.open')?" in res2.message


def test_execute_unknown_command_no_suggestion():
    mock_ctx = make_mock_ctx()
    response = command_core.execute_command_string(mock_ctx, "completely.unrelated").get()
    assert response.message_type == MessageType.ERROR
    assert "Unknown command 'completely.unrelated' (run 'link.help' for more info)." in response.message


def test_execute_command_invalid_arguments():
    mock_ctx = make_mock_ctx()

    @command_core.register_command("item.count", args=[CommandArgSpec("amount", int, "Amount")])
    def cmd_count(context, amount: int) -> CommandResponse:
        return CommandResponse(f"Count: {amount}", MessageType.NORMAL)

    response = command_core.execute_command_string(mock_ctx, "item.count not_a_number").get()
    assert response.message_type == MessageType.ERROR
    assert "Invalid arguments:" in response.message


# =====================================================================
# Error Handling During Command Function Execution
# =====================================================================

def test_run_command_func_signature_mismatch_type_error():
    mock_ctx = make_mock_ctx()

    # Spec expects 1 arg, but Python function accepts 0 (will cause positional argument mismatch TypeError)
    @command_core.register_command("bad.args", args=[CommandArgSpec("val", str, "Val")])
    def cmd_bad(context) -> CommandResponse:
        return CommandResponse("ok", MessageType.NORMAL)

    response = command_core.execute_command_string(mock_ctx, "bad.args test").get()
    assert response.message_type == MessageType.ERROR
    assert "Internal Error: registered and implemented arguments" in response.message


def test_run_command_func_unexpected_exception():
    mock_ctx = make_mock_ctx()

    @command_core.register_command("failing.cmd", args=[])
    def cmd_fail(context) -> CommandResponse:
        raise RuntimeError("Something went horribly wrong")

    response = command_core.execute_command_string(mock_ctx, "failing.cmd").get()
    assert response.message_type == MessageType.ERROR
    assert "Unexpected error executing command 'failing.cmd': Something went horribly wrong" in response.message
