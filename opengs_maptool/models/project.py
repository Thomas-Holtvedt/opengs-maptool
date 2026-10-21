from __future__ import annotations
from typing import TYPE_CHECKING
import opengs_maptool.config as config
import opengs_maptool.logic.datastructure as ds

if TYPE_CHECKING:
    from opengs_maptool.context import ApplicationContext

class Project:
    """In-memory project state for map inputs, outputs, options, and metadata."""

    def __init__(
            self,
            name: str = "Untitled Project",
            editor_version: str = config.VERSION,
            description: str | None = None,
            author: str | None = None
        ):
        # Project description (please use controller to modify)
        self.name: str = name
        self.editor_version: str = editor_version
        self.description: str | None = description
        self.author: str | None = author

        # Images of the maps
        self.land_image: ds.LandImage | None = None
        self.boundary_image: ds.BoundaryImage | None = None
        self.density_image: ds.DensityImage | None = None
        self.terrain_image: ds.TerrainImage | None = None
        self.territory_image: ds.TerritoryImage | None = None
        self.province_image: ds.ProvinceImage | None = None

        # Data of the maps
        self.territory_data: list[ds.RegionMetadata] | None = None
        self.province_data: list[ds.RegionMetadata] | None = None

        # Metadata of the maps
        self.territory_pmap: ds.RegionPixelMap | None = None
        self.cached_masks: ds.Masks | None = None

        # Project settings
        self.land_color: ds.ColorTuple = config.DEFAULT_LAND_COLOR
        self.ocean_color: ds.ColorTuple = config.DEFAULT_OCEAN_COLOR
        self.lake_color: ds.ColorTuple = config.DEFAULT_LAKE_COLOR

        # Generation options
        self.land_territory_density = config.LAND_TERRITORIES_DEFAULT
        self.oceanic_territory_density = config.OCEAN_TERRITORIES_DEFAULT
        self.territory_density_strength = config.DENSITY_STRENGTH_DEFAULT
        self.territory_jagged_land_amplitude = config.JAGGED_BORDER_LAND_AMPLITUDE_DEFAULT
        self.territory_jagged_ocean_amplitude = config.JAGGED_BORDER_OCEAN_AMPLITUDE_DEFAULT
        self.territory_exclude_ocean = False

        self.land_province_density = config.LAND_PROVINCES_DEFAULT
        self.oceanic_province_density = config.OCEAN_PROVINCES_DEFAULT
        self.province_density_strength = config.DENSITY_STRENGTH_DEFAULT
        self.province_jagged_land_amplitude = config.JAGGED_BORDER_LAND_AMPLITUDE_DEFAULT
        self.province_jagged_ocean_amplitude = config.JAGGED_BORDER_OCEAN_AMPLITUDE_DEFAULT
        self.province_exclude_ocean = False

        # Others
        self.file_path: str | None = None
        self.modified: bool = False


    def is_generation_locked(self, context: ApplicationContext) -> bool:
        """True while a territory or province map is being generated.

        Both count for either map, because they share the same input images.
        """
        from opengs_maptool.controllers.task_controller import ThreadTaskSlot
        if not config.GUARDRAILS:
            return False

        task_controller = context.task_controller
        return (
            task_controller.is_thread_slot_occupied(ThreadTaskSlot.generate_territory_map)
            or task_controller.is_thread_slot_occupied(ThreadTaskSlot.generate_province_map)
        )

    def get_density_image_remove_status(self, context: ApplicationContext) -> tuple[bool, str]:
        if self.is_generation_locked(context):
            return False, "A generation task is currently in progress."
        if self.density_image is None:
            return False, "No density image to remove."
        return True, "Density image can be removed."

    def can_density_image_be_removed(self, context: ApplicationContext) -> bool:
        return self.get_density_image_remove_status(context)[0]

    def get_density_image_generate_status(self, context: ApplicationContext) -> tuple[bool, str]:
        if self.is_generation_locked(context):
            return False, "A generation task is currently in progress."
        if self.density_image is not None:
            return False, "Density image already exists."
        if self.land_image is None:
            return False, "Land image is required to generate density image."
        return True, "Density image can be generated."

    def can_density_image_be_generated(self, context: ApplicationContext) -> bool:
        return self.get_density_image_generate_status(context)[0]

    def get_territory_image_generate_status(self, context: ApplicationContext, ignore_locked: bool) -> tuple[bool, str]:
        if (not ignore_locked) and self.is_generation_locked(context):
            return False, "A generation task is currently in progress."
        if self.land_image is None:
            return False, "Land image is required to generate territory image."
        if self.boundary_image is None:
            return False, "Boundary image is required to generate territory image."
        if self.density_image is None:
            return False, "Density image is required to generate territory image."
        return True, "Territory image can be generated."

    def can_territory_image_be_generated(self, context: ApplicationContext, ignore_locked: bool) -> bool:
        return self.get_territory_image_generate_status(context, ignore_locked)[0]

    def get_province_image_generate_status(self, context: ApplicationContext, ignore_locked: bool) -> tuple[bool, str]:
        if (not ignore_locked) and self.is_generation_locked(context):
            return False, "A generation task is currently in progress."
        if self.terrain_image is None:
            return False, "Terrain image is required to generate province image."
        if self.territory_data is None:
            return False, "Territory data is required to generate province image."
        return True, "Province image can be generated."

    def can_province_image_be_generated(self, context: ApplicationContext, ignore_locked: bool) -> bool:
        return self.get_province_image_generate_status(context, ignore_locked)[0]
