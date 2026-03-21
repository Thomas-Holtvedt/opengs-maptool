from dataclasses import dataclass, field
import numpy as np
from numpy.typing import NDArray
from pathlib import Path
from PIL import Image
from typing import IO, Literal
from tqdm import tqdm
import opengs_maptool.config as config
from opengs_maptool.logic.province_generator import generate_province_map
from opengs_maptool.logic.territory_generator import generate_territory_map
from opengs_maptool.logic.density_generator import normalize_density, equator_density
from opengs_maptool.logic.export_module import (
    export_territory_definitions_to_path,
    export_territory_history_to_path,
    export_province_definitions_to_path,
)


@dataclass(init=True)
class MainProgram:
    #=======================================================#
    #                  Internal Attributes                  #
    #=======================================================#

    # Images
    _land_image: Image.Image | None = field(init=False, default=None)
    _boundary_image: Image.Image | None = field(init=False, default=None)
    _density_image: Image.Image | None = field(init=False, default=None)
    _terrain_image: Image.Image | None = field(init=False, default=None)

    _territory_image: Image.Image | None = field(init=False, default=None)
    _province_image: Image.Image | None = field(init=False, default=None)

    # Territories
    _territory_density_strength: float = field(init=False, default=config.DENSITY_STRENGTH_DEFAULT / 10.0)
    _territory_exclude_ocean_density: bool = field(init=False, default=False)
    _territory_jagged_land: bool = field(init=False, default=False)
    _territory_jagged_ocean: bool = field(init=False, default=False)
    _territory_land_density: int = field(init=False, default=config.LAND_TERRITORIES_DEFAULT)
    _territory_ocean_density: int = field(init=False, default=config.OCEAN_TERRITORIES_DEFAULT)

    # Provinces
    _province_density_strength: float = field(init=False, default=config.DENSITY_STRENGTH_DEFAULT / 10.0)
    _province_exclude_ocean_density: bool = field(init=False, default=False)
    _province_jagged_land: bool = field(init=False, default=False)
    _province_jagged_ocean: bool = field(init=False, default=False)
    _province_land_density: int = field(init=False, default=config.LAND_PROVINCES_DEFAULT)
    _province_ocean_density: int = field(init=False, default=config.OCEAN_PROVINCES_DEFAULT)

    # Other Variables
    _progress: int = field(init=False, default=0) # not functionally necessary
    _tqdm_bar: object = field(init=False, default=None, repr=False)
    _last_progress: int = field(init=False, default=None, repr=False)
    _current_process_name: str = field(init=False, default="Generating")


    #=======================================================#
    #                    Exposed Methods                    #
    #=======================================================#

    # Load input images and set parameters
    def load_land_image(self, source: Path | str | Image.Image) -> None:
        if isinstance(source, Image.Image):
            image = source
        else:
            image = Image.open(source)
        self.set_land_image(image)
        self.check_territory_ready()
    
    def load_boundary_image(self, source: Path | str | Image.Image) -> None:
        if isinstance(source, Image.Image):
            image = source
        else:
            image = Image.open(source)
        self.set_boundary_image(image)
    
    def load_density_image(self, source: Path | str | Image.Image) -> None:
        if isinstance(source, Image.Image):
            image = source
        else:
            image = Image.open(source)
        self.set_density_image(image)
        self.check_territory_ready()
    
    def load_normalized_density_image(self) -> None:
        land_image = self.get_land_image()
        if land_image is None:
            raise ValueError("Land image must be loaded before generating normalized density image.")
        normalize_density(self)

    def load_equator_density_image(self) -> None:
        land_image = self.get_land_image()
        if land_image is None:
            raise ValueError("Land image must be loaded before generating equator density image.")
        equator_density(self)

    def load_terrain_image(self, source: Path | str | Image.Image) -> None:
        if isinstance(source, Image.Image):
            image = source
        else:
            image = Image.open(source)
        self.set_terrain_image(image)

    # Process & Generation Steps - Territories
    def set_territory_params(self,
            land_density: int = config.LAND_TERRITORIES_DEFAULT,
            ocean_density: int = config.OCEAN_TERRITORIES_DEFAULT,
            density_strength: float = config.DENSITY_STRENGTH_DEFAULT / 10.0,
            jagged_land_borders: bool = False,
            jagged_ocean_borders: bool = False,
        ) -> None:
        self._territory_land_density = land_density
        self._territory_ocean_density = ocean_density
        self._territory_density_strength = density_strength
        self._territory_jagged_land = jagged_land_borders
        self._territory_jagged_ocean = jagged_ocean_borders
    
    def generate_territories(self) -> None:
        land_exists = self.get_land_image() is not None
        density_exists = self.get_density_image() is not None
        if not(land_exists and density_exists):
            raise ValueError("Territory generation is not available. Ensure land and density images are loaded.")
        self._current_process_name = "Generating Territories"
        generate_territory_map(self)

    def export_territory_image(self, output: Path | str | IO[bytes]) -> None:
        try:
            self.get_territory_image().save(output)
        except AttributeError as error:
            raise ValueError("No territory image to export.") from error
    
    def export_territory_definitions(self, output: Path | str, format: Literal["json", "csv"]) -> None:
        _, territory_data = self.get_territory_pmap_and_data()
        if not territory_data:
            raise ValueError("No territory data to export.")
        export_territory_definitions_to_path(territory_data, output, format)

    def export_territory_history(self, output: Path | str, format: Literal["json", "csv"]) -> None:
        _, territory_data = self.get_territory_pmap_and_data()
        if not territory_data:
            raise ValueError("No territory data to export. Generate territories and provinces before exporting territory history.")
        
        province_data = self.get_province_data()
        if not province_data:
            raise ValueError("No province data available. Generate provinces before exporting territory history.")
        export_territory_history_to_path(territory_data, output, format)

    # Process & Generation Steps - Provinces
    def set_province_params(self,
            land_density: int = config.LAND_PROVINCES_DEFAULT,
            ocean_density: int = config.OCEAN_PROVINCES_DEFAULT,
            density_strength: float = config.DENSITY_STRENGTH_DEFAULT / 10.0,
            jagged_land_borders: bool = False,
            jagged_ocean_borders: bool = False,
        ) -> None:
        self._province_land_density = land_density
        self._province_ocean_density = ocean_density
        self._province_density_strength = density_strength
        self._province_jagged_land = jagged_land_borders
        self._province_jagged_ocean = jagged_ocean_borders
    
    def generate_provinces(self) -> None:
        try:
            self.get_territory_pmap_and_data()
            territory_exists = True
        except RuntimeError:
            territory_exists = False
        density_exists = self.get_density_image() is not None

        if not(territory_exists and density_exists):
            raise ValueError("Province generation is not available. Ensure territories are generated and the density image is loaded.")
        self._current_process_name = "Generating Provinces"
        generate_province_map(self)

    def export_province_image(self, output: Path | str | IO[bytes]) -> None:
        try:
            self.get_province_image().save(output)
        except AttributeError as error:
            raise ValueError("No province image to export.") from error
    
    def export_province_definitions(self, output: Path | str, format: Literal["json", "csv"]) -> None:
        province_data = self.get_province_data()
        if not province_data:
            raise ValueError("No province data to export.")
        export_province_definitions_to_path(province_data, output, format)
   

    #=======================================================#
    #           Implement MapToolProtocol methods           #
    #=======================================================#

    # Progress
    def start_progress(self) -> None:
        self.set_progress(0)

    def set_progress(self, value: int) -> None:
        self._progress = value

        if self._tqdm_bar is None:
            self._tqdm_bar = tqdm(
                total=100, desc=self._current_process_name,
                leave=True, ncols=70, unit="%",
            )
            self._last_progress = 0

        # Only update if value changes
        if value != self._last_progress:
            delta = value - self._last_progress
            self._tqdm_bar.update(delta)
            self._last_progress = value

        if value >= 100:
            self._tqdm_bar.close()
            self._tqdm_bar = None
            self._last_progress = None
    
    def get_progress(self) -> int:
        return self._progress

    # Land
    def set_land_image(self, image: Image.Image | None) -> None:
        self._land_image = image.convert("RGBA") if image is not None else None
        self.set_edit_density_available(True)

    def get_land_image(self) -> Image.Image | None:
        return self._land_image

    # Boundary
    def set_boundary_image(self, image: Image.Image | None) -> None:
        self._boundary_image = image.convert("RGBA") if image is not None else None

    def get_boundary_image(self) -> Image.Image | None:
        return self._boundary_image

    # Terrain
    def set_terrain_image(self, image: Image.Image | None) -> None:
        self._terrain_image = image.convert("RGBA") if image is not None else None

    def get_terrain_image(self) -> Image.Image | None:
        return self._terrain_image

    # Density
    def set_density_image(self, image: Image.Image | None) -> None:
        self._density_image = image.convert("RGBA") if image is not None else None

    def get_density_image(self) -> Image.Image | None:
        return self._density_image

    def set_edit_density_available(self, available: bool) -> None:
        pass # not relevant

    # Territory
    def set_territory_pmap_and_data(self, pmap: NDArray[np.int32], data: list[dict]) -> None:
        self._territory_pmap = pmap
        self._territory_data = data
    
    def get_territory_pmap_and_data(self) -> tuple[NDArray[np.int32], list[dict]]:
        # Providing a default value makes no sense here, so raise
        try:
            return (self._territory_pmap, self._territory_data)
        except AttributeError as error:
            raise RuntimeError("Territory pmap and data accessed before being set") from error
        
    def set_cached_masks(self, masks: dict) -> None:
        self._cached_masks = masks
    
    def get_cached_masks(self) -> dict:
        # Providing a default value makes no sense here, so raise
        try:
            return self._cached_masks
        except AttributeError as error:
            raise RuntimeError("Cached masks accessed before being set") from error

    def set_territory_image(self, image: Image.Image | None) -> None:
        self._territory_image = image.convert("RGBA") if image is not None else None

    def get_territory_image(self) -> Image.Image | None:
        return self._territory_image

    def get_territory_density_strength(self) -> float:
        # No scaling necessary, taken in correct range directly
        return self._territory_density_strength

    def get_territory_exclude_ocean_density(self) -> bool:
        return self._territory_exclude_ocean_density

    def get_territory_jagged_land(self) -> bool:
        return self._territory_jagged_land

    def get_territory_jagged_ocean(self) -> bool:
        return self._territory_jagged_ocean

    def get_territory_land_density(self) -> int:
        return self._territory_land_density

    def get_territory_ocean_density(self) -> int:
        return self._territory_ocean_density

    def set_territory_gen_available(self, available: bool) -> None:
        pass # not relevant

    def set_territory_export_available(self, available: bool) -> None:
        pass # not relevant

    def set_territory_history_export_available(self, available: bool) -> None:
        pass # not relevant

    # Province
    def set_province_image(self, image: Image.Image | None) -> None:
        self._province_image = image.convert("RGBA") if image is not None else None
    
    def get_province_image(self) -> Image.Image | None:
        return self._province_image

    def set_province_data(self, data: list[dict] | None) -> None:
        self.province_data = data

    def get_province_data(self) -> list[dict] | None:
        return self.province_data # None by default

    def get_province_density_strength(self) -> float:
        # No scaling necessary, taken in correct range directly
        return self._province_density_strength

    def get_province_exclude_ocean_density(self) -> bool:
        return self._province_exclude_ocean_density

    def get_province_jagged_land(self) -> bool:
        return self._province_jagged_land

    def get_province_jagged_ocean(self) -> bool:
        return self._province_jagged_ocean

    def get_province_land_province_density(self) -> int:
        return self._province_land_density

    def get_province_ocean_province_density(self) -> int:
        return self._province_ocean_density

    def set_province_gen_available(self, available: bool) -> None:
        pass # not relevant

    def set_province_export_available(self, available: bool) -> None:
        pass # not relevant
    
    # Notifications
    def check_territory_ready(self) -> None:
        pass # not relevant


