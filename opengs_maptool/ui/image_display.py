from PIL import Image
from PyQt6.QtWidgets import QLabel, QSizePolicy
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt


class ImageDisplay(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #333")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._image = None

    def set_image(self, image: Image.Image | None) -> None:
        if image is None:
            self._image = None
            self.clear()
            return
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        self._image = image
        qimage = QImage(
            image.tobytes("raw", "RGBA"),
            image.width,
            image.height,
            QImage.Format.Format_RGBA8888
        )
        pixmap = QPixmap.fromImage(qimage)
        pixmap = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio)

        self.setPixmap(pixmap)

    def get_image(self) -> Image.Image | None:
        return self._image
