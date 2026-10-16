import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QFileDialog, QLineEdit

from opengs_maptool.ui import file_dialogs as fd


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def save_dialog(qapp, monkeypatch):
    """Drive a real QFileDialog: type a name, optionally switch the type, accept."""
    def run(filters, typed, filter_index=None, accept=True):
        captured = {}

        def fake_exec(dialog):
            line_edit = dialog.findChild(QLineEdit, "fileNameEdit")
            line_edit.setText(typed)
            if filter_index is not None:
                chosen = dialog.nameFilters()[filter_index]
                dialog.selectNameFilter(chosen)
                dialog.filterSelected.emit(chosen)
            captured["shown"] = line_edit.text()
            captured["default_suffix"] = dialog.defaultSuffix()
            return (QFileDialog.DialogCode.Accepted if accept
                    else QFileDialog.DialogCode.Rejected).value

        monkeypatch.setattr(QFileDialog, "exec", fake_exec)
        captured["result"] = fd._run_save_dialog(None, "t", filters)
        return captured

    return run


def test_suffixes_in_filter():
    assert fd._suffixes_in_filter("JPEG Files (*.jpg *.jpeg)") == ["jpg", "jpeg"]
    assert fd._suffixes_in_filter("OpenGS Map Files (*.gsmap)") == ["gsmap"]
    assert fd._suffixes_in_filter("All Files (*)") == []


def test_svg_is_available_for_image_export_but_not_import():
    assert "SVG Files (*.svg)" in fd._split_filters(fd.IMAGE_FILTERS)
    assert "*.svg" not in fd.IMAGE_IMPORT_FILTER


@pytest.mark.parametrize("selected_path, expected", [("/tmp/map.png", "/tmp/map.png"), ("", None)])
def test_pick_open_image_uses_supported_filter_and_normalizes_empty_result(
    monkeypatch, selected_path, expected
):
    captured = {}

    def fake_get_open_file_name(parent, title, directory, name_filter):
        captured["name_filter"] = name_filter
        return selected_path, name_filter

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)

    assert fd.pick_open_image(None, "Open image") == expected
    assert captured["name_filter"] == fd.IMAGE_IMPORT_FILTER


def test_bare_project_name_gets_the_gsmap_extension(save_dialog):
    captured = save_dialog(fd.PROJECT_FILTERS, "mymap")
    path, _ = captured["result"]
    assert captured["default_suffix"] == "gsmap"
    assert os.path.basename(path) == "mymap.gsmap"


def test_bare_image_name_follows_the_selected_type(save_dialog):
    bmp_index = fd._split_filters(fd.IMAGE_FILTERS).index("BMP Files (*.bmp)")
    captured = save_dialog(fd.IMAGE_FILTERS, "world", bmp_index)
    path, _ = captured["result"]
    assert os.path.basename(path) == "world.bmp"


def test_all_files_imposes_no_extension(save_dialog):
    all_index = fd._split_filters(fd.IMAGE_FILTERS).index("All Files (*)")
    captured = save_dialog(fd.IMAGE_FILTERS, "raw", all_index)
    path, _ = captured["result"]
    assert captured["default_suffix"] == ""
    assert os.path.basename(path) == "raw"


def test_cancelling_returns_nothing(save_dialog):
    captured = save_dialog(fd.PROJECT_FILTERS, "mymap", accept=False)
    assert captured["result"] == (None, None)


@pytest.mark.parametrize("typed, filter_index, expected, expected_fmt", [
    ("defs", 0, "defs.json", fd.ExportFormat.JSON),
    ("defs", 1, "defs.csv", fd.ExportFormat.CSV),
    ("defs", 2, "defs.yaml", fd.ExportFormat.YAML),
    ("defs", 3, "defs.xml", fd.ExportFormat.XML),
])
def test_pick_save_data_reports_the_format_of_the_chosen_type(
    qapp, monkeypatch, typed, filter_index, expected, expected_fmt
):
    def fake_exec(dialog):
        dialog.findChild(QLineEdit, "fileNameEdit").setText(typed)
        chosen = dialog.nameFilters()[filter_index]
        dialog.selectNameFilter(chosen)
        dialog.filterSelected.emit(chosen)
        return QFileDialog.DialogCode.Accepted.value

    monkeypatch.setattr(QFileDialog, "exec", fake_exec)
    path, fmt = fd.pick_save_data(None, "t")
    assert os.path.basename(path) == expected
    assert fmt == expected_fmt


def test_pick_save_data_returns_none_pair_when_cancelled(qapp, monkeypatch):
    monkeypatch.setattr(
        QFileDialog, "exec", lambda dialog: QFileDialog.DialogCode.Rejected.value
    )
    assert fd.pick_save_data(None, "t") == (None, None)


# --- platform behaviour ------------------------------------------------------

def test_qt_dialogs_are_forced_only_on_linux(monkeypatch):
    for platform, forced in [("linux", True), ("win32", False), ("darwin", False)]:
        monkeypatch.setattr(fd.sys, "platform", platform)
        assert fd._force_qt_dialogs() is forced, platform


@pytest.mark.parametrize("path, name_filter, expected", [
    ("/tmp/mymap", "OpenGS Map Files (*.gsmap)", "/tmp/mymap.gsmap"),
    ("/tmp/world", "JPEG Files (*.jpg *.jpeg)", "/tmp/world.jpg"),
    # An extension the user typed is respected, whatever it is.
    ("/tmp/mymap.gsmap", "OpenGS Map Files (*.gsmap)", "/tmp/mymap.gsmap"),
    ("/tmp/notes.backup", "XML Files (*.xml)", "/tmp/notes.backup"),
    # "All Files" imposes nothing.
    ("/tmp/raw", "All Files (*)", "/tmp/raw"),
    # A dotted directory must not be mistaken for a file extension.
    ("/home/a.b/mymap", "OpenGS Map Files (*.gsmap)", "/home/a.b/mymap.gsmap"),
])
def test_with_default_suffix(path, name_filter, expected):
    assert fd._with_default_suffix(path, name_filter) == expected


def test_native_dialog_still_gets_the_extension(qapp, monkeypatch):
    """Windows keeps its native dialog, which ignores setDefaultSuffix()."""
    monkeypatch.setattr(fd, "_force_qt_dialogs", lambda: False)
    seen = {}

    def fake_exec(dialog):
        seen["native_disabled"] = dialog.testOption(QFileDialog.Option.DontUseNativeDialog)
        dialog.findChild(QLineEdit, "fileNameEdit").setText("mymap")
        return QFileDialog.DialogCode.Accepted.value

    monkeypatch.setattr(QFileDialog, "exec", fake_exec)
    path = fd.pick_save_project(None, "Save project")

    assert seen["native_disabled"] is False, "native dialog should not be disabled"
    assert os.path.basename(path) == "mymap.gsmap"


def test_qt_dialog_is_disabled_on_linux(qapp, monkeypatch):
    monkeypatch.setattr(fd, "_force_qt_dialogs", lambda: True)
    seen = {}

    def fake_exec(dialog):
        seen["native_disabled"] = dialog.testOption(QFileDialog.Option.DontUseNativeDialog)
        dialog.findChild(QLineEdit, "fileNameEdit").setText("mymap")
        return QFileDialog.DialogCode.Accepted.value

    monkeypatch.setattr(QFileDialog, "exec", fake_exec)
    path = fd.pick_save_project(None, "Save project")

    assert seen["native_disabled"] is True
    assert os.path.basename(path) == "mymap.gsmap"
