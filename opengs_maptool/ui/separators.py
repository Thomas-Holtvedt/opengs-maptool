from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget
from PyQt6.QtCore import Qt

class QSeparator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)

class QTextSeparator(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Left line
        line_left = QFrame()
        line_left.setFrameShape(QFrame.HLine)
        line_left.setFrameShadow(QFrame.Sunken)

        # Right line
        line_right = QFrame()
        line_right.setFrameShape(QFrame.HLine)
        line_right.setFrameShadow(QFrame.Sunken)

        # Centered label
        label = QLabel(text, self)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(line_left)
        layout.addWidget(label)
        layout.addWidget(line_right)

def create_separator(text: str = None) -> QFrame:
    if text:
        return QTextSeparator(text)
    return QSeparator()
