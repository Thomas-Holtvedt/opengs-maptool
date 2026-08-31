from __future__ import annotations
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from opengs_maptool.ui.main_window import MainWindow

from PyQt6 import sip
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFormLayout, QGroupBox, QLineEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget
)

from vcolorpicker import getColor

import opengs_maptool.config as config
from opengs_maptool.context import ApplicationContext, LimitedTaskContext
from opengs_maptool.controllers.progress_controller import ProgressController
from opengs_maptool.controllers.task_controller import ThreadTaskSlot
from opengs_maptool.logic.density_generator import (
    equator_density, normalize_density, remove_density_image
)
from opengs_maptool.logic.export_module import (
    export_image, export_territory_definitions, export_territory_history,
    export_province_definitions
)
from opengs_maptool.logic.land_actions import get_land_informations
from opengs_maptool.logic.territory_generator import generate_territory_map
from opengs_maptool.logic.province_generator import generate_province_map
from opengs_maptool.simple_types import TabName
from opengs_maptool.ui.buttons import (
    create_button, create_checkbox, create_slider, ColorPickerButton
)
from opengs_maptool.ui.file_dialogs import (
    pick_open_image, pick_save_data, pick_save_image
)
from opengs_maptool.ui.modals.error_modal import ErrorModal
from opengs_maptool.ui.notifications.notification_manager import NotificationManager


class LeftPanel(QWidget):
    def __init__(self, context: ApplicationContext, main_window: MainWindow):
        super().__init__()
        self._context = context
        self._main_window = main_window
        self._current_tab_name: TabName = TabName.LAND
        # Import buttons on the currently displayed tab, rebuilt on every tab
        # switch. Guardrails disable these while a map is generating.
        self._import_buttons: list[QPushButton] = []

        self.setMinimumWidth(280)
        self._layout = QVBoxLayout(self)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)

        self._scroll.setWidget(self._content_widget)
        self._layout.addWidget(self._scroll)

        # Toast Container for Notifications in Left Panel
        self.toast_container_layout = QVBoxLayout()
        self.toast_container_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
        self.toast_container_layout.setSpacing(6)

        self._layout.addLayout(self.toast_container_layout)

        # Initialize NotificationManager with task controller
        self.notification_manager = NotificationManager(
            main_window=self._main_window,
            task_controller=self._context.task_controller,
            toast_container_layout=self.toast_container_layout,
        )

        # Listen to context refresh requests; emissions from worker threads are
        # queued to this UI-thread receiver by Qt.
        self._context.events.refresh_tab_view_requested.connect(
            self._refresh_tab_view)

        # Prepare Context
        self._context.task_controller.thread_task_slot_occupied.connect(
            self._on_thread_slot_occupied)
        self._context.task_controller.thread_task_slot_freed.connect(
            self._on_thread_slot_freed)

    def _on_thread_slot_occupied(self, slot: ThreadTaskSlot) -> None:
        self._on_thread_slot_updated(slot)

    def _on_thread_slot_freed(self, slot: ThreadTaskSlot) -> None:
        self._on_thread_slot_updated(slot)

    def _on_thread_slot_updated(self, slot: ThreadTaskSlot) -> None:
        # Any slot change can affect the tab on screen, not just the tab that
        # owns the slot: guardrails reach across tabs.
        self._refresh_button_states()

    def _is_generation_locked(self) -> bool:
        """True while a territory or province map is being generated.

        Both count for either map, because they share the same input images.
        """
        if not config.GUARDRAILS:
            return False

        task_controller = self._context.task_controller
        return (
            task_controller.is_thread_slot_occupied(ThreadTaskSlot.generate_territory_map)
            or task_controller.is_thread_slot_occupied(ThreadTaskSlot.generate_province_map)
        )

    def _refresh_button_states(self) -> None:
        """Re-apply the enabled state of every button on the current tab."""
        match self._current_tab_name:
            case TabName.DENSITY:
                self._update_density_buttons_state()
            case TabName.TERRITORY:
                self._update_territory_buttons_state()
            case TabName.PROVINCE:
                self._update_province_buttons_state()

        is_locked = self._is_generation_locked()
        for button in self._import_buttons:
            if not sip.isdeleted(button):
                button.setEnabled(not is_locked)

    def _update_density_buttons_state(self) -> None:
        if sip.isdeleted(self.btn_remove_density_image):  # one suffices
            return  # only do this if the tab is still active and the button exists

        project = self._context.project
        # The density image is an input to both generators, so editing it is
        # locked while either one runs.
        is_slot_free = not self._context.task_controller.is_thread_slot_occupied(
            ThreadTaskSlot.change_density_image) and not self._is_generation_locked()

        self.btn_remove_density_image.setEnabled(
            is_slot_free and project.can_density_image_be_removed())
        self.btn_normalize_density.setEnabled(
            is_slot_free and project.can_density_image_be_generated())
        self.btn_equator_distribution.setEnabled(
            is_slot_free and project.can_density_image_be_generated())

    def _update_territory_buttons_state(self) -> None:
        if sip.isdeleted(self.btn_generate_territories):
            return  # only do this if the tab is still active and the button exists
        is_free = not self._context.task_controller.is_thread_slot_occupied(
            ThreadTaskSlot.generate_territory_map) and not self._is_generation_locked()
        self.btn_generate_territories.setEnabled(
            is_free and self._context.project.can_territory_image_be_generated()
        )

    def _update_province_buttons_state(self) -> None:
        if sip.isdeleted(self.btn_generate_provinces):
            return  # only do this if the tab is still active and the button exists
        is_free = not self._context.task_controller.is_thread_slot_occupied(
            ThreadTaskSlot.generate_province_map) and not self._is_generation_locked()
        self.btn_generate_provinces.setEnabled(
            is_free and self._context.project.can_province_image_be_generated()
        )

    def display_content(self, tab_name: TabName):
        self._current_tab_name = tab_name
        self._clear_content()

        match tab_name:
            case TabName.LAND:
                self._display_land_content()
            case TabName.BOUNDARY:
                self._display_boundary_content()
            case TabName.DENSITY:
                self._display_density_content()
            case TabName.TERRAIN:
                self._display_terrain_content()
            case TabName.TERRITORY:
                self._display_territory_content()
            case TabName.PROVINCE:
                self._display_province_content()

        self._content_layout.addStretch()
        self._refresh_button_states()

    def _clear_content(self):
        self._import_buttons.clear()
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _create_import_button(self, parent_layout, label_text: str, callback) -> QPushButton:
        """Create an image import button that guardrails can disable."""
        button = create_button(parent_layout, label_text, callback)
        self._import_buttons.append(button)
        return button

    def _display_land_content(self):
        # Land actions group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()

        # Import land image button
        self._create_import_button(
            actions_layout,
            "Import Land Image",
            self._import_land_image
        )

        actions_group.setLayout(actions_layout)
        self._content_layout.addWidget(actions_group)

        # Land informations group
        infos_group = QGroupBox("Informations")
        infos_layout = QFormLayout()

        # Land density info
        land_density = QLineEdit()
        land_density.setReadOnly(True)
        land_density.setText(
            f"{get_land_informations(self._context.project)[0]:.2f}%")
        infos_layout.addRow("Land density:", land_density)

        # Ocean density info
        ocean_density = QLineEdit()
        ocean_density.setReadOnly(True)
        ocean_density.setText(
            f"{get_land_informations(self._context.project)[1]:.2f}%")
        infos_layout.addRow("Ocean density:", ocean_density)

        # Lake density info
        lake_density = QLineEdit()
        lake_density.setReadOnly(True)
        lake_density.setText(
            f"{get_land_informations(self._context.project)[2]:.2f}%")
        infos_layout.addRow("Lake density:", lake_density)

        infos_group.setLayout(infos_layout)
        self._content_layout.addWidget(infos_group)

        # Land settings group
        settings_group = QGroupBox("Settings")
        settings_layout = QFormLayout()

        ocean_color_btn = ColorPickerButton(self._context.project.ocean_color, self)
        ocean_color_btn.colorChanged.connect(self._update_ocean_color)
        settings_layout.addRow("Ocean color:", ocean_color_btn)

        lake_color_btn = ColorPickerButton(self._context.project.lake_color, self)
        lake_color_btn.colorChanged.connect(self._update_lake_color)
        settings_layout.addRow("Lake color:", lake_color_btn)

        settings_group.setLayout(settings_layout)
        self._content_layout.addWidget(settings_group)

    def _display_boundary_content(self):
        # Boundary actions group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()

        # Import boundary image button
        self._create_import_button(
            actions_layout,
            "Import Boundary Image",
            self._import_boundary_image
        )

        actions_group.setLayout(actions_layout)
        self._content_layout.addWidget(actions_group)

    def _display_density_content(self):
        # Density actions group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()

        # Import density image button
        self._create_import_button(
            actions_layout,
            "Import Density Image",
            self._import_density_image
        )

        # Remove density image button
        self.btn_remove_density_image = create_button(
            actions_layout,
            "Remove Density Image",
            lambda: self._execute_function_in_thread(
                remove_density_image,
                "Removing Density Image",
                ThreadTaskSlot.change_density_image,
            ),
        )

        # Normalize density button
        self.btn_normalize_density = create_button(
            actions_layout,
            "Normalize Density",
            lambda: self._execute_function_in_thread(
                normalize_density,
                "Normalizing Density Image",
                ThreadTaskSlot.change_density_image,
            ),
        )

        # Equator distribution button
        self.btn_equator_distribution = create_button(
            actions_layout,
            "Equator Distribution",
            lambda: self._execute_function_in_thread(
                equator_density,
                "Setting Density Image to Equator Distribution",
                ThreadTaskSlot.change_density_image,
            ),
        )
        self._update_density_buttons_state()

        # Territory exclude ocean checkbox
        checkbox_territory_exclude_ocean = create_checkbox(
            actions_layout, "Exclude Ocean Territories",
            lambda value: setattr(self._context.project,
                                  'territory_exclude_ocean', bool(value))
        )
        checkbox_territory_exclude_ocean.setChecked(
            self._context.project.territory_exclude_ocean)

        # Province exclude ocean checkbox
        checkbox_province_exclude_ocean = create_checkbox(
            actions_layout, "Exclude Ocean Provinces",
            lambda value: setattr(self._context.project,
                                  'province_exclude_ocean', bool(value))
        )
        checkbox_province_exclude_ocean.setChecked(
            self._context.project.province_exclude_ocean)

        actions_group.setLayout(actions_layout)
        self._content_layout.addWidget(actions_group)

    def _display_terrain_content(self):
        # Terrain actions group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()

        # Import terrain image button
        self._create_import_button(
            actions_layout,
            "Import Terrain Image",
            self._import_terrain_image
        )

        actions_group.setLayout(actions_layout)
        self._content_layout.addWidget(actions_group)

    def _display_territory_content(self):
        # Territory actions group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()

        # Set land territory density slider
        slider_land_territory_density = create_slider(
            actions_layout,
            "Land Territory Density:",
            config.LAND_TERRITORIES_MIN,
            config.LAND_TERRITORIES_MAX,
            self._context.project.land_territory_density,
            config.LAND_TERRITORIES_TICK,
            config.LAND_TERRITORIES_STEP,
            lambda value: setattr(self._context.project,
                                  'land_territory_density', value)
        )

        # Set oceanic territory density slider
        slider_oceanic_territory_density = create_slider(
            actions_layout,
            "Oceanic Territory Density:",
            config.OCEAN_TERRITORIES_MIN,
            config.OCEAN_TERRITORIES_MAX,
            self._context.project.oceanic_territory_density,
            config.OCEAN_TERRITORIES_TICK,
            config.OCEAN_TERRITORIES_STEP,
            lambda value: setattr(self._context.project,
                                  'oceanic_territory_density', value)
        )

        # Set territory density strength slider
        slider_territory_density_strength = create_slider(
            actions_layout,
            "Density Strength:",
            config.DENSITY_STRENGTH_MIN,
            config.DENSITY_STRENGTH_MAX,
            self._context.project.territory_density_strength,
            config.DENSITY_STRENGTH_TICK,
            config.DENSITY_STRENGTH_STEP,
            lambda value: setattr(self._context.project,
                                  'territory_density_strength', value),
            display_scale=0.1
        )

        # Territory jagged land checkbox
        checkbox_territory_jagged_land = create_checkbox(
            actions_layout, "Jagged Land Borders",
            lambda value: setattr(self._context.project,
                                  'territory_jagged_land', bool(value))
        )
        checkbox_territory_jagged_land.setChecked(
            self._context.project.territory_jagged_land)

        # Territory jagged ocean checkbox
        checkbox_territory_jagged_ocean = create_checkbox(
            actions_layout, "Jagged Ocean Borders",
            lambda value: setattr(self._context.project,
                                  'territory_jagged_ocean', bool(value))
        )
        checkbox_territory_jagged_ocean.setChecked(
            self._context.project.territory_jagged_ocean)

        # Generate territories button
        self.btn_generate_territories = create_button(
            actions_layout,
            "Generate Territories",
            lambda: self._execute_function_in_thread(
                generate_territory_map,
                "Generating Territory Map",
                ThreadTaskSlot.generate_territory_map,
            ),
        )
        self._update_territory_buttons_state()

        # Export territory image button
        btn_export_territory_image = create_button(
            actions_layout,
            "Export Territory Image",
            lambda: self._export_image(
                self._context.project.territory_image, "Export Territory Image")
        )
        btn_export_territory_image.setEnabled(
            self._context.project.territory_image != None)

        # Export territory definitions button
        btn_export_territory_definitions = create_button(
            actions_layout,
            "Export Territory Definitions",
            lambda: self._export_project_data(
                self._context.project,
                export_territory_definitions,
                "Export Territory Definitions"
            )
        )
        btn_export_territory_definitions.setEnabled(
            self._context.project.territory_data != None)

        # Export territory history button
        btn_export_territory_history = create_button(
            actions_layout,
            "Export Territory History",
            lambda: self._export_project_data(
                self._context.project,
                export_territory_history,
                "Export Territory History"
            )
        )
        btn_export_territory_history.setEnabled(
            self._context.project.territory_data != None)

        actions_group.setLayout(actions_layout)
        self._content_layout.addWidget(actions_group)

    def _display_province_content(self):
        # Province actions group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()

        # Set land province density slider
        slider_land_province_density = create_slider(
            actions_layout,
            "Land province Density:",
            config.LAND_PROVINCES_MIN,
            config.LAND_PROVINCES_MAX,
            self._context.project.land_province_density,
            config.LAND_PROVINCES_TICK,
            config.LAND_PROVINCES_STEP,
            lambda value: setattr(self._context.project,
                                  'land_province_density', value)
        )

        # Set oceanic province density slider
        slider_oceanic_province_density = create_slider(
            actions_layout,
            "Oceanic province Density",
            config.OCEAN_PROVINCES_MIN,
            config.OCEAN_PROVINCES_MAX,
            self._context.project.oceanic_province_density,
            config.OCEAN_PROVINCES_TICK,
            config.OCEAN_PROVINCES_STEP,
            lambda value: setattr(self._context.project,
                                  'oceanic_province_density', value)
        )

        # Set province density strength slider
        slider_province_density_strength = create_slider(
            actions_layout,
            "Density Strength:",
            config.DENSITY_STRENGTH_MIN,
            config.DENSITY_STRENGTH_MAX,
            self._context.project.province_density_strength,
            config.DENSITY_STRENGTH_TICK,
            config.DENSITY_STRENGTH_STEP,
            lambda value: setattr(self._context.project,
                                  'province_density_strength', value),
            display_scale=0.1
        )

        # Province jagged land checkbox
        checkbox_province_jagged_land = create_checkbox(
            actions_layout, "Jagged Land Borders",
            lambda value: setattr(self._context.project,
                                  'province_jagged_land', bool(value))
        )
        checkbox_province_jagged_land.setChecked(
            self._context.project.province_jagged_land)

        # Province jagged ocean checkbox
        checkbox_province_jagged_ocean = create_checkbox(
            actions_layout, "Jagged Ocean Borders",
            lambda value: setattr(self._context.project,
                                  'province_jagged_ocean', bool(value))
        )
        checkbox_province_jagged_ocean.setChecked(
            self._context.project.province_jagged_ocean)

        # Generate provinces button

        self.btn_generate_provinces = create_button(
            actions_layout,
            "Generate Provinces",
            lambda: self._execute_function_in_thread(
                generate_province_map,
                "Generating Province Map",
                ThreadTaskSlot.generate_province_map,
            ),
        )
        self._update_province_buttons_state()

        # Export province image button
        btn_export_province_image = create_button(
            actions_layout,
            "Export Province Image",
            lambda: self._export_image(
                self._context.project.province_image, "Export Province Image")
        )
        btn_export_province_image.setEnabled(
            self._context.project.province_image != None)

        # Export province definitions button
        btn_export_province_definitions = create_button(
            actions_layout,
            "Export Province Definitions",
            lambda: self._export_project_data(
                self._context.project,
                export_province_definitions,
                "Export Province Definitions"
            )
        )
        btn_export_province_definitions.setEnabled(
            self._context.project.province_data != None)

        actions_group.setLayout(actions_layout)
        self._content_layout.addWidget(actions_group)

    def _show_error_modal_if_exception(self, exception: BaseException | None):
        if exception is not None:
            modal = ErrorModal(self, str(exception))
            modal.exec()  # Force user to acknowledge the error before continuing

    def _import_land_image(self) -> None:
        path = pick_open_image(self, "Import Land Image")
        if path:
            error = self._context.import_service.import_land_image(path)
            self._show_error_modal_if_exception(error)

    def _import_boundary_image(self):
        path = pick_open_image(self, "Import Boundary Image")
        if path:
            error = self._context.import_service.import_boundary_image(path)
            self._show_error_modal_if_exception(error)

    def _import_density_image(self):
        path = pick_open_image(self, "Import Density Image")
        if path:
            error = self._context.import_service.import_density_image(path)
            self._show_error_modal_if_exception(error)

    def _import_terrain_image(self):
        path = pick_open_image(self, "Import Terrain Image")
        if path:
            error = self._context.import_service.import_terrain_image(path)
            self._show_error_modal_if_exception(error)

    def _export_image(self, image, title):
        path = pick_save_image(self, title)
        if not path:
            return

        export_image(path, image)

    def _export_project_data(self, project, exporter_function, title):
        path, fmt = pick_save_data(self, title)
        if not path:
            return

        exporter_function(project, path, fmt)

    def _update_ocean_color(self, color):
        self._context.project.ocean_color = color

    def _update_lake_color(self, color):
        self._context.project.lake_color = color

    def _execute_function_in_thread(
        self,
        function: Callable[[LimitedTaskContext, ProgressController], Any],
        title: str, slot: ThreadTaskSlot,
    ) -> None:

        task = self._context.task_controller.start_task(
            function,
            title,
            slot,
            pos_args=[],
            kw_args={
                "task_ctx": LimitedTaskContext(self._context),
            },
            # "progress_controller" is automatically added as a keyword argument
        )

    def _refresh_tab_view(self, tab_name: TabName):
        self._main_window.update_all_image_displays()
        if self._current_tab_name == tab_name:
            # Without this check, the current tab would be filled
            # with the content of the tab that was asked to be refreshed
            self.display_content(tab_name)
