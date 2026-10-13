from PyQt6.QtWidgets import QMenuBar

class MenuBar:
    def __init__(self, main_window):
        self._main_window = main_window
        self._create_menu_bar()
        

    def _create_menu_bar(self):
        menu_bar: QMenuBar = self._main_window.menuBar()

        menu_file = menu_bar.addMenu("File")
        menu_file.addAction(self._main_window.action_new)
        menu_file.addAction(self._main_window.action_open)
        menu_file.addSeparator()
        menu_file.addAction(self._main_window.action_save)
        menu_file.addAction(self._main_window.action_save_as)
        menu_file.addSeparator()
        menu_file.addAction(self._main_window.action_quit)

        menu_edit = menu_bar.addMenu("Edit")
        menu_edit.addAction(self._main_window.action_open_project_details)
        # menu_edit.addAction(self._main_window.action_undo)
        # menu_edit.addAction(self._main_window.action_redo)

        menu_view = menu_bar.addMenu("View")
        menu_view.addAction(self._main_window.action_fullscreen)
        menu_view.addSeparator()
        menu_view.addAction(self._main_window.action_zoom_in)
        menu_view.addAction(self._main_window.action_zoom_out)
        menu_view.addAction(self._main_window.action_reset_zoom)

        menu_help = menu_bar.addMenu("Help")
        menu_help.addAction(self._main_window.action_open_github)
        menu_help.addAction(self._main_window.action_open_console_help)
        menu_help.addAction(self._main_window.action_open_discord)
