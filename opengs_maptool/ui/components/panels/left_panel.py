from __future__ import annotations
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from opengs_maptool.ui.main_window import MainWindow

from PyQt6 import sip
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFormLayout, QGroupBox, QLineEdit, QPushButton,
    QScrollArea, QStackedWidget, QVBoxLayout, QWidget
)

import opengs_maptool.config as config
from opengs_maptool.context import ApplicationContext
from opengs_maptool.controllers.project_controller import ProjectAttribute
from opengs_maptool.controllers.progress_controller import ProgressController
from opengs_maptool.controllers.task_controller import ThreadTaskSlot
import opengs_maptool.logic.datastructure as ds
from opengs_maptool.logic.density_generator import (
    equator_density_image, normalize_density_image, remove_density_image
)
from opengs_maptool.logic.export_module import (
    export_image, export_territory_definitions, export_territory_history,
    export_province_definitions, ExportFormat
)
from opengs_maptool.logic.land_actions import get_land_informations
from opengs_maptool.logic.territory_generator import generate_territory_map
from opengs_maptool.logic.province_generator import generate_province_map
from opengs_maptool.models.project import Project
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
        # Density readouts on the cached Land page, refreshed when it is shown.
        self._land_density_fields: list[QLineEdit] = []
        self._land_color_buttons: dict[ProjectAttribute, ColorPickerButton] = {}
        self._project_checkboxes: dict[ProjectAttribute, Any] = {}
        self._export_buttons_by_attribute: dict[ProjectAttribute, list[QPushButton]] = {}

        self.setMinimumWidth(280)
        self._layout = QVBoxLayout(self)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._page_stack = QStackedWidget(self._content_widget)
        self._content_layout.addWidget(self._page_stack)
        self._tab_pages: dict[TabName, QWidget] = {}
        self._tab_page_layouts: dict[TabName, QVBoxLayout] = {}
        self._tab_import_buttons: dict[TabName, list[QPushButton]] = {}
        self._generation_slider_widgets: dict[TabName, QWidget] = {}
        self._generation_sliders = {}

        self._scroll.setWidget(self._content_widget)
        self._layout.addWidget(self._scroll)
        self._create_generation_sliders()

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

        # Prepare Context
        self._context.task_controller.thread_task_slot_occupied.connect(self._on_thread_slot_occupied)
        self._context.task_controller.thread_task_slot_freed.connect(self._on_thread_slot_freed)
        self._context.project_controller.project_was_modified.connect(self._on_project_modification)

    def _create_generation_sliders(self) -> None:
        slider_specs = (
            (
                TabName.TERRITORY,
                ProjectAttribute.land_territory_density,
                "Land Territory Density:",
                config.LAND_TERRITORIES_MIN,
                config.LAND_TERRITORIES_MAX,
                config.LAND_TERRITORIES_TICK,
                config.LAND_TERRITORIES_STEP,
                self._context.project_controller.set_land_territory_density,
                None,
            ),
            (
                TabName.TERRITORY,
                ProjectAttribute.oceanic_territory_density,
                "Oceanic Territory Density:",
                config.OCEAN_TERRITORIES_MIN,
                config.OCEAN_TERRITORIES_MAX,
                config.OCEAN_TERRITORIES_TICK,
                config.OCEAN_TERRITORIES_STEP,
                self._context.project_controller.set_oceanic_territory_density,
                None,
            ),
            (
                TabName.TERRITORY,
                ProjectAttribute.territory_density_strength,
                "Density Strength:",
                config.DENSITY_STRENGTH_MIN,
                config.DENSITY_STRENGTH_MAX,
                config.DENSITY_STRENGTH_TICK,
                config.DENSITY_STRENGTH_STEP,
                self._context.project_controller.set_territory_density_strength,
                1 / config.DENSITY_STRENGTH_DIVISOR,
            ),
            (
                TabName.TERRITORY,
                ProjectAttribute.territory_jagged_land_amplitude,
                "Jagged Land Borders Strength:",
                config.JAGGED_BORDER_LAND_AMPLITUDE_MIN,
                config.JAGGED_BORDER_LAND_AMPLITUDE_MAX,
                config.JAGGED_BORDER_LAND_AMPLITUDE_TICK,
                config.JAGGED_BORDER_LAND_AMPLITUDE_STEP,
                self._context.project_controller.set_territory_jagged_land_amplitude,
                1 / config.JAGGED_BORDER_LAND_AMPLITUDE_DIVISOR,
            ),
            (
                TabName.TERRITORY,
                ProjectAttribute.territory_jagged_ocean_amplitude,
                "Jagged Ocean Borders Strength:",
                config.JAGGED_BORDER_OCEAN_AMPLITUDE_MIN,
                config.JAGGED_BORDER_OCEAN_AMPLITUDE_MAX,
                config.JAGGED_BORDER_OCEAN_AMPLITUDE_TICK,
                config.JAGGED_BORDER_OCEAN_AMPLITUDE_STEP,
                self._context.project_controller.set_territory_jagged_ocean_amplitude,
                1 / config.JAGGED_BORDER_OCEAN_AMPLITUDE_DIVISOR,
            ),
            (
                TabName.PROVINCE,
                ProjectAttribute.land_province_density,
                "Land province Density:",
                config.LAND_PROVINCES_MIN,
                config.LAND_PROVINCES_MAX,
                config.LAND_PROVINCES_TICK,
                config.LAND_PROVINCES_STEP,
                self._context.project_controller.set_land_province_density,
                None,
            ),
            (
                TabName.PROVINCE,
                ProjectAttribute.oceanic_province_density,
                "Oceanic province Density",
                config.OCEAN_PROVINCES_MIN,
                config.OCEAN_PROVINCES_MAX,
                config.OCEAN_PROVINCES_TICK,
                config.OCEAN_PROVINCES_STEP,
                self._context.project_controller.set_oceanic_province_density,
                None,
            ),
            (
                TabName.PROVINCE,
                ProjectAttribute.province_density_strength,
                "Density Strength:",
                config.DENSITY_STRENGTH_MIN,
                config.DENSITY_STRENGTH_MAX,
                config.DENSITY_STRENGTH_TICK,
                config.DENSITY_STRENGTH_STEP,
                self._context.project_controller.set_province_density_strength,
                1 / config.DENSITY_STRENGTH_DIVISOR,
            ),
            (
                TabName.PROVINCE,
                ProjectAttribute.province_jagged_land_amplitude,
                "Jagged Land Borders Strength:",
                config.JAGGED_BORDER_LAND_AMPLITUDE_MIN,
                config.JAGGED_BORDER_LAND_AMPLITUDE_MAX,
                config.JAGGED_BORDER_LAND_AMPLITUDE_TICK,
                config.JAGGED_BORDER_LAND_AMPLITUDE_STEP,
                self._context.project_controller.set_province_jagged_land_amplitude,
                1 / config.JAGGED_BORDER_LAND_AMPLITUDE_DIVISOR,
            ),
            (
                TabName.PROVINCE,
                ProjectAttribute.province_jagged_ocean_amplitude,
                "Jagged Ocean Borders Strength:",
                config.JAGGED_BORDER_OCEAN_AMPLITUDE_MIN,
                config.JAGGED_BORDER_OCEAN_AMPLITUDE_MAX,
                config.JAGGED_BORDER_OCEAN_AMPLITUDE_TICK,
                config.JAGGED_BORDER_OCEAN_AMPLITUDE_STEP,
                self._context.project_controller.set_province_jagged_ocean_amplitude,
                1 / config.JAGGED_BORDER_OCEAN_AMPLITUDE_DIVISOR,
            ),
        )

        for tab_name in (TabName.TERRITORY, TabName.PROVINCE):
            slider_widget = QWidget()
            slider_layout = QVBoxLayout(slider_widget)
            slider_layout.setContentsMargins(0, 0, 0, 0)
            self._generation_slider_widgets[tab_name] = slider_widget

        for (
            tab_name, attribute, label, minimum, maximum, tick_interval, step,
            setter, display_scale,
        ) in slider_specs:
            slider = create_slider(
                self._generation_slider_widgets[tab_name].layout(),
                label,
                minimum,
                maximum,
                getattr(self._context.project, attribute.name),
                tick_interval,
                step,
                setter,
                display_scale=display_scale,
            )
            self._generation_sliders[attribute] = slider

    def _update_generation_slider(self, attribute: ProjectAttribute) -> None:
        slider = self._generation_sliders.get(attribute)
        if slider is None:
            return

        value = getattr(self._context.project, attribute.name)
        if slider.value() != value:
            slider.setValue(value)

    def _on_thread_slot_occupied(self, slot: ThreadTaskSlot) -> None:
        self._on_thread_slot_updated(slot)

    def _on_thread_slot_freed(self, slot: ThreadTaskSlot) -> None:
        self._on_thread_slot_updated(slot)

    def _on_thread_slot_updated(self, slot: ThreadTaskSlot) -> None:
        # Any slot change can affect the tab on screen, not just the tab that
        # owns the slot: guardrails reach across tabs.
        self._refresh_button_states()

    def _refresh_button_states(self) -> None:
        """Re-apply the enabled state of every button on the current tab."""
        match self._current_tab_name:
            case TabName.DENSITY:
                self._update_density_buttons_state()
            case TabName.TERRITORY:
                self._update_territory_buttons_state()
            case TabName.PROVINCE:
                self._update_province_buttons_state()

        is_locked = self._context.project.is_generation_locked(self._context)
        for button in self._import_buttons:
            if not sip.isdeleted(button):
                button.setEnabled(not is_locked)

    def _update_density_buttons_state(self) -> None:
        if sip.isdeleted(self.btn_remove_density_image): # one suffices
            return # only do this if the tab is still active and the button exists

        project = self._context.project
        # The density image is an input to both generators, so editing it is
        # locked while either one runs.
        is_slot_free = (
            not self._context.task_controller.is_thread_slot_occupied(ThreadTaskSlot.change_density_image)
        )

        self.btn_remove_density_image.setEnabled(is_slot_free and project.can_density_image_be_removed(self._context))
        self.btn_normalize_density.setEnabled(is_slot_free and project.can_density_image_be_generated(self._context))
        self.btn_equator_distribution.setEnabled(is_slot_free and project.can_density_image_be_generated(self._context))

    def _update_territory_buttons_state(self) -> None:
        if sip.isdeleted(self.btn_generate_territories):
            return # only do this if the tab is still active and the button exists
        is_free = (
            not self._context.task_controller.is_thread_slot_occupied(ThreadTaskSlot.generate_territory_map)
        )
        self.btn_generate_territories.setEnabled(
            is_free and self._context.project.can_territory_image_be_generated(self._context, ignore_locked=False)
        )

    def _update_province_buttons_state(self) -> None:
        if sip.isdeleted(self.btn_generate_provinces):
            return # only do this if the tab is still active and the button exists
        is_free = (
            not self._context.task_controller.is_thread_slot_occupied(ThreadTaskSlot.generate_province_map)
        )
        self.btn_generate_provinces.setEnabled(
            is_free and self._context.project.can_province_image_be_generated(self._context, ignore_locked=False)
        )

    def display_content(self, tab_name: TabName):
        self._current_tab_name = tab_name
        page = self._tab_pages.get(tab_name)
        if page is None:
            self._import_buttons = []
            page = QWidget()
            self._content_layout = QVBoxLayout(page)
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
            self._page_stack.addWidget(page)
            self._tab_pages[tab_name] = page
            self._tab_page_layouts[tab_name] = self._content_layout
            self._tab_import_buttons[tab_name] = self._import_buttons
        else:
            self._content_layout = self._tab_page_layouts[tab_name]
            self._import_buttons = self._tab_import_buttons[tab_name]

        self._page_stack.setCurrentWidget(page)
        if tab_name == TabName.LAND:
            self._refresh_land_informations()
        self._refresh_button_states()

    def _create_import_button(self, parent_layout, label_text: str, callback) -> QPushButton:
        """Create an image import button that guardrails can disable."""
        button = create_button(parent_layout, label_text, callback)
        self._import_buttons.append(button)
        return button

    def _register_export_button(
        self, attribute: ProjectAttribute, button: QPushButton
    ) -> None:
        self._export_buttons_by_attribute.setdefault(attribute, []).append(button)
        button.setEnabled(getattr(self._context.project, attribute.name) is not None)

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

        # Densities are read straight off the configured colors, so they are
        # kept as fields and refreshed whenever one of those colors changes.
        for label in ("Land density:", "Ocean density:", "Lake density:"):
            field = QLineEdit()
            field.setReadOnly(True)
            infos_layout.addRow(label, field)
            self._land_density_fields.append(field)

        infos_group.setLayout(infos_layout)
        self._content_layout.addWidget(infos_group)

        # Land settings group
        settings_group = QGroupBox("Settings")
        settings_layout = QFormLayout()

        land_color_btn = ColorPickerButton(
            self._context.project.land_color, self, "Land Color")
        land_color_btn.colorChanged.connect(self._update_land_color)
        self._land_color_buttons[ProjectAttribute.land_color] = land_color_btn
        settings_layout.addRow("Land color:", land_color_btn)

        ocean_color_btn = ColorPickerButton(
            self._context.project.ocean_color, self, "Ocean Color")
        ocean_color_btn.colorChanged.connect(self._update_ocean_color)
        self._land_color_buttons[ProjectAttribute.ocean_color] = ocean_color_btn
        settings_layout.addRow("Ocean color:", ocean_color_btn)

        lake_color_btn = ColorPickerButton(
            self._context.project.lake_color, self, "Lake Color")
        lake_color_btn.colorChanged.connect(self._update_lake_color)
        self._land_color_buttons[ProjectAttribute.lake_color] = lake_color_btn
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
                normalize_density_image,
                "Normalizing Density Image",
                ThreadTaskSlot.change_density_image,
            ),
        )

        # Equator distribution button
        self.btn_equator_distribution = create_button(
            actions_layout,
            "Equator Distribution",
            lambda: self._execute_function_in_thread(
                equator_density_image,
                "Setting Density Image to Equator Distribution",
                ThreadTaskSlot.change_density_image,
            ),
        )
        self._update_density_buttons_state()

        # Territory exclude ocean checkbox
        checkbox_territory_exclude_ocean = create_checkbox(
            actions_layout, "Exclude Ocean Territories",
            lambda value: self._context.project_controller.set_territory_exclude_ocean(bool(value))
        )
        checkbox_territory_exclude_ocean.setChecked(self._context.project.territory_exclude_ocean)
        self._project_checkboxes[ProjectAttribute.territory_exclude_ocean] = checkbox_territory_exclude_ocean

        # Province exclude ocean checkbox
        checkbox_province_exclude_ocean = create_checkbox(
            actions_layout, "Exclude Ocean Provinces",
            lambda value: self._context.project_controller.set_province_exclude_ocean(bool(value))
        )
        checkbox_province_exclude_ocean.setChecked(self._context.project.province_exclude_ocean)
        self._project_checkboxes[ProjectAttribute.province_exclude_ocean] = checkbox_province_exclude_ocean

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

        actions_layout.addWidget(self._generation_slider_widgets[TabName.TERRITORY])

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
                "Export Territory Image",
                self._context.project.territory_image,
                self._context.project.territory_data,
            )
        )
        self._register_export_button(ProjectAttribute.territory_image, btn_export_territory_image)

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
        self._register_export_button(ProjectAttribute.territory_data, btn_export_territory_definitions)

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
        self._register_export_button(ProjectAttribute.territory_data, btn_export_territory_history)

        actions_group.setLayout(actions_layout)
        self._content_layout.addWidget(actions_group)

    def _display_province_content(self):
        # Province actions group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()

        actions_layout.addWidget(self._generation_slider_widgets[TabName.PROVINCE])

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
                "Export Province Image",
                self._context.project.province_image,
                self._context.project.province_data,
            )
        )
        self._register_export_button(ProjectAttribute.province_image, btn_export_province_image)

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
        self._register_export_button(ProjectAttribute.province_data, btn_export_province_definitions)

        actions_group.setLayout(actions_layout)
        self._content_layout.addWidget(actions_group)

    def _show_error_modal_if_exception(self, exception: BaseException | None):
        if exception is not None:
            modal = ErrorModal(self, str(exception))
            modal.exec() # Force user to acknowledge the error before continuing

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

    def _export_image(self,
                title: str, image: ds.TerritoryImage|ds.ProvinceImage|None,
                data: list[ds.RegionMetadata]|None=None
            ) -> None:
        if not image:
            return
        path = pick_save_image(self, title)
        if not path:
            return

        export_image(path, image, data, raise_on_error=False)

    def _export_project_data(self, project, exporter_function: Callable[[Project, str, ExportFormat], None], title):
        path, fmt = pick_save_data(self, title)
        if (not path) or (not fmt):
            return

        exporter_function(project, path, fmt)

    def _on_project_modification(self, attribute: ProjectAttribute):
        self._update_generation_slider(attribute)

        color_button = self._land_color_buttons.get(attribute)
        if color_button is not None:
            color_button.set_color(getattr(self._context.project, attribute.name))

        checkbox = self._project_checkboxes.get(attribute)
        if checkbox is not None:
            was_blocked = checkbox.blockSignals(True)
            try:
                checkbox.setChecked(getattr(self._context.project, attribute.name))
            finally:
                checkbox.blockSignals(was_blocked)

        for button in self._export_buttons_by_attribute.get(attribute, []):
            # this only works if the attribute names match exactly
            button.setEnabled(getattr(self._context.project, attribute.name) is not None)

        if attribute in {
            ProjectAttribute.land_image,
            ProjectAttribute.land_color,
            ProjectAttribute.ocean_color,
            ProjectAttribute.lake_color,
        }:
            # update image displays
            self._refresh_tab_view(TabName.LAND) # update color pickers and land informations

        if attribute in {
            ProjectAttribute.boundary_image,
        }:
            # update image displays
            self._refresh_tab_view(TabName.BOUNDARY)

        if attribute in {
            ProjectAttribute.density_image,
            ProjectAttribute.territory_exclude_ocean,
            ProjectAttribute.province_exclude_ocean,
            # Density buttons are already updated on slot changes
        }:
            # update image displays
            self._refresh_tab_view(TabName.DENSITY) # update checkboxes

        if attribute in {
            ProjectAttribute.terrain_image,
        }:
            # update image displays
            self._refresh_tab_view(TabName.TERRAIN)

        if attribute in {
            ProjectAttribute.territory_image,
            ProjectAttribute.territory_data,
            ProjectAttribute.land_territory_density,
            ProjectAttribute.oceanic_territory_density,
            ProjectAttribute.territory_density_strength,
            ProjectAttribute.territory_jagged_land_amplitude,
            ProjectAttribute.territory_jagged_ocean_amplitude,
            # Generate Territories button are already updated on slot changes
        }:
            # update image displays
            self._refresh_tab_view(TabName.TERRITORY)

        if attribute in {
            ProjectAttribute.province_image,
            ProjectAttribute.province_data,
            ProjectAttribute.land_province_density,
            ProjectAttribute.oceanic_province_density,
            ProjectAttribute.province_density_strength,
            ProjectAttribute.province_jagged_land_amplitude,
            ProjectAttribute.province_jagged_ocean_amplitude,
        }:
            # update image displays
            self._refresh_tab_view(TabName.PROVINCE)

    def _update_land_color(self, color):
        self._context.project_controller.set_land_color(color) # Causes the above listener

    def _update_ocean_color(self, color):
        self._context.project_controller.set_ocean_color(color)

    def _update_lake_color(self, color):
        self._context.project_controller.set_lake_color(color)

    def _refresh_land_informations(self):
        """Recompute the land/ocean/lake densities shown on the land tab."""
        fields = self._land_density_fields
        if not fields or any(sip.isdeleted(field) for field in fields):
            return  # only do this if the tab is still active

        # One pass over the image for all three readouts.
        informations = get_land_informations(self._context.project)
        for field, percentage in zip(fields, informations):
            field.setText(f"{percentage:.2f}%")

    def _execute_function_in_thread(
            self,
            function: Callable[[ApplicationContext, ProgressController], Any],
            title: str, slot: ThreadTaskSlot,
        ) -> None:

        task = self._context.task_controller.start_task(
            function,
            title,
            slot,
            provide_progress_controller=True,
            pos_args=[],
            kw_args={
                "task_ctx": self._context,
            },
            # "progress_controller" is automatically added as a keyword argument
            before_start_callback=None,  # No additional setup needed before starting the task
        )

    def _refresh_tab_view(self, tab_name: TabName):
        self._main_window.update_all_image_displays()
        if self._current_tab_name == tab_name:
            self.display_content(tab_name)
