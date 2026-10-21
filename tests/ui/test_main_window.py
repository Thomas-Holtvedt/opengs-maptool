import os

# Must be set before any QApplication is constructed.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from opengs_maptool.context import ApplicationContext
import pytest
from PyQt6.QtWidgets import QApplication, QGroupBox, QPushButton

from opengs_maptool.app import App
from opengs_maptool.controllers.project_controller import ProjectAttribute
from opengs_maptool.simple_types import TabName


@pytest.fixture(scope="module")
def app():
    existing = QApplication.instance()
    if existing is not None:
        yield existing
        return
    application = App()
    yield application


@pytest.fixture
def window(app):
    from opengs_maptool.ui.main_window import MainWindow
    return MainWindow(app)


def _labels(left_panel):
    current_page = left_panel._page_stack.currentWidget()
    return {
        button.text(): button.isEnabled()
        for button in current_page.findChildren(QPushButton)
    }


def test_left_panel_is_populated_for_the_initial_tab(window):
    """addTab() selects the first tab before currentChanged is connected."""
    left_panel = window._left_panel

    assert window._tabs.currentIndex() == 0
    assert left_panel._current_tab_name is TabName.LAND
    land_page = left_panel._tab_pages[TabName.LAND]
    assert land_page.layout().count() > 0, "left panel is blank on startup"
    assert all(
        slider_widget.parentWidget() is None
        for slider_widget in left_panel._generation_slider_widgets.values()
    )

    assert "Import Land Image" in _labels(left_panel)


def test_switching_tabs_displays_cached_left_panel_content(window):
    left_panel = window._left_panel

    window._tabs.setCurrentIndex(window._tab_names_by_index.index(TabName.DENSITY))
    assert left_panel._current_tab_name is TabName.DENSITY
    density_page = left_panel._tab_pages[TabName.DENSITY]
    labels = _labels(left_panel)
    assert "Equator Distribution" in labels

    window._tabs.setCurrentIndex(window._tab_names_by_index.index(TabName.LAND))
    assert left_panel._current_tab_name is TabName.LAND
    land_page = left_panel._tab_pages[TabName.LAND]
    assert land_page.layout().count() > 0
    assert any(g.title() == "Informations" for g in land_page.findChildren(QGroupBox))

    window._tabs.setCurrentIndex(window._tab_names_by_index.index(TabName.DENSITY))
    assert left_panel._tab_pages[TabName.DENSITY] is density_page
    assert left_panel._page_stack.currentWidget() is density_page


def test_generation_sliders_survive_refresh_and_sync_only_changed_attribute(window):
    left_panel = window._left_panel
    window._tabs.setCurrentIndex(window._tab_names_by_index.index(TabName.TERRITORY))

    attribute = ProjectAttribute.land_territory_density
    slider = left_panel._generation_sliders[attribute]
    value_before = slider.value()

    window._context.project_controller.project_was_modified.emit(attribute)
    assert left_panel._generation_sliders[attribute] is slider
    assert slider.value() == value_before

    changed_value = value_before + 1 if value_before < slider.maximum() else value_before - 1
    controller = window._context.project_controller
    try:
        controller.set_land_territory_density(changed_value)

        assert left_panel._generation_sliders[attribute] is slider
        assert slider.value() == changed_value
    finally:
        controller.set_land_territory_density(value_before)


def test_cached_controls_follow_project_attribute_changes(window):
    left_panel = window._left_panel
    controller = window._context.project_controller
    project = window._context.project

    color_attribute = ProjectAttribute.land_color
    window._tabs.setCurrentIndex(window._tab_names_by_index.index(TabName.LAND))
    color_button = left_panel._land_color_buttons[color_attribute]
    original_color = project.land_color
    changed_color = tuple((channel + 1) % 256 for channel in original_color)
    try:
        controller.set_land_color(changed_color)
        assert color_button.color() == changed_color
    finally:
        controller.set_land_color(original_color)

    checkbox_attribute = ProjectAttribute.territory_exclude_ocean
    window._tabs.setCurrentIndex(window._tab_names_by_index.index(TabName.DENSITY))
    checkbox = left_panel._project_checkboxes[checkbox_attribute]
    original_checkbox_value = project.territory_exclude_ocean
    try:
        controller.set_territory_exclude_ocean(not original_checkbox_value)
        assert checkbox.isChecked() is not original_checkbox_value
    finally:
        controller.set_territory_exclude_ocean(original_checkbox_value)

    window._tabs.setCurrentIndex(window._tab_names_by_index.index(TabName.TERRITORY))
    data_buttons = left_panel._export_buttons_by_attribute[ProjectAttribute.territory_data]
    original_data = project.territory_data
    try:
        controller.set_territory_data([])
        assert all(button.isEnabled() for button in data_buttons)
    finally:
        controller.set_territory_data(original_data)


class _StuckThreadPool:
    """Starts nothing, so the slot stays occupied for the duration of a test."""
    def start(self, runnable):
        return


@pytest.fixture
def occupied_generation_slot(monkeypatch):
    """Hold a generation slot open without running anything."""
    from opengs_maptool.controllers import task_controller as tc_module

    monkeypatch.setattr(
        tc_module.QThreadPool, 'globalInstance', staticmethod(lambda: _StuckThreadPool())
    )

    occupied = []

    def occupy(window, slot):
        context: ApplicationContext = window._context
        occupied.append((context.task_controller, slot))
        return context.task_controller.start_task(
            lambda progress_controller: None,
            title="busy", slot=slot, provide_progress_controller=True,
            pos_args=[], kw_args={},
            before_start_callback=None,
        )

    yield occupy

    # The TaskController lives on the shared application context, so a slot left
    # occupied would leak into the next test.
    for controller, slot in occupied:
        controller._free_slot(slot)


def test_guardrails_disable_inputs_while_a_map_generates(window, occupied_generation_slot, monkeypatch):
    from opengs_maptool.controllers.task_controller import ThreadTaskSlot
    import opengs_maptool.config as config

    monkeypatch.setattr(config, "GUARDRAILS", True)
    left_panel = window._left_panel

    window._tabs.setCurrentIndex(window._tab_names_by_index.index(TabName.LAND))
    assert _labels(left_panel)["Import Land Image"] is True

    occupied_generation_slot(window, ThreadTaskSlot.generate_territory_map)

    # The tab on screen is locked...
    assert _labels(left_panel)["Import Land Image"] is False
    # ...and so is a tab visited while the job runs.
    window._tabs.setCurrentIndex(window._tab_names_by_index.index(TabName.DENSITY))
    density = _labels(left_panel)
    assert density["Import Density Image"] is False
    assert density["Normalize Density"] is False


def test_generating_a_territory_map_blocks_generating_provinces(window, occupied_generation_slot, monkeypatch):
    from opengs_maptool.controllers.task_controller import ThreadTaskSlot
    import opengs_maptool.config as config

    monkeypatch.setattr(config, "GUARDRAILS", True)
    project = window._context.project
    monkeypatch.setattr(project, "terrain_image", object())
    monkeypatch.setattr(project, "territory_data", [])

    window._tabs.setCurrentIndex(window._tab_names_by_index.index(TabName.PROVINCE))
    generate_button = window._left_panel.btn_generate_provinces
    assert generate_button.isEnabled()

    occupied_generation_slot(window, ThreadTaskSlot.generate_territory_map)

    assert not generate_button.isEnabled()


def test_guardrails_disabled_leaves_inputs_alone(window, occupied_generation_slot, monkeypatch):
    from opengs_maptool.controllers.task_controller import ThreadTaskSlot
    import opengs_maptool.config as config

    monkeypatch.setattr(config, "GUARDRAILS", False)
    left_panel = window._left_panel

    occupied_generation_slot(window, ThreadTaskSlot.generate_territory_map)

    window._tabs.setCurrentIndex(window._tab_names_by_index.index(TabName.LAND))
    assert _labels(left_panel)["Import Land Image"] is True


def test_guardrails_release_when_the_slot_frees(window, occupied_generation_slot, monkeypatch):
    from opengs_maptool.controllers.task_controller import ThreadTaskSlot
    import opengs_maptool.config as config

    monkeypatch.setattr(config, "GUARDRAILS", True)
    left_panel = window._left_panel
    controller = window._context.task_controller

    window._tabs.setCurrentIndex(window._tab_names_by_index.index(TabName.LAND))
    occupied_generation_slot(window, ThreadTaskSlot.generate_territory_map)
    assert _labels(left_panel)["Import Land Image"] is False

    # However the task ends -- success, error or cancel -- the slot is freed.
    controller._free_slot(ThreadTaskSlot.generate_territory_map)
    assert _labels(left_panel)["Import Land Image"] is True
