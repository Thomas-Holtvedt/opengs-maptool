from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QFormLayout,
    QVBoxLayout,
)
from opengs_maptool.controllers.project_controller import ProjectController


class ProjectDetailsModal(QDialog):
    def __init__(self, parent, project_controller: ProjectController):
        super().__init__(parent)
        self._project_controller = project_controller

        self.setWindowTitle("Project details")
        self.setModal(True)

        self._create_ui()
        self._load_project()


    def _create_ui(self):
        """Create the UI elements for the project details form."""
        self._name_input = QLineEdit()

        self._editor_version_input = QLineEdit()
        self._editor_version_input.setReadOnly(True)

        self._description_input = QTextEdit()
        self._description_input.setFixedHeight(120)

        self._author_input = QLineEdit()

        # Project path (not editable)
        self._path_label = QLabel()
        self._path_label.setWordWrap(True)
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        form_layout = QFormLayout()
        form_layout.addRow("Name <span style='color: red;'>*</span>", self._name_input)
        form_layout.addRow("Editor version <span style='color: red;'>*</span>", self._editor_version_input)
        form_layout.addRow("Description", self._description_input)
        form_layout.addRow("Author", self._author_input)
        form_layout.addRow("Project path", self._path_label)

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.accepted.connect(self._on_save)
        self._button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(self._button_box)


    def _load_project(self):
        """Load project details into the form fields."""
        project = self._project_controller.get_project()
        self._name_input.setText(project.name)
        self._editor_version_input.setText(project.editor_version)
        self._description_input.setPlainText(project.description or "")
        self._author_input.setText(project.author or "")
        self._path_label.setText(project.file_path or "Not saved yet")


    def _on_save(self):
        """Validate input and save changes to the project."""
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation error", "Project name is required.")
            return

        description = self._description_input.toPlainText().strip() or None
        author = self._author_input.text().strip() or None

        self._project_controller.set_project_name(name)
        self._project_controller.set_project_description(description)
        self._project_controller.set_project_author(author)

        self.accept()
