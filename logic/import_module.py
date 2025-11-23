from PIL import Image
from PyQt6.QtWidgets import QFileDialog


def import_image(layout, text, image_display):
    path, _ = QFileDialog.getOpenFileName(
        layout,
        text,
        "",
        "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
    )
    if not path:
        return

    imported_image = Image.open(path)
    image_display.set_image(imported_image)
