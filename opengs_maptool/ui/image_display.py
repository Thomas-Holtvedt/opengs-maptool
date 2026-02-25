import numpy as np
from numpy.typing import NDArray
from pathlib import Path
from PIL import Image
from PyQt6.QtWidgets import QWidget, QGridLayout, QHBoxLayout, QLabel, QFileDialog, QPushButton, QScrollArea
from PyQt6.QtGui import QPixmap, QImage, QIcon
from PyQt6.QtCore import Qt, QSize

from opengs_maptool.logic import export_to_json, export_to_csv
from opengs_maptool import config


EMPTY_IMAGE = Image.new("RGB", (160, 90), color=(100, 100, 100))


class _ZoomableImageLabel(QLabel):
    def fit_to_widget(self):
        """Set zoom so the image fills the widget size (keeping aspect ratio, but maximizing area)."""
        if self._original_pixmap is None:
            return
        label_w = max(1, self.width())
        label_h = max(1, self.height())
        pixmap_w = self._original_pixmap.width()
        pixmap_h = self._original_pixmap.height()
        if pixmap_w == 0 or pixmap_h == 0:
            return
        scale_w = label_w / pixmap_w
        scale_h = label_h / pixmap_h
        fit_zoom = min(scale_w, scale_h)
        # If the image is smaller than the widget, scale up to fill
        fit_zoom = max(fit_zoom, 1.0)
        self.set_zoom(fit_zoom)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 10.0
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #333")
        self.setScaledContents(False)
        self.setMinimumSize(400, 300)
        self._original_pixmap = None

    def setPixmap(self, pixmap: QPixmap, auto_fit: bool = False):
        self._original_pixmap = pixmap
        # Set minimum size to fill parent
        self.setMinimumSize(self.parentWidget().width(), self.parentWidget().height()) if self.parentWidget() else None
        if auto_fit:
            self.fit_to_widget()
        else:
            self._update_pixmap()

    def _update_pixmap(self):
        if self._original_pixmap is None:
            return
        w = int(self._original_pixmap.width() * self._zoom)
        h = int(self._original_pixmap.height() * self._zoom)
        scaled = self._original_pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        super().setPixmap(scaled)

    def wheelEvent(self, event):
        # Ctrl+Wheel or touchpad pinch for zoom, else propagate
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle = event.angleDelta().y()
            factor = 1.25 if angle > 0 else 0.8
            self.set_zoom(self._zoom * factor)
            event.accept()
        else:
            event.ignore()

    def set_zoom(self, zoom: float):
        zoom = max(self._min_zoom, min(self._max_zoom, zoom))
        if abs(zoom - self._zoom) > 1e-4:
            self._zoom = zoom
            self._update_pixmap()

    def get_zoom(self):
        return self._zoom

    def resizeEvent(self, event):
        # If zoom is close to auto-fit, refit on resize; otherwise, keep manual zoom
        prev_zoom = self._zoom
        if self._original_pixmap is not None:
            label_w = max(1, self.width())
            label_h = max(1, self.height())
            pixmap_w = self._original_pixmap.width()
            pixmap_h = self._original_pixmap.height()
            scale_w = label_w / pixmap_w
            scale_h = label_h / pixmap_h
            fit_zoom = min(scale_w, scale_h)
            # If user hasn't zoomed, or zoom is close to fit, auto-fit on resize
            if abs(prev_zoom - fit_zoom) < 1e-2 or abs(prev_zoom - 1.0) < 1e-2:
                self.set_zoom(fit_zoom)
            else:
                self._update_pixmap()
        else:
            self._update_pixmap()
        super().resizeEvent(event)

class ImageDisplay(QWidget):
    """Widget that displays an image with export controls, scrolling, and zooming.

    Args:
        name: Label used in export dialogs and filenames.
        parent: Optional parent widget.
        csv_export: When True, enables CSV export for list-of-dict data.
    """
    def __init__(self, name: str, parent=None, csv_export: bool = False) -> None:
        super().__init__(parent)
        self.name = name
        self.csv_export = csv_export
        self.setMinimumSize(400, 300)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scrollable, zoomable image label
        self._image_label = _ZoomableImageLabel()
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setWidget(self._image_label)
        self._scroll_area.setMinimumSize(400, 300)
        layout.addWidget(self._scroll_area, 0, 0)

        # Button container for top-right buttons
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(5, 5, 5, 0)
        button_layout.setSpacing(5)
        button_layout.addStretch()

        # Example image button (icon, leftmost)
        self._example_image_button = QPushButton()
        example_icon_path = Path(__file__).resolve().parent / "assets" / "example-icon.svg"
        if example_icon_path.exists():
            self._example_image_button.setIcon(QIcon(str(example_icon_path)))
            self._example_image_button.setIconSize(QSize(24, 24))
        else:
            self._example_image_button.setText("Ex")
        self._example_image_button.setMaximumSize(40, 40)
        self._example_image_button.setStyleSheet(
            "QPushButton { "
            "  background-color: rgba(0, 0, 0, 150); "
            "  border: none; "
            "  border-radius: 5px; "
            "  padding: 5px; "
            "} "
            "QPushButton:hover { background-color: rgba(0, 0, 0, 200); }"
        )
        self._example_image_button.clicked.connect(self._on_load_example_image)
        self._example_image_button.setVisible(False)
        # Move to leftmost position
        button_layout.insertWidget(0, self._example_image_button)

        # JSON export button
        self._download_json_button = QPushButton()
        json_icon_path = Path(__file__).resolve().parent / "assets" / "json-icon.svg"
        if json_icon_path.exists():
            self._download_json_button.setIcon(QIcon(str(json_icon_path)))
            self._download_json_button.setIconSize(QSize(24, 24))
        else:
            self._download_json_button.setText("{ }")
        self._download_json_button.setMaximumSize(40, 40)
        self._download_json_button.setStyleSheet(
            "QPushButton { "
            "  background-color: rgba(0, 0, 0, 150); "
            "  border: none; "
            "  border-radius: 5px; "
            "  padding: 5px; "
            "} "
            "QPushButton:hover { background-color: rgba(0, 0, 0, 200); }"
        )
        self._download_json_button.clicked.connect(self._on_download_json)
        self._download_json_button.setVisible(False)  # Only show if data is set
        button_layout.addWidget(self._download_json_button)

        # CSV export button
        self._download_csv_button = QPushButton()
        csv_icon_path = Path(__file__).resolve().parent / "assets" / "csv-icon.svg"
        if csv_icon_path.exists():
            self._download_csv_button.setIcon(QIcon(str(csv_icon_path)))
            self._download_csv_button.setIconSize(QSize(24, 24))
        else:
            self._download_csv_button.setText("CSV")
        self._download_csv_button.setMaximumSize(40, 40)
        self._download_csv_button.setStyleSheet(
            "QPushButton { "
            "  background-color: rgba(0, 0, 0, 150); "
            "  border: none; "
            "  border-radius: 5px; "
            "  padding: 5px; "
            "} "
            "QPushButton:hover { background-color: rgba(0, 0, 0, 200); }"
        )
        self._download_csv_button.clicked.connect(self._on_download_csv)
        self._download_csv_button.setVisible(False)  # Only show if data is set and csv_export is True
        button_layout.addWidget(self._download_csv_button)

        # Download button - overlaid in top right corner
        self._download_button = QPushButton()
        save_icon_path = Path(__file__).resolve().parent / "assets" / "save-icon.svg"
        if save_icon_path.exists():
            self._download_button.setIcon(QIcon(str(save_icon_path)))
            self._download_button.setIconSize(QSize(24, 24))
        else:
            self._download_button.setIcon(QIcon.fromTheme("document-save"))
        self._download_button.setMaximumSize(40, 40)
        self._download_button.setStyleSheet(
            "QPushButton { "
            "  background-color: rgba(0, 0, 0, 150); "
            "  border: none; "
            "  border-radius: 5px; "
            "  padding: 5px; "
            "} "
            "QPushButton:hover { background-color: rgba(0, 0, 0, 200); }"
        )
        self._download_button.clicked.connect(self._on_download)
        button_layout.addWidget(self._download_button)

        layout.addWidget(button_container, 0, 0, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        self._image = None
        self._data = None
        self._data_name = "Data"
        self.set_image(EMPTY_IMAGE)

    def set_image(self, image: Image.Image) -> None:
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
        self._image_label.setPixmap(pixmap, auto_fit=True)
        # Center scrollbars to middle after image is set
        hbar = self._scroll_area.horizontalScrollBar()
        vbar = self._scroll_area.verticalScrollBar()
        if hbar.maximum() > 0:
            hbar.setValue(hbar.maximum() // 2)
        if vbar.maximum() > 0:
            vbar.setValue(vbar.maximum() // 2)
    
    def set_image_buffer(self, image: NDArray[np.uint8]):
        self.set_image(Image.fromarray(image))
    
    def set_data(self, data: dict | list, data_name: str = "Data") -> None:
        """Attach JSON/CSV-exportable data to this widget.

        When ``csv_export`` is True, ``data`` should be a
        ``list[dict[str, JSON-compatible]]`` so it can be written as rows.
        """
        self._data = data
        self._data_name = data_name
        self._download_json_button.setVisible(True)
        if self.csv_export:
            self._download_csv_button.setVisible(True)

    # No need for _scale_image_to_fit or resizeEvent: handled by _ZoomableImageLabel

    def get_image(self) -> Image.Image | None:
        if (self._image is None) or (self._image is EMPTY_IMAGE):
            return None
        else:
            return self._image
    
    def zoom_in(self):
        self._image_label.set_zoom(self._image_label.get_zoom() * 1.25)

    def zoom_out(self):
        self._image_label.set_zoom(self._image_label.get_zoom() * 0.8)

    def reset_zoom(self):
        self._image_label.set_zoom(1.0)
    
    def get_image_buffer(self) -> NDArray[np.uint8] | None:
        image = self.get_image()
        if image is None:
            return None
        return np.array(image.convert("RGBA"), dtype=np.uint8)
    
    def get_data(self) -> dict | list | None:
        return self._data
    
    def _on_download(self) -> None:
        """Save the current image to a file."""
        image = self.get_image()
        if image is None:
            return
        
        Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {self.name}",
            f"{self.name}.png",
            "PNG Images (*.png);;JPEG Images (*.jpg);;BMP Images (*.bmp)"
        )
        path_lower = path.lower()
        if path and not(path_lower.endswith(".png") or path_lower.endswith(".jpg") or path_lower.endswith(".bmp")):
            path += ".png"
        if path:
            image.save(path)
    
    def _on_download_json(self) -> None:
        """Save the current data as JSON."""
        if self._data is None:
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {self._data_name}",
            f"{self._data_name}.json",
            "JSON Files (*.json)"
        )
        if path:
            export_to_json(self._data, path)
    
    def _on_download_csv(self) -> None:
        """Save the current data as CSV."""
        if self._data is None or not isinstance(self._data, list):
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {self._data_name}",
            f"{self._data_name}.csv",
            "CSV Files (*.csv)"
        )
        if path and (not path.lower().endswith(".csv")):
            path += ".csv"
        if path and len(self._data) > 0:
            export_to_csv(self._data, path)

    def _on_load_example_image(self) -> None:
        if self.example_image_path:
            try:
                img = Image.open(self.example_image_path)
                self.set_image(img)
            except Exception as e:
                print(f"Failed to load example image: {e}")

    def import_image(self) -> bool:
        Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Import {self.name}",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if not path:
            return False

        imported_image = Image.open(path)
        self.set_image(imported_image)
        return True
