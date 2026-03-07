import config
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QProgressBar, QTabWidget, QLabel
from logic.province_generator import generate_province_map
from logic.territory_generator import generate_territory_map
from logic.import_module import import_image
from logic.export_module import (export_image, export_territory_definitions,
                                 export_territory_history,
                                 export_province_definitions)
from ui.buttons import create_slider, create_button
from ui.image_display import ImageDisplay


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        # MAIN LAYOUT
        self.setWindowTitle(config.TITLE)
        self.setMinimumSize(800, 600)
        self.resize(config.WINDOW_SIZE_WIDTH,
                    config.WINDOW_SIZE_HEIGHT)
        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, stretch=1)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        main_layout.addWidget(self.progress)
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        self.progress.setValue(0)

        self.label_version = QLabel("Version "+config.VERSION)
        main_layout.addWidget(self.label_version)

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

        # TAB3 TERRITORY IMAGE
        self.territory_tab = QWidget()
        self.territory_image_display = ImageDisplay()
        territory_tab_layout = QVBoxLayout(self.territory_tab)
        territory_tab_layout.addWidget(self.territory_image_display)
        self.tabs.addTab(self.territory_tab, "Territory Image")
        button_territory_row = QHBoxLayout()
        territory_tab_layout.addLayout(button_territory_row)

        # Buttons
        self.territory_land_slider = create_slider(territory_tab_layout,
                                                   "Territory Land Density:",
                                                   config.LAND_TERRITORIES_MIN,
                                                   config.LAND_TERRITORIES_MAX,
                                                   config.LAND_TERRITORIES_DEFAULT,
                                                   config.LAND_TERRITORIES_TICK,
                                                   config.LAND_TERRITORIES_STEP)

        self.territory_ocean_slider = create_slider(territory_tab_layout,
                                                    "Territory Ocean Density:",
                                                    config.OCEAN_TERRITORIES_MIN,
                                                    config.OCEAN_TERRITORIES_MAX,
                                                    config.OCEAN_TERRITORIES_DEFAULT,
                                                    config.OCEAN_TERRITORIES_TICK,
                                                    config.OCEAN_TERRITORIES_STEP)

        self.button_gen_territories = create_button(territory_tab_layout,
                                                    "Generate Territories",
                                                    lambda: generate_territory_map(self))
        self.button_gen_territories.setEnabled(False)

        self.button_exp_terr_img = create_button(button_territory_row,
                                                 "Export Territory Image",
                                                 lambda: export_image(self,
                                                                      self.territory_image_display.get_image(),
                                                                      "Export Territory Image"))
        self.button_exp_terr_img.setEnabled(False)

        self.button_exp_terr_def = create_button(button_territory_row,
                                                 "Export Territory Definitions",
                                                 lambda: export_territory_definitions(self))
        self.button_exp_terr_def.setEnabled(False)

        self.button_exp_terr_hist = create_button(button_territory_row,
                                                  "Export Territory History",
                                                  lambda: export_territory_history(self))
        self.button_exp_terr_hist.setEnabled(False)

        # TAB4 PROVINCE IMAGE
        self.province_tab = QWidget()
        self.province_image_display = ImageDisplay()
        province_tab_layout = QVBoxLayout(self.province_tab)
        province_tab_layout.addWidget(self.province_image_display)
        self.tabs.addTab(self.province_tab, "Province Image")
        button_row = QHBoxLayout()
        province_tab_layout.addLayout(button_row)

        # Buttons
        self.land_slider = create_slider(province_tab_layout,
                                         "Land province Density:",
                                         config.LAND_PROVINCES_MIN,
                                         config.LAND_PROVINCES_MAX,
                                         config.LAND_PROVINCES_DEFAULT,
                                         config.LAND_PROVINCES_TICK,
                                         config.LAND_PROVINCES_STEP)

        self.ocean_slider = create_slider(province_tab_layout,
                                          "Ocean province Density",
                                          config.OCEAN_PROVINCES_MIN,
                                          config.OCEAN_PROVINCES_MAX,
                                          config.OCEAN_PROVINCES_DEFAULT,
                                          config.OCEAN_PROVINCES_TICK,
                                          config.OCEAN_PROVINCES_STEP)

        self.button_gen_prov = create_button(province_tab_layout,
                                             "Generate Provinces",
                                             lambda: generate_province_map(self))
        self.button_gen_prov.setEnabled(False)

        self.button_exp_prov_img = create_button(button_row,
                                                 "Export Province Image",
                                                 lambda: export_image(self,
                                                                      self.province_image_display.get_image(),
                                                                      "Export Province Image"))
        self.button_exp_prov_img.setEnabled(False)

        self.button_exp_prov_def = create_button(button_row,
                                                  "Export Province Definitions",
                                                  lambda: export_province_definitions(self))
        self.button_exp_prov_def.setEnabled(False)

