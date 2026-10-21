from html import escape
import opengs_maptool.config as config
from opengs_maptool.controllers.task_controller import ThreadTaskSlot
from opengs_maptool.context import ApplicationContext
from opengs_maptool.services.command_service import execute_command_string, serialize_command
from opengs_maptool.models.command_response import CommandResponse
from opengs_maptool.models.message import Message, MessageAuthor, MessageType
from opengs_maptool.ui.modals.error_modal import ErrorModal
from PyQt6.QtCore import QEventLoop, Qt
from PyQt6.QtGui import QFontDatabase, QKeyEvent, QTextCursor
from PyQt6.QtWidgets import QFileDialog, QTextEdit, QVBoxLayout, QWidget, QLineEdit, QPushButton, QHBoxLayout, QSizePolicy


class _CommandInput(QLineEdit):
    def __init__(self, history_provider):
        super().__init__()
        self._history_provider = history_provider
        self._history: list[str] = []
        self._history_index: int | None = None
        self._draft = ""
        self.textEdited.connect(self._reset_history_navigation)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.modifiers() == Qt.KeyboardModifier.NoModifier:
            if event.key() == Qt.Key.Key_Up and self._show_previous_command():
                event.accept()
                return
            if event.key() == Qt.Key.Key_Down and self._show_next_command():
                event.accept()
                return
        super().keyPressEvent(event)

    def _show_previous_command(self) -> bool:
        if self._history_index is None:
            commands = self._history_provider()
            if not commands:
                return False
            self._history = [command.text for command in reversed(commands)]
            self._history_index = 0
            self._draft = self.text()
        else:
            self._history_index = min(len(self._history) - 1, self._history_index + 1)

        self.setText(self._history[self._history_index])
        return True

    def _show_next_command(self) -> bool:
        if self._history_index is None:
            return False

        if self._history_index > 0:
            self._history_index -= 1
            self.setText(self._history[self._history_index])
        else:
            draft = self._draft
            self._reset_history_navigation()
            self.setText(draft)
        return True

    def _reset_history_navigation(self, _text: str = "") -> None:
        self._history = []
        self._history_index = None
        self._draft = ""


class ConsoleWidget(QWidget):
    def __init__(self, context: ApplicationContext, main_window):
        super().__init__()
        self._context = context
        self._main_window = main_window

        monospace_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

        layout = QVBoxLayout()

        # Output log (read-only)
        self._output = QTextEdit()
        self._output.setFont(monospace_font)
        self._output.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._output.setReadOnly(True)
        self._output.setPlaceholderText("Type 'link.help' for a help link.")
        layout.addWidget(self._output)

        # Input line (for user commands)
        self._input = _CommandInput(self._context.console_controller.get_command_history)
        self._input.setFont(monospace_font)
        self._input.setPlaceholderText("Enter command...")
        self._input.returnPressed.connect(self._submit_user_command)
        layout.addWidget(self._input)

        # Buttons
        self._btn_export_logs = QPushButton("Export Logs")
        self._btn_export_logs.clicked.connect(self._export_logs)

        self._btn_restore_logs = QPushButton("Restore Logs")
        self._btn_restore_logs.clicked.connect(self._restore_logs)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self._btn_export_logs)
        buttons_layout.addWidget(self._btn_restore_logs)
        layout.addLayout(buttons_layout)

        # Keep controls compact while allowing the output area to consume extra vertical space.
        layout.setStretch(0, 1)
        layout.setStretch(1, 0)
        layout.setStretch(2, 0)

        self.setLayout(layout)


    def print_message(self, message: Message):
        """
        Displays a message in the console widget.
        The text style varies depending on the author and the type of message.

        @param message: The message to display
        """
        message_text = message.text
        message_color = None

        match message.type:
            case MessageType.COMMAND:
                message_color = config.CONSOLE_COMMAND_COLOR
                if message.author == MessageAuthor.USER:
                    message_text = f"USER COMMAND >> {message_text}"
                elif message.author == MessageAuthor.SYSTEM:
                    message_text = f"AUTOMATED COMMAND >> {message_text}"

            case MessageType.NORMAL:
                message_color = config.CONSOLE_NORMAL_COLOR
            case MessageType.INFO:
                message_color = config.CONSOLE_INFO_COLOR
            case MessageType.SUCCESS:
                message_color = config.CONSOLE_SUCCESS_COLOR
            case MessageType.WARNING:
                message_color = config.CONSOLE_WARNING_COLOR
            case MessageType.ERROR:
                message_color = config.CONSOLE_ERROR_COLOR


        if message_color is not None:
            # QTextEdit collapses '\n' in rich text; use <br> for visible line breaks.
            html_text = escape(message_text).replace("\n", "<br>")
            self._output.append(f"<span style='color: {message_color};'>{html_text}</span>")
        else:
            # Insert as plain text to avoid accidental HTML parsing.
            self._output.moveCursor(QTextCursor.MoveOperation.End)
            self._output.insertPlainText(message_text + "\n")

        self._output.verticalScrollBar().setValue(self._output.verticalScrollBar().maximum())


    def _submit_user_command(self) -> None:
        """
        Sends and displays a user command in the console
        """
        if self._context.task_controller.is_thread_slot_occupied(ThreadTaskSlot.execute_command):
            return

        self._input._reset_history_navigation()
        user_message_text = self._input.text().strip()
        self._input.clear()

        if len(user_message_text) == 0:
            return

        command_message = self._context.console_controller.add_command_message(user_message_text, MessageAuthor.USER)
        self.print_message(command_message) # Show message in widget

        promise = execute_command_string(self._context, command_message.text)
        promise.then(self._process_command_response)

    def submit_system_command(self, command_segments: list[str]) -> CommandResponse:
        """Send a command and return response without blocking the UI."""
        command_text = serialize_command(command_segments)
        command_message = self._context.console_controller.add_command_message(command_text, MessageAuthor.SYSTEM)
        self.print_message(command_message)

        promise = execute_command_string(self._context, command_text)

        response = None
        def callback(r):
            nonlocal response
            response = r
            self._process_command_response(response)
            loop.quit()
        promise.then(callback)

        loop = QEventLoop()
        loop.exec()

        return response

    def _process_command_response(self, response: CommandResponse) -> None:
        message = response.as_message()
        self._context.console_controller.add_response_message(
            message.text,
            message.type
        )
        self.print_message(message)

    def _export_logs(self):
        filename, _ = QFileDialog.getSaveFileName(
            None, "Export console history", "", "CSV Files (*.csv);;All Files (*)"
        )

        if not filename:
            return

        self._context.console_controller.export_console(filename)


    def _restore_logs(self):
        """
        Restores a message history in the console and displays it in the widget
        """
        filename, _ = QFileDialog.getOpenFileName(
            None, "Import console history", "", "CSV Files (*.csv);;All Files (*)"
        )

        if not filename:
            return

        try:
            self._console_controller.import_console(filename)
            self._output.clear()

            for message in self._context.console.messages:
                self.print_message(message)
        except Exception:
            error_text = "Cannot open this file, incompatible format"
            error_modal = ErrorModal(self._main_window, error_text)
            error_modal.exec()
