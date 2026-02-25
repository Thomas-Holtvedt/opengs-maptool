from pathlib import Path
from PIL import Image
from typing import Callable
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QPushButton, QMessageBox, QSpinBox, QSizePolicy
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPainter, QColor
from logic.maptool import MapTool
from ui.buttons import create_slider, create_button
from ui.image_display import ImageDisplay
from ui.flappy_bird_game import FlappyBirdGame
import opengs_maptool.config as config


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


class BackgroundWorker(QThread):
    """Generalized worker thread for running tasks in the background with progress tracking."""
    finished = pyqtSignal(object)
    progress = pyqtSignal(int)
    error = pyqtSignal(Exception)
    
    def __init__(self, task: Callable, *args, **kwargs) -> None:
        """
        Initialize the background worker.
        
        Args:
            task: The function to run in the background. 
                  If the task needs progress tracking, it should accept a 'progress_callback' kwarg.
            *args: Positional arguments to pass to the task
            **kwargs: Keyword arguments to pass to the task
        """
        super().__init__()
        self.task = task
        self.args = args
        self.kwargs = kwargs
    
    def run(self) -> None:
        """Run the task in a background thread."""
        try:
            # Inject progress callback if task accepts it
            def progress_callback(current: int, total: int = 100) -> None:
                percentage = int((current / total) * 100) if total > 0 else current
                self.progress.emit(percentage)
            
            # Add progress_callback to kwargs if not already present
            if 'progress_callback' not in self.kwargs:
                self.kwargs['progress_callback'] = progress_callback
            
            result = self.task(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(e)


EXAMPLE_INPUT_DIR = Path(__file__).parent.parent / "examples" / "input"
EXAMPLE_BOUNDARY_ORIG_IMAGE = Image.open(EXAMPLE_INPUT_DIR / "bound2_orig.png")
EXAMPLE_LAND_IMAGE = Image.open(EXAMPLE_INPUT_DIR / "land2.png")
EMPTY_IMAGE = Image.new("RGB", EXAMPLE_BOUNDARY_ORIG_IMAGE.size, color=(100, 100, 100))

class MapToolWindow(QWidget):
    """
    Open Grand Strategy Map Tool, which can be used from a UI Window.
    """

    def __init__(self) -> None:
        super().__init__()
        # Initialize data storage
        self._cont_areas_image_buffer = None
        self._cont_areas_data = None
        self._class_image_buffer = None
        self._class_counts = None
        self._territory_image_buffer = None
        self._territory_data = None
        self._province_image_buffer = None
        self._province_data = None
        self.create_layout()
        self.showMaximized()
    

    def create_layout(self) -> None:
        # MAIN LAYOUT
        self.setWindowTitle(config.TITLE)
        self.setMinimumSize(800, 600)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, stretch=1)

        #self.progress = QProgressBar()
        #self.progress.setVisible(False)
        #main_layout.addWidget(self.progress)
        #self.progress.setMinimum(0)
        #self.progress.setMaximum(100)
        #self.progress.setValue(0)

        # Bottom bar with game button and version label
        bottom_layout = QHBoxLayout()
        self.button_flappy_bird = QPushButton("Play 🐦 While Waiting")
        self.button_flappy_bird.clicked.connect(self.on_button_play_flappy_bird)
        bottom_layout.addWidget(self.button_flappy_bird)
        bottom_layout.addStretch()
        self.label_version = QLabel("Version "+config.VERSION)
        bottom_layout.addWidget(self.label_version)
        main_layout.addLayout(bottom_layout)

        self.create_start_tab()
        self.tabs.addTab(self.readme_tab, "Getting Started")
        self.create_boundary_tab()
        self.tabs.addTab(self.boundary_tab, "Adapt Boundary Image")
        self.create_input_images_tab()
        self.tabs.addTab(self.land_tab, "Input Images")
        self.create_areas_tab()
        self.tabs.addTab(self.areas_tab, "Generate Areas")
        self.create_territory_tab()
        self.tabs.addTab(self.territory_tab, "Generate Territories")
        self.create_province_tab()
        self.tabs.addTab(self.province_tab, "Generate Provinces")

    def on_button_play_flappy_bird(self) -> None:
            """Open Flappy Bird game in a new window."""
            self.flappy_bird_window = FlappyBirdGame()
            self.flappy_bird_window.show()

    def create_start_tab(self) -> None:
        self.readme_tab = QWidget()
        start_layout = QVBoxLayout(self.readme_tab)
        self.readme_label = QLabel(
            '<h1>Please read the README</h1>'
            '<h2><a href="https://github.com/Thomas-Holtvedt/opengs-maptool/blob/main/README.md">'        
            'Open the README in your browser</a></h2>'
        )
        self.readme_label.setOpenExternalLinks(True)
        self.readme_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        start_layout.addWidget(self.readme_label)

    def create_boundary_tab(self) -> None:
        self.boundary_tab = QWidget()
        boundary_tab_layout = QVBoxLayout(self.boundary_tab)
        
        create_button(boundary_tab_layout, "Import Boundary Image", self.on_button_import_boundary)

        self.orig_boundary_image_display = ImageDisplay(name="Boundary Image")
        self.orig_boundary_image_display.set_image(EXAMPLE_BOUNDARY_ORIG_IMAGE)
        boundary_tab_layout.addWidget(self.orig_boundary_image_display, stretch=1)

        create_button(boundary_tab_layout,
            "Normalize Territory and Province Density",
            self.on_button_normalize_density,
        )
        
        self.normalized_boundary_image_display = ImageDisplay(name="Adapted Boundary Image")
        self.normalized_boundary_image_display.set_image(EMPTY_IMAGE)
        boundary_tab_layout.addWidget(self.normalized_boundary_image_display, stretch=1)

    def create_input_images_tab(self) -> None:
        self.land_tab = QWidget()
        land_tab_layout = QVBoxLayout(self.land_tab)

        boundary_button_row = QHBoxLayout()
        land_tab_layout.addLayout(boundary_button_row)
        create_button(boundary_button_row, "Import Final Boundary Image", self.on_button_import_final_boundary)
        create_button(boundary_button_row, "Keep Generated Boundary Image", self.on_button_keep_generated_boundary)
        
        self.final_boundary_image_display = ImageDisplay(name="Final Boundary Image")
        self.final_boundary_image_display.set_image(EMPTY_IMAGE)
        land_tab_layout.addWidget(self.final_boundary_image_display, stretch=1)

        self.button_import_land = ProgressButton("Import and Clean Land Image")
        self.button_import_land.clicked.connect(self.on_button_import_land)
        land_tab_layout.addWidget(self.button_import_land)

        self.land_image_display = ImageDisplay(name="Land Image")
        self.land_image_display.set_image(EMPTY_IMAGE)
        land_tab_layout.addWidget(self.land_image_display, stretch=1)

    def create_areas_tab(self) -> None:
        self.areas_tab = QWidget()
        areas_tab_layout = QVBoxLayout(self.areas_tab)

        self.cont_areas_rng_seed_input = self._create_seed_input(
            areas_tab_layout,
            "Continuous Areas RNG Seed:",
            int(1e6),
        )
        
        self.button_generate_areas = ProgressButton("Generate Continuous Areas")
        self.button_generate_areas.clicked.connect(self.on_button_generate_areas)
        areas_tab_layout.addWidget(self.button_generate_areas)

        self.areas_image_display = ImageDisplay(name="Continuous Areas Image", csv_export=True)
        self.areas_image_display.set_image(EMPTY_IMAGE)
        areas_tab_layout.addWidget(self.areas_image_display, stretch=1)

    def create_territory_tab(self) -> None:
        self.territory_tab = QWidget()
        territory_tab_layout = QVBoxLayout(self.territory_tab)

        self.territories_rng_seed_input = self._create_seed_input(
            territory_tab_layout,
            "Territories RNG Seed:",
            int(2e6),
        )

        # Buttons
        self.pixels_per_land_territory_slider = create_slider(territory_tab_layout,
            "Pixels per Land territory:",
            config.PIXELS_PER_LAND_TERRITORY_MIN,
            config.PIXELS_PER_LAND_TERRITORY_MAX,
            config.PIXELS_PER_LAND_TERRITORY_DEFAULT,
            config.PIXELS_PER_LAND_TERRITORY_TICK,
            config.PIXELS_PER_LAND_TERRITORY_STEP,
        )

        self.pixels_per_water_territory_slider = create_slider(territory_tab_layout,
            "Pixels per Water territory:",
            config.PIXELS_PER_WATER_TERRITORY_MIN,
            config.PIXELS_PER_WATER_TERRITORY_MAX,
            config.PIXELS_PER_WATER_TERRITORY_DEFAULT,
            config.PIXELS_PER_WATER_TERRITORY_TICK,
            config.PIXELS_PER_WATER_TERRITORY_STEP,
        )

        self.button_gen_territories = ProgressButton("Generate Territories")
        self.button_gen_territories.clicked.connect(self.on_button_generate_territories)
        territory_tab_layout.addWidget(self.button_gen_territories)

        self.territory_image_display = ImageDisplay(name="Territory Image", csv_export=True)
        self.territory_image_display.set_image(EMPTY_IMAGE)
        territory_tab_layout.addWidget(self.territory_image_display, stretch=1)

    def create_province_tab(self) -> None:
        self.province_tab = QWidget()
        province_tab_layout = QVBoxLayout(self.province_tab)

        self.provinces_rng_seed_input = self._create_seed_input(
            province_tab_layout,
            "Provinces RNG Seed:",
            int(3e6),
        )

        # Buttons
        self.pixels_per_land_province_slider = create_slider(province_tab_layout,
            "Pixels per Land province:",
            config.PIXELS_PER_LAND_PROVINCE_MIN,
            config.PIXELS_PER_LAND_PROVINCE_MAX,
            config.PIXELS_PER_LAND_PROVINCE_DEFAULT,
            config.PIXELS_PER_LAND_PROVINCE_TICK,
            config.PIXELS_PER_LAND_PROVINCE_STEP,
        )

        self.pixels_per_water_province_slider = create_slider(province_tab_layout,
            "Pixels per Water province:",
            config.PIXELS_PER_WATER_PROVINCE_MIN,
            config.PIXELS_PER_WATER_PROVINCE_MAX,
            config.PIXELS_PER_WATER_PROVINCE_DEFAULT,
            config.PIXELS_PER_WATER_PROVINCE_TICK,
            config.PIXELS_PER_WATER_PROVINCE_STEP,
        )

        self.button_gen_provinces = ProgressButton("Generate Provinces")
        self.button_gen_provinces.clicked.connect(self.on_button_generate_provinces)
        province_tab_layout.addWidget(self.button_gen_provinces)
    
        self.province_image_display = ImageDisplay(name="Province Image", csv_export=True)
        self.province_image_display.set_image(EMPTY_IMAGE)
        province_tab_layout.addWidget(self.province_image_display, stretch=1)

    # TAB 2
    def on_button_import_boundary(self) -> None:
        self.orig_boundary_image_display.import_image()

    def on_button_normalize_density(self) -> None:
        image_buffer = self.orig_boundary_image_display.get_image_buffer()
        if image_buffer is not None:
            normalized_buffer = MapTool.normalize_boundary_area_density(image_buffer)
            self.normalized_boundary_image_display.set_image(Image.fromarray(normalized_buffer))

    # TAB 3
    def on_button_import_final_boundary(self) -> None:
        self.final_boundary_image_display.import_image()

    def on_button_keep_generated_boundary(self) -> None:
        self.final_boundary_image_display.set_image(self.normalized_boundary_image_display.get_image() or EMPTY_IMAGE)

    def on_button_import_land(self) -> None:
        self.land_image_display.import_image()

        def run_task(maptool: MapTool, progress_callback: Callable) -> tuple:
            self.button_import_land.set_progress(30)
            class_image, _, class_counts = maptool._generate_type_classification()
            return (class_image, class_counts)
        
        def on_progress(value: int) -> None:
            self.button_import_land.set_progress(value)
        
        def on_finished(result: tuple) -> None:
            self.button_import_land.reset_progress()
            self.button_import_land.setEnabled(True)
            class_image, class_counts = result
            self.land_image_display.set_image(class_image)
            self.land_image_display.set_data(class_counts, "Classification Counts")
        
        def on_error(error: Exception) -> None:
            self.button_import_land.reset_progress()
            self.button_import_land.setEnabled(True)
            QMessageBox.critical(self, "Error", f"Error processing land image: {error}")

        self.button_import_land.reset_progress()
        self.button_import_land.setEnabled(False)
        
        self.classify_worker = self._create_background_worker(run_task, on_progress, on_finished, on_error)

    # TAB 4
    def on_button_generate_areas(self) -> None:
        def run_task(maptool: MapTool, progress_callback: Callable) -> tuple:
            cont_areas_image, cont_areas_image_buffer, cont_areas_data = maptool._generate_cont_areas(progress_callback=progress_callback)
            return (cont_areas_image, cont_areas_image_buffer, cont_areas_data)
        
        def on_progress(value: int) -> None:
            self.button_generate_areas.set_progress(value)
        
        def on_finished(result: tuple) -> None:
            self.button_generate_areas.reset_progress()
            self.button_generate_areas.setEnabled(True)
            cont_areas_image, cont_areas_image_buffer, cont_areas_data = result
            self.areas_image_display.set_image(cont_areas_image)
            self.areas_image_display.set_data(cont_areas_data, "Continuous Area Data")
            # Store for later use in territory/province generation
            self._cont_areas_image_buffer = cont_areas_image_buffer
            self._cont_areas_data = cont_areas_data
            # Also generate type classification
            self._generate_type_classification()
        
        def on_error(error: Exception) -> None:
            self.button_generate_areas.reset_progress()
            self.button_generate_areas.setEnabled(True)
            QMessageBox.critical(self, "Error", f"Error generating areas: {error}")

        self.button_generate_areas.reset_progress()
        self.button_generate_areas.setEnabled(False)
        
        self.areas_worker = self._create_background_worker(run_task, on_progress, on_finished, on_error)
    
    def _generate_type_classification(self) -> None:
        maptool = self._create_maptool()
        _, self._class_image_buffer, self._class_counts = maptool._generate_type_classification()
    
    # TAB 5
    def on_button_generate_territories(self) -> None:
        if self._cont_areas_image_buffer is None:
            QMessageBox.warning(self, "Warning", "Continuous areas must be generated first")
            return
        
        def run_task(maptool: MapTool, progress_callback: Callable) -> tuple:
            territory_image, territory_image_buffer, territory_data = maptool._generate_territories(
                self._cont_areas_image_buffer,
                self._cont_areas_data,
                self._class_image_buffer,
                self._class_counts,
                progress_callback=progress_callback,
            )
            return (territory_image, territory_image_buffer, territory_data)
        
        def on_progress(value: int) -> None:
            self.button_gen_territories.set_progress(value)
        
        def on_finished(result: tuple) -> None:
            self.button_gen_territories.reset_progress()
            self.button_gen_territories.setEnabled(True)
            territory_image, territory_image_buffer, territory_data = result
            self.territory_image_display.set_image(territory_image)
            self.territory_image_display.set_data(territory_data, "Territory Data")
            # Store for later use in province generation
            self._territory_image_buffer = territory_image_buffer
            self._territory_data = territory_data
        
        def on_error(error: Exception) -> None:
            self.button_gen_territories.reset_progress()
            self.button_gen_territories.setEnabled(True)
            QMessageBox.critical(self, "Error", f"Error generating territories: {error}")

        self.button_gen_territories.reset_progress()
        self.button_gen_territories.setEnabled(False)
        
        self.territories_worker = self._create_background_worker(run_task, on_progress, on_finished, on_error)

    # TAB 6
    def on_button_generate_provinces(self) -> None:
        if self._territory_image_buffer is None:
            QMessageBox.warning(self, "Warning", "Territories must be generated first")
            return
        
        def run_task(maptool: MapTool, progress_callback: Callable) -> tuple:
            province_image, province_image_buffer, province_data = maptool._generate_provinces(
                self._territory_image_buffer,
                self._territory_data,
                self._class_image_buffer,
                self._class_counts,
                progress_callback=progress_callback,
            )
            return (province_image, province_image_buffer, province_data)
        
        def on_progress(value: int) -> None:
            self.button_gen_provinces.set_progress(value)
        
        def on_finished(result: tuple) -> None:
            self.button_gen_provinces.reset_progress()
            self.button_gen_provinces.setEnabled(True)
            province_image, province_image_buffer, province_data = result
            self.province_image_display.set_image(province_image)
            self.province_image_display.set_data(province_data, "Province Data")
            # Store for later use
            self._province_image = province_image
            self._province_image_buffer = province_image_buffer
            self._province_data = province_data
        
        def on_error(error: Exception) -> None:
            self.button_gen_provinces.reset_progress()
            self.button_gen_provinces.setEnabled(True)
            QMessageBox.critical(self, "Error", f"Error generating provinces: {error}")

        self.button_gen_provinces.reset_progress()
        self.button_gen_provinces.setEnabled(False)
        
        self.provinces_worker = self._create_background_worker(run_task, on_progress, on_finished, on_error)


    def _create_maptool(self) -> MapTool:
        return MapTool(
            land_image=self.land_image_display.get_image(),
            boundary_image=self.final_boundary_image_display.get_image(),
            pixels_per_land_territory=self.pixels_per_land_territory_slider.value(),
            pixels_per_water_territory=self.pixels_per_water_territory_slider.value(),
            pixels_per_land_province=self.pixels_per_land_province_slider.value(),
            pixels_per_water_province=self.pixels_per_water_province_slider.value(),
            cont_areas_rng_seed=self.cont_areas_rng_seed_input.value(),
            territories_rng_seed=self.territories_rng_seed_input.value(),
            provinces_rng_seed=self.provinces_rng_seed_input.value(),
        )

    def _create_seed_input(self, parent_layout: QVBoxLayout, label_text: str, default_value: int) -> QSpinBox:
        row = QHBoxLayout()
        parent_layout.addLayout(row)

        label = QLabel(label_text)
        row.addWidget(label)

        spinbox = QSpinBox()
        spinbox.setMinimum(0)
        spinbox.setMaximum(2_147_483_647)
        spinbox.setSingleStep(1)
        spinbox.setValue(default_value)
        row.addWidget(spinbox)

        return spinbox
    
    def _create_background_worker(self, run_task: Callable, on_progress: Callable, on_finished: Callable, on_error: Callable) -> BackgroundWorker:
        worker = BackgroundWorker(run_task, self._create_maptool())
        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.start()
        return worker

