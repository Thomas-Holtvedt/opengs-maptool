import numpy as np
from numpy.typing import NDArray
from PIL import Image
from pathlib import Path
from logic.export_module import export_to_json, export_to_csv
from PyQt6.QtWidgets import QWidget, QGridLayout, QHBoxLayout, QLabel, QFileDialog, QPushButton
from PyQt6.QtGui import QPixmap, QImage, QIcon
from PyQt6.QtCore import Qt, QSize
import opengs_maptool.config as config


class ImageDisplay(QWidget):
    """Widget that displays an image with export controls.

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
        
        # Image label - spans entire grid
        self._image_label = QLabel()
        self._image_label.setMinimumSize(400, 300)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet("background-color: #333")
        self._image_label.setScaledContents(False)
        layout.addWidget(self._image_label, 0, 0)
        
        # Button container for top-right buttons
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(5, 5, 5, 0)
        button_layout.setSpacing(5)
        button_layout.addStretch()
        
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
        self._original_pixmap = None
        self._data = None
        self._data_name = "Data"

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
        self._original_pixmap = QPixmap.fromImage(qimage)
        self._scale_image_to_fit()
    
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

    def _scale_image_to_fit(self) -> None:
        if self._original_pixmap is None:
            return
        
        pixmap = self._original_pixmap.scaled(
            self._image_label.width(),
            self._image_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._image_label.setPixmap(pixmap)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._scale_image_to_fit()

    def get_image(self) -> Image.Image | None:
        return self._image
    
    def get_image_buffer(self) -> NDArray[np.uint8] | None:
        if self._image is None:
            return None
        return np.array(self._image.convert("RGBA"), dtype=np.uint8)
    
    def _on_download(self) -> None:
        """Save the current image to a file."""
        if self._image is None:
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
            self._image.save(path)
    
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
