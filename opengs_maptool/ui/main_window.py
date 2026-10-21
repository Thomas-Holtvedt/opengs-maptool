from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from opengs_maptool.app import App

import opengs_maptool.config as config
import opengs_maptool.logic.editor_actions as editor_actions
from opengs_maptool.simple_types import TabName
from opengs_maptool.ui.components.bars.menu_bar import MenuBar
from opengs_maptool.ui.components.bars.status_bar import StatusBar
from opengs_maptool.ui.components.bars.tool_bar import ToolBar
from opengs_maptool.ui.components.panels.left_panel import LeftPanel
from opengs_maptool.ui.components.panels.right_panel import RightPanel
from opengs_maptool.ui.components.tab import Tab
from opengs_maptool.controllers.project_controller import ProjectAttribute
from opengs_maptool.ui.file_dialogs import pick_open_project, pick_save_project
from opengs_maptool.ui.modals.error_modal import ErrorModal
from opengs_maptool.ui.modals.project_details_modal import ProjectDetailsModal
from opengs_maptool.ui.modals.save_modal import SaveModal
from opengs_maptool.ui.modals.stopping_tasks_modal import StoppingTasksModal
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (QMainWindow, QWidget,
                             QHBoxLayout, QTabWidget, QVBoxLayout,
                             QSplitter)
import qtawesome as qta

class MainWindow(QMainWindow):
    def __init__(self, app: App):
        super().__init__()
        self._app = app
        self._context = app.context

        self._update_window_title(ProjectAttribute.name)
        self.setMinimumSize(800, 600)
        self.resize(config.WINDOW_SIZE_WIDTH, config.WINDOW_SIZE_HEIGHT)

        self._create_actions()
        self._init_layout()

        # Refresh UI when context reports project-level changes.
        self._context.project_controller.project_was_modified.connect(self._update_window_title)

    def _update_window_title(self, attribute: ProjectAttribute):
        if attribute == ProjectAttribute.name:
            self.setWindowTitle(self._context.project.name + " - " + config.TITLE)

    def _init_layout(self):
        self._menu_bar = MenuBar(self)
        self._tool_bar = ToolBar(self)
        self._status_bar = StatusBar(self)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)

        content_layout = QHBoxLayout()

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel
        self._left_panel = LeftPanel(self._context, self)
        splitter.addWidget(self._left_panel)

        # Central panel
        self._tabs = QTabWidget()

        # Create all tabs
        # use a trick to avoid typing out the names manually
        self._tab_names_by_index = list[TabName]()
        for tab_name_enum in TabName:
            tab = Tab(tab_name_enum)
            self._tabs.addTab(tab, tab_name_enum.value.capitalize())
            self._tab_names_by_index.append(tab_name_enum)

        self._tabs.currentChanged.connect(self._update_left_panel)
        # addTab() already selected the first tab above, emitting currentChanged
        # before the connect existed, so populate the left panel for it here.
        self.update_current_left_panel()
        splitter.addWidget(self._tabs)

        # Right panel
        right_panel = RightPanel(self._context, self)
        splitter.addWidget(right_panel)

        splitter.setSizes([400, 900, 300])
        splitter.setChildrenCollapsible(False)

        content_layout.addWidget(splitter)
        main_layout.addLayout(content_layout, stretch=1)

    def _update_left_panel(self, index):
        self._left_panel.display_content(self._tab_names_by_index[index])


    def update_current_left_panel(self):
        self._update_left_panel(self._tabs.currentIndex())


    def update_all_image_displays(self):
        for i in range(self._tabs.count()):

            tab: Tab = self._tabs.widget(i)
            tab_name = tab.get_tab_name_enum()
            image_display = tab.get_image_display()

            match tab_name:
                case TabName.LAND:
                    image_display.set_image(self._context.project.land_image)
                case TabName.BOUNDARY:
                    image_display.set_image(self._context.project.boundary_image)
                case TabName.DENSITY:
                    image_display.set_image(self._context.project.density_image)
                case TabName.TERRAIN:
                    image_display.set_image(self._context.project.terrain_image)
                case TabName.TERRITORY:
                    image_display.set_image(self._context.project.territory_image)
                case TabName.PROVINCE:
                    image_display.set_image(self._context.project.province_image)


    # TODO: Perhaps create an actions file containing all the actions instead of storing them here
    def _create_actions(self):
        self.action_new = QAction(qta.icon('fa6s.file'), "New", self)
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        self.action_new.triggered.connect(self._new_project)
        self.action_new.setIconVisibleInMenu(False)

        self.action_open = QAction(qta.icon('fa6s.folder-open'), "Open", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self._open_project)
        self.action_open.setIconVisibleInMenu(False)

        self.action_save = QAction(qta.icon('fa6s.floppy-disk'), "Save", self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.triggered.connect(self._save_project)
        self.action_save.setIconVisibleInMenu(False)

        self.action_save_as = QAction("Save as", self)
        self.action_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.action_save_as.triggered.connect(self._save_project_as)

        self.action_quit = QAction("Quit", self)
        self.action_quit.setShortcut(QKeySequence.StandardKey.Close)
        self.action_quit.triggered.connect(self.close)

        self.action_open_project_details = QAction(qta.icon('fa6s.pencil'), "Project details", self)
        self.action_open_project_details.setShortcut(QKeySequence("Ctrl+I"))
        self.action_open_project_details.triggered.connect(self._open_project_details)
        self.action_open_project_details.setIconVisibleInMenu(False)

        # TODO: Create undo / redo actions
        # self.action_undo = QAction("Undo", self)
        # self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)

        # self.action_redo = QAction("Redo", self)
        # self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)

        self.action_fullscreen = QAction("Fullscreen", self)
        self.action_fullscreen.setShortcut(QKeySequence.StandardKey.FullScreen)
        self.action_fullscreen.triggered.connect(self._fullscreen)

        self.action_zoom_in = QAction("Zoom in", self)
        self.action_zoom_in.setShortcut(QKeySequence.StandardKey.ZoomIn)
        self.action_zoom_in.triggered.connect(self._zoom_in)

        self.action_zoom_out = QAction("Zoom out", self)
        self.action_zoom_out.setShortcut(QKeySequence.StandardKey.ZoomOut)
        self.action_zoom_out.triggered.connect(self._zoom_out)

        self.action_reset_zoom = QAction("Reset zoom", self)
        self.action_reset_zoom.setShortcut(QKeySequence("Ctrl+0"))
        self.action_reset_zoom.triggered.connect(self._reset_zoom)

        self.action_open_github = QAction("GitHub", self)
        self.action_open_github.triggered.connect(editor_actions.open_github)

        self.action_open_console_help = QAction("Console help", self)
        self.action_open_console_help.triggered.connect(editor_actions.open_console_help)

        self.action_open_discord = QAction("Discord", self)
        self.action_open_discord.triggered.connect(editor_actions.open_discord)


    def _fullscreen(self):
        if self.isFullScreen() != True:
            self.showFullScreen()
        else:
            self.showNormal()


    def _zoom_in(self):
        image_display = self.get_current_image_display()
        if image_display is not None:
            image_display.zoom_in()


    def _zoom_out(self):
        image_display = self.get_current_image_display()
        if image_display is not None:
            image_display.zoom_out()


    def _reset_zoom(self):
        image_display = self.get_current_image_display()
        if image_display is not None:
            image_display.reset_zoom()


    def _new_project(self):
        if not self._confirm_discarded_changes():
            return

        self._context.project_controller.create_project()


    def _open_project(self):
        if not self._confirm_discarded_changes():
            return

        filename = pick_open_project(self, "Open project")

        if not filename:
            return

        try:
            self._context.project_controller.load_project(filename)
        except Exception:
            error_text = "Cannot open this file, incompatible format"
            error_modal = ErrorModal(self, error_text)
            error_modal.exec()


    def _save_project(self) -> bool:
        if self._context.project_controller.save_project():
            return True

        return self._save_project_as()


    def _save_project_as(self) -> bool:
        filename = pick_save_project(self, "Save project")

        if not filename:
            return False

        self._context.project_controller.save_project_as(filename)
        return True


    def _open_project_details(self):
        modal = ProjectDetailsModal(self, self._context.project_controller)
        modal.exec()


    def _confirm_discarded_changes(self) -> bool:
        if not self._context.project_controller.is_project_modified():
            return True

        save_modal = SaveModal(self)
        response = save_modal.exec()

        if response == SaveModal.StandardButton.Save:
            return self._save_project()
        elif response == SaveModal.StandardButton.Discard:
            return True
        else:
            return False


    def closeEvent(self, event):
        if self._confirm_discarded_changes():
            # Ask running background tasks to stop and wait briefly.
            # If the modal times out the user can choose to force quit.
            modal = StoppingTasksModal(self)
            modal.start_and_wait(self._context.task_controller, timeout_ms=4000)
            event.accept()
        else:
            event.ignore()
