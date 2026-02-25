import sys
from pathlib import Path
from PIL import Image
from PyQt6.QtWidgets import QApplication
from ui.maptool_window import MapToolWindow
from logic.maptool import MapTool

def main_automatic() -> None:
    import json

    # Default paths
    input_directory = Path(__file__).parent.parent / "examples" / "input"
    output_directory = Path(__file__).parent.parent / "examples" / "output"
    
    #boundary_image = np.array(Image.open(input_directory / "bound2_borders.png").convert("RGBA"))
    #boundary_image = normalize_area_density(boundary_image)
    #Image.fromarray(boundary_image).save(input_directory / "bound2_yellow.png")

    maptool = MapTool(
        land_image=Image.open(input_directory / "land2.png"),
        boundary_image=Image.open(input_directory / "bound2_density.png")
    )

    result = maptool.generate()
    result.cont_areas_image.save(output_directory / "cont_areas_image.png")
    result.class_image.save(output_directory / "class_image.png")
    result.territory_image.save(output_directory / "territory_image.png")
    result.province_image.save(output_directory / "province_image.png")
    (output_directory / "data.json").write_text(json.dumps(dict(
        cont_areas=result.cont_areas_data,
        class_counts=result.class_counts,
        territories=result.territory_data,
        provinces=result.province_data,
    )))

def main_gui() -> None:
    app = QApplication(sys.argv)
    window = MapToolWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    #main_automatic()
    main_gui()

