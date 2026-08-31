from __future__ import annotations
import opengs_maptool.config as config
import opengs_maptool.logic.datastructure as ds
import numpy as np
from numpy.typing import NDArray

class Project:
    """In-memory project state for map inputs, outputs, options, and metadata."""

    def __init__(
            self,
            name: str = "Untitled Project",
            editor_version: str = config.VERSION,
            description: str | None = None,
            author: str | None = None
        ):
        # Project description
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
        self.ocean_color: tuple[int] = config.DEFAULT_OCEAN_COLOR
        self.lake_color: tuple[int] = config.DEFAULT_LAKE_COLOR

        # Generation options
        self.land_territory_density = config.LAND_TERRITORIES_DEFAULT
        self.oceanic_territory_density = config.OCEAN_TERRITORIES_DEFAULT
        self.territory_density_strength = config.DENSITY_STRENGTH_DEFAULT
        self.territory_jagged_land = False
        self.territory_jagged_ocean = False

        self.territory_exclude_ocean = False
        self.province_exclude_ocean = False

        self.land_province_density = config.LAND_PROVINCES_DEFAULT
        self.oceanic_province_density = config.OCEAN_PROVINCES_DEFAULT
        self.province_density_strength = config.DENSITY_STRENGTH_DEFAULT
        self.province_jagged_land = False
        self.province_jagged_ocean = False

        # Others
        self.file_path: str | None = None
        self.modified: bool = False


    def can_density_image_be_removed(self) -> bool:
        return self.density_image is not None

    def can_density_image_be_generated(self) -> bool:
        return (self.density_image is None) and (self.land_image is not None)

    def can_territory_image_be_generated(self) -> bool:
        return (
            (self.land_image is not None) and
            (self.boundary_image is not None) and
            (self.density_image is not None)
        )

    def can_province_image_be_generated(self) -> bool:
        return (self.terrain_image is not None) and (self.territory_data is not None)
