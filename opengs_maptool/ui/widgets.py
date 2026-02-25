from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QPushButton, QLabel


def create_text(parent_layout, text: str, font_size: int = 14) -> QLabel:
    label = QLabel(f'<div style="font-size:{font_size}px;">{text}</div>')
    label.setWordWrap(True)
    parent_layout.addWidget(label)
    return label


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


class ProgressButton(QPushButton):
    """Button with integrated progress bar background."""
    
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self._progress = 0
        self._default_text = text
        self._is_processing = False
        self.setMinimumHeight(35)
        
    def set_progress(self, value: int) -> None:
        """Set progress value (0-100)."""
        self._progress = max(0, min(100, value))
        if not self._is_processing and value > 0:
            self._is_processing = True
            self.setText(f"{self._default_text} - {self._progress}%")
        elif self._is_processing:
            self.setText(f"{self._default_text} - {self._progress}%")
        self.update()  # Trigger repaint
        
    def reset_progress(self) -> None:
        """Reset progress to 0."""
        self._progress = 0
        self._is_processing = False
        self.setText(self._default_text)
        self.update()
        
    def paintEvent(self, event) -> None:
        """Custom paint to show progress as button background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background for the unfilled portion (light gray)
        if self._is_processing:
            background_color = QColor(220, 220, 220, 80)
            painter.fillRect(0, 0, self.width(), self.height(), background_color)
        
        # Draw progress background
        if self._progress > 0:
            progress_width = int((self.width() * self._progress) / 100)
            progress_color = QColor(70, 160, 70, 120)  # Green, semi-transparent
            painter.fillRect(0, 0, progress_width, self.height(), progress_color)
        
        # Let the default button paint on top
        painter.end()
        super().paintEvent(event)
