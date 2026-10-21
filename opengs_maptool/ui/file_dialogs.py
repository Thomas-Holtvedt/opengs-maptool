import os
import re
import sys

from PyQt6.QtWidgets import QFileDialog
from opengs_maptool.logic.export_module import ExportFormat

IMAGE_FILTERS = (
    "PNG Files (*.png);;"
    "JPEG Files (*.jpg *.jpeg);;"
    "BMP Files (*.bmp);;"
    "GIF Files (*.gif);;"
    "SVG Files (*.svg);;"
    "TIFF Files (*.tiff *.tif);;"
    "WebP Files (*.webp);;"
    "All Files (*)"
)

IMAGE_IMPORT_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.gif)"

DATA_FILTERS = (
    "JSON Files (*.json);;"
    "CSV Files (*.csv);;"
    "YAML Files (*.yaml *.yml);;"
    "XML Files (*.xml);;"
    "All Files (*)"
)

PROJECT_FILTERS = (
    "OpenGS Map Files (*.gsmap);;"
    "ZIP Files (*.zip);;"
    "All Files (*)"
)


def _split_filters(filters: str) -> list[str]:
    return [f.strip() for f in filters.split(";;") if f.strip()]


def _suffixes_in_filter(name_filter: str) -> list[str]:
    """Concrete extensions in a Qt name filter: 'JPEG (*.jpg *.jpeg)' -> ['jpg', 'jpeg'].

    Wildcard-only patterns such as the '(*)' of "All Files" yield nothing, which
    is what marks that filter as imposing no extension.
    """
    match = re.search(r"\(([^)]*)\)", name_filter)
    if not match:
        return []

    suffixes = []
    for pattern in match.group(1).split():
        if pattern.startswith("*.") and len(pattern) > 2 and "*" not in pattern[2:]:
            suffixes.append(pattern[2:].lower())
    return suffixes


def _force_qt_dialogs() -> bool:
    """Whether to bypass the platform's own file dialog.

    The Linux native/portal save dialogs behave inconsistently -- the file-type
    dropdown does not always drive the filename, and they ignore
    setDefaultSuffix(). Windows and macOS keep their native dialogs, which is
    what users of those platforms expect.
    """
    return sys.platform.startswith("linux")


def _with_default_suffix(path: str, name_filter: str) -> str:
    """Append the selected type's extension when the filename has none.

    Mirrors QFileDialog.setDefaultSuffix(), which the native dialogs ignore, so
    that a bare filename ends up with the same extension on every platform.
    """
    suffixes = _suffixes_in_filter(name_filter)
    if not suffixes:
        return path  # "All Files (*)" imposes nothing
    if os.path.splitext(os.path.basename(path))[1]:
        return path  # the user already gave an extension; respect it

    return f"{path}.{suffixes[0]}"


def _run_save_dialog(parent, title: str, filters: str) -> tuple[str | None, str | None]:
    """Save dialog whose filename always agrees with the selected file type.

    The static QFileDialog.getSaveFileName() appends no extension when the user
    types a bare name. Driving the dialog directly lets us set a default suffix
    from the selected type, and -- where Qt's own dialog is used -- gives its
    built-in filter/filename sync as well. The suffix is applied again in Python
    on the way out, because the native dialogs ignore setDefaultSuffix().
    """
    name_filters = _split_filters(filters)

    dialog = QFileDialog(parent, title)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    dialog.setFileMode(QFileDialog.FileMode.AnyFile)
    if _force_qt_dialogs():
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dialog.setNameFilters(name_filters)

    def on_filter_selected(name_filter: str) -> None:
        suffixes = _suffixes_in_filter(name_filter)
        if not suffixes:
            dialog.setDefaultSuffix("")  # "All Files (*)" imposes nothing
            return
        dialog.setDefaultSuffix(suffixes[0])

    on_filter_selected(dialog.selectedNameFilter())
    dialog.filterSelected.connect(on_filter_selected)

    if dialog.exec() != QFileDialog.DialogCode.Accepted:
        return None, None

    selected_files = dialog.selectedFiles()
    if not selected_files:
        return None, None

    selected_filter = dialog.selectedNameFilter()
    return _with_default_suffix(selected_files[0], selected_filter), selected_filter


def pick_open_image(parent, title):
    path, _ = QFileDialog.getOpenFileName(
        parent, title, "", IMAGE_IMPORT_FILTER,
    )
    return path or None


def pick_open_project(parent, title):
    path, _ = QFileDialog.getOpenFileName(parent, title, "", PROJECT_FILTERS)
    return path or None


def pick_save_image(parent, title):
    """Open save dialog for image files and return path with proper extension."""
    path, _ = _run_save_dialog(parent, title, IMAGE_FILTERS)
    return path


def pick_save_project(parent, title):
    """Open save dialog for project files and return path with proper extension."""
    path, _ = _run_save_dialog(parent, title, PROJECT_FILTERS)
    return path


def pick_save_data(parent, title) -> tuple[str | None, ExportFormat | None]:
    """Open save dialog for data files and return (path, format) tuple with proper extension."""
    path, _ = _run_save_dialog(parent, title, DATA_FILTERS)
    if not path:
        return None, None
    return path, ExportFormat.get_by_path(path)
