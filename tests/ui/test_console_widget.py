import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from opengs_maptool.ui.components.console_widget import ConsoleWidget


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def test_input_scrolls_command_history_and_restores_draft(app):
    history = [SimpleNamespace(text="first.command"), SimpleNamespace(text="second.command")]
    context = SimpleNamespace(
        console_controller=SimpleNamespace(get_command_history=lambda: history)
    )
    widget = ConsoleWidget(context, None)
    input_line = widget._input
    input_line.setText("unfinished")

    QTest.keyClick(input_line, Qt.Key.Key_Up)
    assert input_line.text() == "second.command"

    QTest.keyClick(input_line, Qt.Key.Key_Up)
    assert input_line.text() == "first.command"

    QTest.keyClick(input_line, Qt.Key.Key_Up)
    assert input_line.text() == "first.command"

    QTest.keyClick(input_line, Qt.Key.Key_Down)
    assert input_line.text() == "second.command"

    QTest.keyClick(input_line, Qt.Key.Key_Down)
    assert input_line.text() == "unfinished"

    QTest.keyClick(input_line, Qt.Key.Key_Down)
    assert input_line.text() == "unfinished"

    widget.close()
