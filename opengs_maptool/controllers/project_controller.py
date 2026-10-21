from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from opengs_maptool.context import ApplicationContext

from enum import Enum, auto
from PyQt6.QtCore import QObject, pyqtSignal
from opengs_maptool.models.project import Project
from opengs_maptool.services.project_service import ProjectService
from opengs_maptool.logic import datastructure as ds


class ProjectAttribute(Enum):
    """
    Enum representing the various attributes of a project.
    The attribute names have to match the project attributes exactly.
    """
    # Project description
    name = auto()
    editor_version = auto()
    description = auto()
    author = auto()

    # Images of the maps
    land_image = auto()
    boundary_image = auto()
    density_image = auto()
    terrain_image = auto()
    territory_image = auto()
    province_image = auto()

    # Data of the maps
    territory_data = auto()
    province_data = auto()

    # Metadata of the maps
    territory_pmap = auto()
    cached_masks = auto()

    # Project settings
    land_color = auto()
    ocean_color = auto()
    lake_color = auto()

    # Generation options
    land_territory_density = auto()
    oceanic_territory_density = auto()
    territory_density_strength = auto()
    territory_jagged_land_amplitude = auto()
    territory_jagged_ocean_amplitude = auto()
    territory_exclude_ocean = auto()

    land_province_density = auto()
    oceanic_province_density = auto()
    province_density_strength = auto()
    province_jagged_land_amplitude = auto()
    province_jagged_ocean_amplitude = auto()
    province_exclude_ocean = auto()

class ProjectController(QObject):
    """Coordinate project lifecycle actions between UI context and project service."""

    project_was_modified = pyqtSignal(ProjectAttribute)

    def __init__(self, context: ApplicationContext, project_service: ProjectService):
        super().__init__()
        self._context = context
        self._project_service = project_service


    def create_project(self) -> Project:
        # TODO: fix bug: last save path is not reset after new project creation
        project = self._project_service.create()
        self._context.project = project
        for attribute in ProjectAttribute:
            self._notify_project_modified(attribute)
        return project


    def load_project(self, path: str) -> Project:
        # TODO: fix bug: last save path is not reset after new project loading
        project = self._project_service.load(path)
        self._context.project = project
        for attribute in ProjectAttribute:
            self._notify_project_modified(attribute, set_modified=False) # don't accidentally mark as modified
        return project


    def save_project(self) -> bool:
        if self._context.project.file_path is None:
            return False

        self._project_service.save(self._context.project, self._context.project.file_path)
        return True


    def save_project_as(self, path: str) -> bool:
        self._project_service.save(self._context.project, path)
        return True


    def get_project(self) -> Project:
        return self._context.project


    def is_project_modified(self) -> bool:
        return self._context.project.modified


    def _notify_project_modified(self, attribute: ProjectAttribute, set_modified: bool = True) -> None:
        if set_modified:
            self._context.project.modified = True
        self.project_was_modified.emit(attribute)


    # --- Project metadata setters ------------------------------------

    def set_project_name(self, name: str) -> None:
        if name != self._context.project.name:
            self._context.project.name = name
            self._notify_project_modified(ProjectAttribute.name)


    def set_editor_version(self, version: str) -> None:
        if version != self._context.project.editor_version:
            self._context.project.editor_version = version
            self._notify_project_modified(ProjectAttribute.editor_version)


    def set_project_description(self, description: str | None) -> None:
        if (description or None) != (self._context.project.description or None):
            self._context.project.description = description or None
            self._notify_project_modified(ProjectAttribute.description)


    def set_project_author(self, author: str | None) -> None:
        if (author or None) != (self._context.project.author or None):
            self._context.project.author = author or None
            self._notify_project_modified(ProjectAttribute.author)


    # --- Image setters -------------------------------------------------

    def set_land_image(self, image: ds.LandImage | None) -> None:
        self._context.project.land_image = image
        self._notify_project_modified(ProjectAttribute.land_image)

    def set_boundary_image(self, image: ds.BoundaryImage | None) -> None:
        self._context.project.boundary_image = image
        self._notify_project_modified(ProjectAttribute.boundary_image)

    def set_density_image(self, image: ds.DensityImage | None) -> None:
        self._context.project.density_image = image
        self._notify_project_modified(ProjectAttribute.density_image)

    def set_terrain_image(self, image: ds.TerrainImage | None) -> None:
        self._context.project.terrain_image = image
        self._notify_project_modified(ProjectAttribute.terrain_image)

    def set_territory_image(self, image: ds.TerritoryImage | None) -> None:
        self._context.project.territory_image = image
        self._notify_project_modified(ProjectAttribute.territory_image)

    def set_province_image(self, image: ds.ProvinceImage | None) -> None:
        self._context.project.province_image = image
        self._notify_project_modified(ProjectAttribute.province_image)


    # --- Data setters --------------------------------------------------

    def set_territory_data(self, data: list[ds.RegionMetadata] | None) -> None:
        self._context.project.territory_data = data
        self._notify_project_modified(ProjectAttribute.territory_data)

    def set_province_data(self, data: list[ds.RegionMetadata] | None) -> None:
        self._context.project.province_data = data
        self._notify_project_modified(ProjectAttribute.province_data)


    # --- Map metadata setters ------------------------------------------

    def set_territory_pmap(self, pmap: ds.RegionPixelMap | None) -> None:
        self._context.project.territory_pmap = pmap
        self._notify_project_modified(ProjectAttribute.territory_pmap)

    def set_cached_masks(self, masks: ds.Masks | None) -> None:
        self._context.project.cached_masks = masks
        self._notify_project_modified(ProjectAttribute.cached_masks)

    # --- Project settings -----------------------------------------------

    def set_land_color(self, color: ds.ColorTuple) -> None:
        if color != self._context.project.land_color:
            self._context.project.land_color = color
            self._notify_project_modified(ProjectAttribute.land_color)

    def set_ocean_color(self, color: ds.ColorTuple) -> None:
        if color != self._context.project.ocean_color:
            self._context.project.ocean_color = color
            self._notify_project_modified(ProjectAttribute.ocean_color)

    def set_lake_color(self, color: ds.ColorTuple) -> None:
        if color != self._context.project.lake_color:
            self._context.project.lake_color = color
            self._notify_project_modified(ProjectAttribute.lake_color)


    # --- Color setters --------------------------------------------------

    def set_land_color(self, color: ds.ColorTuple) -> None:
        if color != self._context.project.land_color:
            self._context.project.land_color = color
            self._notify_project_modified(ProjectAttribute.land_color)

    def set_ocean_color(self, color: ds.ColorTuple) -> None:
        if color != self._context.project.ocean_color:
            self._context.project.ocean_color = color
            self._notify_project_modified(ProjectAttribute.ocean_color)

    def set_lake_color(self, color: ds.ColorTuple) -> None:
        if color != self._context.project.lake_color:
            self._context.project.lake_color = color
            self._notify_project_modified(ProjectAttribute.lake_color)


    # --- Territory generation option setters ----------------------------

    def set_land_territory_density(self, value: int | float) -> None:
        if value != self._context.project.land_territory_density:
            self._context.project.land_territory_density = value
            self._notify_project_modified(ProjectAttribute.land_territory_density)

    def set_oceanic_territory_density(self, value: int | float) -> None:
        if value != self._context.project.oceanic_territory_density:
            self._context.project.oceanic_territory_density = value
            self._notify_project_modified(ProjectAttribute.oceanic_territory_density)

    def set_territory_density_strength(self, value: int | float) -> None:
        if value != self._context.project.territory_density_strength:
            self._context.project.territory_density_strength = value
            self._notify_project_modified(ProjectAttribute.territory_density_strength)

    def set_territory_jagged_land_amplitude(self, value: int | float) -> None:
        if value != self._context.project.territory_jagged_land_amplitude:
            self._context.project.territory_jagged_land_amplitude = value
            self._notify_project_modified(ProjectAttribute.territory_jagged_land_amplitude)

    def set_territory_jagged_ocean_amplitude(self, value: int | float) -> None:
        if value != self._context.project.territory_jagged_ocean_amplitude:
            self._context.project.territory_jagged_ocean_amplitude = value
            self._notify_project_modified(ProjectAttribute.territory_jagged_ocean_amplitude)

    def set_territory_exclude_ocean(self, exclude: bool) -> None:
        if exclude != self._context.project.territory_exclude_ocean:
            self._context.project.territory_exclude_ocean = exclude
            self._notify_project_modified(ProjectAttribute.territory_exclude_ocean)


    # --- Province generation option setters -----------------------------

    def set_land_province_density(self, value: int | float) -> None:
        if value != self._context.project.land_province_density:
            self._context.project.land_province_density = value
            self._notify_project_modified(ProjectAttribute.land_province_density)

    def set_oceanic_province_density(self, value: int | float) -> None:
        if value != self._context.project.oceanic_province_density:
            self._context.project.oceanic_province_density = value
            self._notify_project_modified(ProjectAttribute.oceanic_province_density)

    def set_province_density_strength(self, value: int | float) -> None:
        if value != self._context.project.province_density_strength:
            self._context.project.province_density_strength = value
            self._notify_project_modified(ProjectAttribute.province_density_strength)

    def set_province_jagged_land_amplitude(self, value: int | float) -> None:
        if value != self._context.project.province_jagged_land_amplitude:
            self._context.project.province_jagged_land_amplitude = value
            self._notify_project_modified(ProjectAttribute.province_jagged_land_amplitude)

    def set_province_jagged_ocean_amplitude(self, value: int | float) -> None:
        if value != self._context.project.province_jagged_ocean_amplitude:
            self._context.project.province_jagged_ocean_amplitude = value
            self._notify_project_modified(ProjectAttribute.province_jagged_ocean_amplitude)

    def set_province_exclude_ocean(self, exclude: bool) -> None:
        if exclude != self._context.project.province_exclude_ocean:
            self._context.project.province_exclude_ocean = exclude
            self._notify_project_modified(ProjectAttribute.province_exclude_ocean)
