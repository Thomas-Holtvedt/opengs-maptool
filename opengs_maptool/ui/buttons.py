from PyQt6.QtWidgets import (
    QColorDialog, QHBoxLayout, QLabel, QSlider, QPushButton, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

def create_slider(
    parent_layout,
    label_text: str,
    minimum: int,
    maximum: int,
    default: int,
    tick_interval: int = 100,
    step: int = 100,
    onchange_callback_function = None,
    display_scale: float = None
):

    row = QHBoxLayout()
    parent_layout.addLayout(row)

    label = QLabel(label_text)
    row.addWidget(label)

    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setMinimum(minimum)
    slider.setMaximum(maximum)
    slider.setValue(default)
    slider.setTickInterval(tick_interval)
    slider.setSingleStep(step)
    row.addWidget(slider, stretch=1)

    def format_value(v):
        if display_scale is not None:
            return f"{v * display_scale:.1f}"
        return str(v)

    value_label = QLabel(format_value(default))
    row.addWidget(value_label)
    slider.valueChanged.connect(lambda v: value_label.setText(format_value(v)))
    if onchange_callback_function:
        slider.valueChanged.connect(onchange_callback_function)
    return slider


def create_button(
    parent_layout,
    label_text: str,
    callback_function
):
    button = QPushButton(label_text)
    button.clicked.connect(callback_function)
    parent_layout.addWidget(button)
    return button


def create_checkbox(
    parent_layout,
    label_text: str,
    callback_function = None
):
    checkbox = QCheckBox(label_text)
    if callback_function:
        checkbox.stateChanged.connect(callback_function)

    parent_layout.addWidget(checkbox)
    return checkbox


class ColorPickerButton(QPushButton):
    """A swatch button that opens a color dialog pre-set to its current color.

    Qt's own dialog is used rather than a third-party frameless one: it picks up
    the Fusion palette like the rest of the tool, and it is a real window, so the
    window manager gives it a title bar that can be dragged and a close button.
    """

    colorChanged = pyqtSignal(tuple)

    def __init__(self, color, parent=None, title="Select Color"):
        super().__init__("", parent)

        self._title = title
        self._color = tuple(color)

        self.clicked.connect(self._get_color)
        self._update(self._color)

    def color(self) -> tuple[int, int, int]:
        return self._color

    def set_color(self, color) -> None:
        """Set the swatch without emitting colorChanged."""
        self._update(tuple(color))

    def _get_color(self):
        chosen = QColorDialog.getColor(
            QColor(*self._color),
            self,
            self._title,
            # Keep the Qt-drawn dialog so it matches the rest of the app instead
            # of whatever the platform would substitute.
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )

        if not chosen.isValid():
            # Dialog was cancelled — leave the current color untouched.
            return

        color = (chosen.red(), chosen.green(), chosen.blue())
        if color == self._color:
            return

        self._update(color)
        self.colorChanged.emit(color)

    def _update(self, color):
        self._color = color
        r, g, b = color

        self.setText(f"({r}, {g}, {b})")
        self.setToolTip(f"{self._title} — currently #{r:02X}{g:02X}{b:02X}")

        # Keep the label legible on both dark and light swatches.
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        text_color = "#000000" if luminance > 0.5 else "#ffffff"

        self.setStyleSheet(
            "QPushButton {"
            f"background-color: rgb({r}, {g}, {b});"
            f"color: {text_color};"
            "border: 1px solid palette(mid);"
            "border-radius: 3px;"
            "padding: 4px 8px;"
            "}"
            "QPushButton:hover { border: 1px solid palette(highlight); }"
        )
