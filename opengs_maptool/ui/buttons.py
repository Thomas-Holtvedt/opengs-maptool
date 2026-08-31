from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QPushButton, QCheckBox
from PyQt6.QtCore import Qt, pyqtSignal

from vcolorpicker import getColor

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
    colorChanged = pyqtSignal(tuple)

    def __init__(self, color, parent=None):
        super().__init__("", parent)

        self.clicked.connect(self._get_color)
        self._update(color)

    def _get_color(self):
        color = tuple(map(int, getColor()))
        self._update(color)

        self.colorChanged.emit(color)

    def _update(self, color):
        self.setText(str(color))
        self.setStyleSheet("background-color: rgb" + str(color) + ";")
