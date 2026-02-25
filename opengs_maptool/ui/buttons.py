from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QPushButton, QCheckBox
from PyQt6.QtCore import Qt


def create_slider(
    parent_layout,
    label_text: str,
    minimum: int,
    maximum: int,
    default: int,
    tick_interval: int = 100,
    step: int = 100
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
    value_label = QLabel(str(default))
    row.addWidget(value_label)
    slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
    return slider


def create_button(
    parent_layout,
    label_text: str,
    callback_function
) -> QPushButton:
    button = QPushButton(label_text)
    button.clicked.connect(callback_function)
    parent_layout.addWidget(button)
    return button


def create_checkbox(
    parent_layout,
    label_text: str
):
    button = QCheckBox(label_text)
    parent_layout.addWidget(button)
    return button
