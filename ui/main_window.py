import config
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QProgressBar, QTabWidget
from logic.province_generator import generate_province_map
from logic.import_module import import_image
from logic.export_module import export_image, export_provinces_csv
from ui.buttons import create_slider, create_button
from ui.image_display import ImageDisplay


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        # MAIN LAYOUT
        self.setWindowTitle(config.TITLE)
        self.resize(config.WINDOW_SIZE_WIDTH,
                    config.WINDOW_SIZE_HEIGHT)
        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, stretch=1)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        main_layout.addWidget(self.progress)

        # TAB1 LAND IMAGE
        self.land_tab = QWidget()
        self.land_image_display = ImageDisplay()
        land_tab_layout = QVBoxLayout(self.land_tab)
        land_tab_layout.addWidget(self.land_image_display)
        self.tabs.addTab(self.land_tab, "Land Image")

        # Buttons
        create_button(land_tab_layout,
                      "Import Land Image",
                      lambda: import_image(self,
                                           "Import Land Image",
                                           self.land_image_display))

        # TAB2 BOUNDARY IMAGE
        self.boundary_tab = QWidget()
        self.boundary_image_display = ImageDisplay()
        boundary_tab_layout = QVBoxLayout(self.boundary_tab)
        boundary_tab_layout.addWidget(self.boundary_image_display)
        self.tabs.addTab(self.boundary_tab, "Boundary Image")

        # Buttons
        create_button(boundary_tab_layout,
                      "Import Boundary Image",
                      lambda: import_image(self,
                                           "Import Boundary Image",
                                           self.boundary_image_display))

        # TAB3 PROVINCE IMAGE
        self.province_tab = QWidget()
        self.province_image_display = ImageDisplay()
        province_tab_layout = QVBoxLayout(self.province_tab)
        province_tab_layout.addWidget(self.province_image_display)
        self.tabs.addTab(self.province_tab, "Province Image")
        button_row = QHBoxLayout()
        province_tab_layout.addLayout(button_row)

        # Buttons
        self.land_slider = create_slider(province_tab_layout,
                                         "Land province density:",
                                         config.LAND_PROVINCES_MIN,
                                         config.LAND_PROVINCES_MAX,
                                         config.LAND_PROVINCES_DEFAULT,
                                         config.LAND_PROVINCES_TICK,
                                         config.LAND_PROVINCES_STEP)

        self.ocean_slider = create_slider(province_tab_layout,
                                          "Ocean province density",
                                          config.OCEAN_PROVINCES_MIN,
                                          config.OCEAN_PROVINCES_MAX,
                                          config.OCEAN_PROVINCES_DEFAULT,
                                          config.OCEAN_PROVINCES_TICK,
                                          config.OCEAN_PROVINCES_STEP)

        create_button(province_tab_layout,
                      "Generate Provinces",
                      lambda: generate_province_map(self))

        create_button(button_row,
                      "Export Province Map",
                      lambda: export_image(self,
                                           self.province_image_display.get_image(),
                                           "Export Province Map"))

        create_button(button_row,
                      "Export Province CSV",
                      lambda: export_provinces_csv(self))
