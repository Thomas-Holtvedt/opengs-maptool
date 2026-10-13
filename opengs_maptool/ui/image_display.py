from PIL import Image
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap, QPainter
from PyQt6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
)

class ImageDisplay(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Graphics scene
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # Image displayed
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        self._image = None
        self._zoom = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 20.0

        # View appearance
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Behavior
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_image(self, image: Image.Image | None):
        """Sets the image to display"""
        if image is None:
            self._image = None
            self._pixmap_item.setPixmap(QPixmap())
            self._scene.setSceneRect(0, 0, 0, 0)
            self._zoom = 1.0
            self.resetTransform()
            return

        if image.mode != "RGBA":
            image = image.convert("RGBA")

        self._image = image

        qimage = QImage(
            self._image.tobytes("raw", "RGBA"),
            self._image.width,
            self._image.height,
            self._image.width * 4,
            QImage.Format.Format_RGBA8888,
        ).copy()

        pixmap = QPixmap.fromImage(qimage)
        
        self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        
        self._fit_image()

    def wheelEvent(self, event):
        """Zoom in and out using the scroll wheel"""

        if self._image is None:
            event.ignore()
            return

        delta = event.angleDelta().y()
        
        if delta > 0:
            self._apply_zoom(1.15)
        elif delta < 0:
            self._apply_zoom(1 / 1.15)

        event.accept()

    def _fit_image(self):
        """Fit the image to the view"""
        if self._image is None:
            return

        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        
        self._zoom = self.transform().m11()

    def _apply_zoom(self, factor):
        if self._image is None:
            return

        new_zoom = self._zoom * factor

        if not self._min_zoom <= new_zoom <= self._max_zoom:
            return

        self.scale(factor, factor)
        self._zoom = new_zoom

    def zoom_in(self):
        self._apply_zoom(1.15)

    def zoom_out(self):
        self._apply_zoom(1 / 1.15)

    def reset_zoom(self):
        """Reset the zoom to the default level (fit to view)"""
        self._fit_image()

    def mouseDoubleClickEvent(self, event):
        """Reset zoom on double click"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset_zoom()
            event.accept()
            return

        super().mouseDoubleClickEvent(event)

    def get_image(self) -> Image.Image | None:
        """Returns the current image being displayed"""
        return self._image
    