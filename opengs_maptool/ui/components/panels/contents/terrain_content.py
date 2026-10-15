from PyQt6.QtWidgets import QHBoxLayout, QHeaderView, QPushButton, QWidget, QVBoxLayout, QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem
from PyQt6.QtCore import QSize, Qt
import qtawesome as qta
from opengs_maptool.context import ApplicationContext
import opengs_maptool.logic.datastructure as ds
from opengs_maptool.ui.buttons import ColorPickerButton, create_button
from opengs_maptool.ui.file_dialogs import pick_open_image
from opengs_maptool.ui.modals.error_modal import ErrorModal
from opengs_maptool.ui.separators import create_separator

class TerrainContent(QWidget):
    def __init__(self, context: ApplicationContext):
        super().__init__()
        self.setContentsMargins(0, 0, 0, 0)

        self._context = context
        self._import_terrain_btn: QPushButton = None

        self._init_ui()

    def _init_ui(self):
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        actions_group = self._create_terrain_actions_group()
        self._layout.addWidget(actions_group)

        settings_group = self._create_terrain_settings_group()
        self._layout.addWidget(settings_group)

    def _create_terrain_actions_group(self) -> QWidget:
        # Terrain actions group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()
        
        # Import terrain image button
        self._import_terrain_btn = create_button(actions_layout, "Import Terrain Image", lambda: self._import_terrain_image())
        
        actions_group.setLayout(actions_layout)
        return actions_group

    def _create_terrain_settings_group(self) -> QWidget:
        settings_group = QGroupBox("Settings")
        settings_layout = QFormLayout()

        # Land terrains layout
        settings_layout.addRow(create_separator("Land Terrains"))

        land_terrain_table = self._create_terrain_table(self._context.project.land_terrains)
        settings_layout.addRow(land_terrain_table)

        create_button(
            settings_layout,
            "Add Land Terrain",
            lambda: self._add_terrain(land_terrain_table, self._context.project.land_terrains)
        )

        # Naval terrains layout
        settings_layout.addRow(create_separator("Naval Terrains"))

        naval_terrain_table = self._create_terrain_table(self._context.project.naval_terrains)
        settings_layout.addRow(naval_terrain_table)

        create_button(
            settings_layout,
            "Add Naval Terrain",
            lambda: self._add_terrain(naval_terrain_table, self._context.project.naval_terrains)
        )

        # Lake terrains layout
        settings_layout.addRow(create_separator("Lake Terrains"))

        lake_terrain_table = self._create_terrain_table(self._context.project.lake_terrains)
        settings_layout.addRow(lake_terrain_table)

        create_button(
            settings_layout,
            "Add Lake Terrain",
            lambda: self._add_terrain(lake_terrain_table, self._context.project.lake_terrains)
        )

        settings_group.setLayout(settings_layout)
        return settings_group

    def _create_terrain_table(self, terrain_dict: dict[str, ds.ColorTuple]) -> QTableWidget:
        table = QTableWidget(len(terrain_dict), 3)
        table.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
        table.setHorizontalHeaderLabels(["Terrain", "Color", ""])

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 36)
        
        table.verticalHeader().setVisible(False)

        for row, (terrain_name, color) in enumerate(terrain_dict.items()):
            # Add terrain name item
            terrain_name_item = QTableWidgetItem(terrain_name)
            table.setItem(row, 0, terrain_name_item)

            # Add color picker button
            color_btn = ColorPickerButton(color, self, f"New Color")
            color_btn.colorChanged.connect(
                lambda new_color, item=terrain_name_item:
                    self._update_terrain_color(item, new_color, terrain_dict)
            )

            table.setCellWidget(row, 1, color_btn)

            # Add delete button
            delete_btn_container = self._create_delete_button(terrain_name_item, table, terrain_dict)

            if len(terrain_dict) == 1:
                delete_btn = delete_btn_container.findChild(QPushButton)
                if delete_btn:
                    delete_btn.setEnabled(False)

            table.setCellWidget(row, 2, delete_btn_container)

        table.itemChanged.connect(
            lambda item: self._update_terrains(table, terrain_dict) if item.column() == 0 else None
        )

        return table

    def _create_delete_button(self, item: QTableWidgetItem, table: QTableWidget, terrain_dict: dict[str, ds.ColorTuple]) -> QWidget:
        delete_btn = QPushButton()
        delete_btn.setIcon(qta.icon("fa6s.trash"))
        delete_btn.setIconSize(QSize(14, 14))
        delete_btn.setFixedSize(24, 24)
        delete_btn.setToolTip("Delete Terrain")

        delete_btn.clicked.connect(
            lambda checked=False, item=item:
                self._delete_terrain(item, table, terrain_dict)
        )

        delete_btn_container = QWidget()
        delete_btn_layout = QHBoxLayout(delete_btn_container)
        delete_btn_layout.addWidget(delete_btn)
        delete_btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        delete_btn_layout.setContentsMargins(0, 0, 0, 0)

        return delete_btn_container

    def _add_terrain(self, table: QTableWidget, terrain_dict: dict[str, ds.ColorTuple]):
        new_row_index = table.rowCount()
        new_terrain_name = self._generate_unique_terrain_name(terrain_dict)
        new_terrain_color = (255, 255, 255)
        
        # Add the new terrain to the table
        table.insertRow(new_row_index)

        terrain_item = QTableWidgetItem(new_terrain_name)
        table.setItem(new_row_index, 0, terrain_item)

        color_btn = ColorPickerButton(new_terrain_color, self, "New Color")
        table.setCellWidget(new_row_index, 1, color_btn)

        delete_btn = self._create_delete_button(terrain_item, table, terrain_dict)
        table.setCellWidget(new_row_index, 2, delete_btn)

        # Update the terrain dictionary with the new terrain
        terrain_dict[new_terrain_name] = new_terrain_color
        self._context.project.modified = True

    def _delete_terrain(self, item: QTableWidgetItem, table: QTableWidget, terrain_dict: dict[str, ds.ColorTuple]):
        terrain_name = item.text()
        if terrain_name in terrain_dict:
            del terrain_dict[terrain_name]
            self._context.project.modified = True

        # Remove the row from the table
        row_index = item.row()
        table.removeRow(row_index)

        self._update_terrains(table, terrain_dict)
        
    def _update_terrains(self, table: QTableWidget, terrain_dict: dict[str, ds.ColorTuple]):
        terrain_dict.clear()

        # Update the terrain dictionary based on the current state of the table
        for row in range(table.rowCount()):
            terrain_name_item = table.item(row, 0)
            color_btn = table.cellWidget(row, 1)

            if terrain_name_item and color_btn:
                terrain_color = color_btn.color()
                terrain_name = terrain_name_item.text()

                # Check that each terrain name is unique; if not, generate one
                if not self._check_terrain_name_uniqueness(terrain_name, terrain_dict):
                    terrain_name = self._generate_unique_terrain_name(terrain_dict)
                    terrain_name_item.setText(terrain_name)

                terrain_dict[terrain_name] = terrain_color
                self._context.project.modified = True

        # Enables or disables the delete buttons based on the number of terrains
        can_delete = table.rowCount() > 1

        for row in range(table.rowCount()):
            container = table.cellWidget(row, 2)
            if container:
                delete_btn = container.findChild(QPushButton)
                if delete_btn:
                    delete_btn.setEnabled(can_delete)

    def _update_terrain_color(self, item: QTableWidgetItem, new_color: ds.ColorTuple, terrain_dict: dict[str, ds.ColorTuple]):
        terrain_name = item.text()
        terrain_dict[terrain_name] = new_color
        self._context.project.modified = True

    def _check_terrain_name_uniqueness(self, terrain_name: str, terrain_dict: dict[str, ds.ColorTuple]) -> bool:
        """Check if the terrain name is unique in the given terrain dictionary."""
        return terrain_name not in terrain_dict

    def _generate_unique_terrain_name(self, terrain_dict: dict[str, ds.ColorTuple]) -> str:
        i = len(terrain_dict)
        terrain_name = "terrain_" + str(i)

        while not self._check_terrain_name_uniqueness(terrain_name, terrain_dict):
            i += 1
            terrain_name = "terrain_" + str(i)

        return terrain_name

    def _import_terrain_image(self):
        path = pick_open_image(self, "Import Terrain Image")
        if path:
            error = self._context.import_service.import_terrain_image(path)

            # Displays a message if an error occurs
            if error is not None:
                modal = ErrorModal(self, str(error))
                modal.exec()

    def get_import_button(self) -> QPushButton:
        return self._import_terrain_btn
