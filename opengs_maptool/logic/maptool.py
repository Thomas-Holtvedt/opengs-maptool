from __future__ import annotations
from gceutils import grepr_dataclass
import numpy as np
from numpy.typing import NDArray
from PIL import Image
from typing import Callable

from opengs_maptool.logic.boundaries_to_cont import convert_boundaries_to_cont_areas, assign_borders_to_areas, classify_pixels_by_color, clean_boundary_image
from opengs_maptool.logic.cont_to_regions import convert_all_cont_areas_to_regions
from opengs_maptool.logic.utils import NumberSeries, RegionMetadata
from opengs_maptool import config


PROGRESS_CALLBACK = Callable[[int, int], None] | None # (Numerator, Denominator) e.g. (113 of 209)

class StepMapTool:
    """
    Open Grand Strategy Map Tool, which can be directly used in Python.
    
    This class provides separate static methods for each step of the map generation pipeline.
    Each method accepts and returns Numpy image arrays and associated region metadata.

    The full map generation pipeline consists of:
        1. Converting boundaries to continuous areas
        2. Generating density samples from continuous areas
        3. Generating territories from density samples
        4. Generating provinces from territories

    Each step can be called independently, allowing for granular control and inspection of intermediate results.
    Progress callbacks can be provided to monitor the progress of each step.
    """


    @staticmethod
    def clean_class_image(class_image: Image.Image) -> Image.Image:
        """
        Standardize a type classification image to configured ocean/lake/land colors.

        Args:
            class_image: Input classification image as PIL Image.

        Returns:
            RGBA image where each pixel is reassigned to the nearest of
            `config.OCEAN_COLOR`, `config.LAKE_COLOR`, or `config.LAND_COLOR`.
        """
        class_image = classify_pixels_by_color(np.array(class_image.convert("RGBA")))
        return Image.fromarray(class_image)

    @staticmethod
    def clean_boundary_image(boundary_image: Image.Image) -> Image.Image:
        """
        Standardize a boundary image to strict black borders and gray areas.

        Args:
            boundary_image: Input boundary image as PIL Image.

        Returns:
            Image with boundaries set to (0, 0, 0, 255)
            and all other pixels set to (128, 128, 128, 255).
        """
        boundary_image = clean_boundary_image(np.array(boundary_image.convert("RGBA")))
        return Image.fromarray(boundary_image)
    

    @staticmethod
    def generate_cont_areas(
        class_image: NDArray[np.uint8],
        boundary_image: NDArray[np.uint8],
        rng_seed: int = config.DEFAULT_CONT_AREAS_RNG_SEED,
        min_area_pixels: int = config.MIN_AREA_PIXELS_DEFAULT,
        progress_callback: PROGRESS_CALLBACK = None,
    ) -> tuple[NDArray[np.uint8], list[RegionMetadata]]:
        """
        Convert boundary and classification images into continuous areas.

        Args:
            class_image: Numpy array of the classification image (land/ocean/lake).
            boundary_image: Numpy array of the boundary image.
            rng_seed: Random seed for reproducibility.
            min_area_pixels: Minimum pixel area for a region.
            progress_callback: Optional callback for progress updates.
        """
        if progress_callback:
            progress_callback(0, 100)

        def boundaries_progress(current, total):
            if progress_callback:
                # Map progress (0-100) to overall progress (0-40)
                progress_callback(int((current / total) * 40), 100)

        areas_with_borders_image, cont_area_data = convert_boundaries_to_cont_areas(
            class_image,
            boundary_image,
            rng_seed,
            min_area_pixels=min_area_pixels,  # Filter out tiny areas & islands
            progress_callback=boundaries_progress,
        )

        if progress_callback:
            progress_callback(40, 100)

        def border_progress(current, total):
            if progress_callback:
                # Map iteration progress (0-100) to overall progress (40-80)
                progress_callback(40 + int((current / total) * 40), 100)

        cont_area_image = assign_borders_to_areas(areas_with_borders_image, area_data=cont_area_data, progress_callback=border_progress)

        if progress_callback:
            progress_callback(80, 100)

        # Assign proper region_ids
        number_series = NumberSeries(config.AREA_ID_PREFIX, config.SERIES_ID_START, config.SERIES_ID_END)
        for region in cont_area_data:
            region.region_id = number_series.get_id()
        
        if progress_callback:
            progress_callback(100, 100)
        return (cont_area_image, cont_area_data)
    
    @staticmethod
    def generate_dens_samps(
        boundary_image: NDArray[np.uint8],
        cont_area_image: NDArray[np.uint8],
        cont_area_data: list[RegionMetadata],
        pixels_per_land_dens_samp: int,
        pixels_per_water_dens_samp: int,
        rng_seed: int = config.DEFAULT_DENS_SAMPS_RNG_SEED,
        lloyd_iterations: int = config.LLOYD_ALGO_ITERATIONS_DEFAULT,
        progress_callback: PROGRESS_CALLBACK = None,
    ) -> tuple[NDArray[np.uint8], list[RegionMetadata]]:
        """
        Generate density samples (subregions) within continuous areas.

        Args:
            boundary_image: Numpy array of the boundary image.
            cont_area_image: Numpy array of the continuous area image.
            cont_area_data: List of RegionMetadata for continuous areas.
            pixels_per_land_dens_samp: Target pixels per land density sample.
            pixels_per_water_dens_samp: Target pixels per water density sample.
            rng_seed: Random seed for reproducibility.
            lloyd_iterations: Number of Lloyd's algorithm iterations.
            progress_callback: Optional callback for progress updates.  
        """
        def dens_samp_progress(current: int, total: int) -> None:
            if progress_callback:
                # Map progress (0-100) to overall progress (0-90)
                progress_callback(int((current / total) * 90), 100)

        dens_samp_image, dens_samp_data = convert_all_cont_areas_to_regions(
            cont_area_image=cont_area_image,
            cont_area_metadata=cont_area_data,
            density_image=boundary_image,
            pixels_per_land_region=pixels_per_land_dens_samp,
            pixels_per_water_region=pixels_per_water_dens_samp,
            fn_new_number_series=lambda area_meta: NumberSeries(
                f"{area_meta.region_id}-TEMP", config.SERIES_ID_START, config.SERIES_ID_END
            ),
            rng_seed=rng_seed,
            lloyd_iterations=lloyd_iterations,
            override_density_multiplier=True,
            tqdm_description="Generating density samples from areas",
            tqdm_unit="areas",
            progress_callback=dens_samp_progress,
        )

        if progress_callback:
            progress_callback(90, 100)

        # Assign proper region_ids
        number_series = NumberSeries(config.DENS_SAMP_ID_PREFIX, config.SERIES_ID_START, config.SERIES_ID_END)
        for dens_samp in dens_samp_data:
            dens_samp.region_id = number_series.get_id()

        if progress_callback:
            progress_callback(100, 100)
        return (dens_samp_image, dens_samp_data)
    
    @staticmethod
    def generate_territories(
        boundary_image: NDArray[np.uint8],
        dens_samp_image: NDArray[np.uint8],
        dens_samp_data: list[RegionMetadata],
        pixels_per_land_territory: int,
        pixels_per_water_territory: int,
        rng_seed: int = config.DEFAULT_TERRITORIES_RNG_SEED,
        lloyd_iterations: int = config.LLOYD_ALGO_ITERATIONS_DEFAULT,
        progress_callback: PROGRESS_CALLBACK = None,
    ) -> tuple[NDArray[np.uint8], list[RegionMetadata]]:
        """
        Generate territories from density samples.

        Args:
            boundary_image: Numpy array of the boundary image.
            dens_samp_image: Numpy array of the density sample image.
            dens_samp_data: List of RegionMetadata for density samples.
            pixels_per_land_territory: Target pixels per land territory.
            pixels_per_water_territory: Target pixels per water territory.
            rng_seed: Random seed for reproducibility.
            lloyd_iterations: Number of Lloyd's algorithm iterations.
            progress_callback: Optional callback for progress updates.
        """
        def territory_progress(current: int, total: int) -> None:
            if progress_callback:
                # Map progress (0-100) to overall progress (0-90)
                progress_callback(int((current / total) * 90), 100)
        
        territory_image, territory_data = convert_all_cont_areas_to_regions(
            cont_area_image=dens_samp_image,
            cont_area_metadata=dens_samp_data,
            density_image=boundary_image,
            pixels_per_land_region=pixels_per_land_territory,
            pixels_per_water_region=pixels_per_water_territory,
            fn_new_number_series=lambda dens_samp_meta: NumberSeries(
                f"{dens_samp_meta.region_id}-TEMP", config.SERIES_ID_START, config.SERIES_ID_END
            ),
            rng_seed=rng_seed,
            lloyd_iterations=lloyd_iterations,
            override_density_multiplier=False,
            tqdm_description="Generating territories from density samples",
            tqdm_unit="density samples",
            progress_callback=territory_progress,
        )

        if progress_callback:
            progress_callback(90, 100)

        # Assign proper region_ids        
        number_series = NumberSeries(config.TERRITORY_ID_PREFIX, config.SERIES_ID_START, config.SERIES_ID_END)
        for territory in territory_data:
            territory.region_id = number_series.get_id()
        
        if progress_callback:
            progress_callback(100, 100)
        return (territory_image, territory_data)

    @staticmethod
    def generate_provinces(
        boundary_image: NDArray[np.uint8],
        territory_image: NDArray[np.uint8],
        territory_data: list[RegionMetadata],
        pixels_per_land_province: int,
        pixels_per_water_province: int,
        rng_seed: int = config.DEFAULT_PROVINCES_RNG_SEED,
        lloyd_iterations: int = config.LLOYD_ALGO_ITERATIONS_DEFAULT,
        progress_callback: PROGRESS_CALLBACK = None,
    ) -> tuple[NDArray[np.uint8], list[RegionMetadata]]:
        """
        Generate provinces from territories.

        Args:
            boundary_image: Numpy array of the boundary image.
            territory_image: Numpy array of the territory image.
            territory_data: List of RegionMetadata for territories.
            pixels_per_land_province: Target pixels per land province.
            pixels_per_water_province: Target pixels per water province.
            rng_seed: Random seed for reproducibility.
            lloyd_iterations: Number of Lloyd's algorithm iterations.
            progress_callback: Optional callback for progress updates.
        """
        def province_progress(current: int, total: int) -> None:
            if progress_callback:
                # Map progress (0-100) to overall progress (0-90)
                progress_callback(int((current / total) * 90), 100)
        
        province_image, province_data = convert_all_cont_areas_to_regions(
            cont_area_image=territory_image,
            cont_area_metadata=territory_data,
            density_image=boundary_image,
            pixels_per_land_region=pixels_per_land_province,
            pixels_per_water_region=pixels_per_water_province,
            fn_new_number_series=lambda territory_meta: NumberSeries(
                f"{territory_meta.region_id}-TEMP", config.SERIES_ID_START, config.SERIES_ID_END
            ),
            rng_seed=rng_seed,
            lloyd_iterations=lloyd_iterations,
            override_density_multiplier=False,
            tqdm_description="Generating provinces from territories",
            tqdm_unit="territories",
            progress_callback=province_progress,
        )
        
        if progress_callback:
            progress_callback(90, 100)
        
        # Assign proper region_ids
        number_series = NumberSeries(config.PROVINCE_ID_PREFIX, config.SERIES_ID_START, config.SERIES_ID_END)
        for province in province_data:
            province.region_id = number_series.get_id()

        if progress_callback:
            progress_callback(100, 100)
        return (province_image, province_data)
    

@grepr_dataclass(init=False)
class ProcessMapTool:
    """
    Open Grand Strategy Map Tool, which can be directly used in Python.
    Provides a single all-inclusive generation method to be called on a created instance.
    Supports event listeners after each generation step.
    """
    class_image: NDArray[np.uint8]
    boundary_image: NDArray[np.uint8]
    pixels_per_land_territory: int
    pixels_per_water_territory: int
    pixels_per_land_province: int
    pixels_per_water_province: int
    lloyd_iterations: int
    cont_areas_rng_seed: int
    dens_samps_rng_seed: int
    territories_rng_seed: int
    provinces_rng_seed: int
    progress_callback: PROGRESS_CALLBACK = None

    def __init__(self,
            class_image: Image.Image,
            boundary_image: Image.Image,
            pixels_per_land_dens_samp: int = config.PIXELS_PER_LAND_DENS_SAMP_DEFAULT,
            pixels_per_water_dens_samp: int = config.PIXELS_PER_WATER_DENS_SAMP_DEFAULT,
            pixels_per_land_territory: int = config.PIXELS_PER_LAND_TERRITORY_DEFAULT,
            pixels_per_water_territory: int = config.PIXELS_PER_WATER_TERRITORY_DEFAULT,
            pixels_per_land_province: int = config.PIXELS_PER_LAND_PROVINCE_DEFAULT,
            pixels_per_water_province: int = config.PIXELS_PER_WATER_PROVINCE_DEFAULT, # 1/5th
            lloyd_iterations: int = config.LLOYD_ALGO_ITERATIONS_DEFAULT,
            cont_areas_rng_seed: int = config.DEFAULT_CONT_AREAS_RNG_SEED,
            dens_samps_rng_seed: int = config.DEFAULT_DENS_SAMPS_RNG_SEED,
            territories_rng_seed: int = config.DEFAULT_TERRITORIES_RNG_SEED,
            provinces_rng_seed: int = config.DEFAULT_PROVINCES_RNG_SEED,
            progress_callback: PROGRESS_CALLBACK = None,
        ) -> None:
        """
        Args:
            class_image: **CLEANED** PIL Image containing land/ocean/lake classification (see StepMapTool.clean_class_image)
            boundary_image: **CLEANED** PIL Image containing (country) boundaries (see StepMapTool.clean_boundary_image)
            pixels_per_land_dens_samp: Approximate pixels per land dens_samp
            pixels_per_water_dens_samp: Approximate pixels per water dens_samp
            pixels_per_land_territory: Approximate pixels per land territory
            pixels_per_water_territory: Approximate pixels per water territory
            pixels_per_land_province: Approximate pixels per land province
            pixels_per_water_province: Approximate pixels per water province
            lloyd_iterations: Number of Lloyd's algorithm iterations for province and territory generation 
            cont_areas_rng_seed: RNG seed used for continuous area generation
            dens_samps_rng_seed: RNG seed used for dens_samp generation
            territories_rng_seed: RNG seed used for territory generation
            provinces_rng_seed: RNG seed used for province generation
            progress_callback: Optional callback for progress updates
        """
        super().__init__()

        self.class_image = np.array(class_image.convert("RGBA"))
        self.boundary_image = np.array(boundary_image.convert("RGBA"))
        self.pixels_per_land_dens_samp = pixels_per_land_dens_samp
        self.pixels_per_water_dens_samp = pixels_per_water_dens_samp
        self.pixels_per_land_territory = pixels_per_land_territory
        self.pixels_per_water_territory = pixels_per_water_territory
        self.pixels_per_land_province = pixels_per_land_province
        self.pixels_per_water_province = pixels_per_water_province
        self.lloyd_iterations = lloyd_iterations
        self.cont_areas_rng_seed = cont_areas_rng_seed
        self.dens_samps_rng_seed = dens_samps_rng_seed
        self.territories_rng_seed = territories_rng_seed
        self.provinces_rng_seed = provinces_rng_seed
        self.progress_callback = progress_callback or (lambda num, denom: None)
   
    def generate(self) -> MapToolResult:
        """
        Generate province and territory maps from stored input images.
        Calls event listener methods on completing a map.
        
        This method orchestrates the full map generation pipeline:
        1. Converts boundaries to continuous areas
        2. Generates density samples from continuous areas
        3. Generates territories from density samples
        4. Generates provinces from territories
        """
        cont_area_image_buffer, cont_area_data = StepMapTool.generate_cont_areas(
            self.class_image, self.boundary_image, self.cont_areas_rng_seed,
            progress_callback=lambda num, denom: self.progress_callback(round(0 + (num/denom)*25), 100),
        )
        cont_area_image = Image.fromarray(cont_area_image_buffer)
        if callable(getattr(self, "on_cont_areas_generated", None)):
            self.on_cont_areas_generated(cont_area_image, cont_area_image_buffer, cont_area_data)
        
        dens_samp_image_buffer, dens_samp_data = StepMapTool.generate_dens_samps(
            self.boundary_image, cont_area_image_buffer, cont_area_data,
            self.pixels_per_land_dens_samp, self.pixels_per_water_dens_samp,
            self.dens_samps_rng_seed, self.lloyd_iterations,
            progress_callback=lambda num, denom: self.progress_callback(round(25 + (num/denom)*25), 100),
        )
        dens_samp_image = Image.fromarray(dens_samp_image_buffer)
        if callable(getattr(self, "on_dens_samps_generated", None)):
            self.on_dens_samps_generated(dens_samp_image, dens_samp_image_buffer, dens_samp_data)
        
        territory_image_buffer, territory_data = StepMapTool.generate_territories(
            self.boundary_image, dens_samp_image_buffer, dens_samp_data,
            self.pixels_per_land_territory, self.pixels_per_water_territory,
            self.territories_rng_seed, self.lloyd_iterations,
            progress_callback=lambda num, denom: self.progress_callback(round(50 + (num/denom)*25), 100),
        )
        territory_image = Image.fromarray(territory_image_buffer)
        if callable(getattr(self, "on_territories_generated", None)):
            self.on_territories_generated(territory_image, territory_image_buffer, territory_data)
        
        province_image_buffer, province_data = StepMapTool.generate_provinces(
            self.boundary_image, territory_image_buffer, territory_data,
            self.pixels_per_land_province, self.pixels_per_water_province,
            self.provinces_rng_seed, self.lloyd_iterations,
            progress_callback=lambda num, denom: self.progress_callback(round(75 + (num/denom)*25), 100),
        )
        province_image = Image.fromarray(province_image_buffer)
        if callable(getattr(self, "on_provinces_generated", None)):
            self.on_provinces_generated(province_image, province_image_buffer, province_data)

        return MapToolResult(
            cont_area_image, cont_area_data,
            dens_samp_image, dens_samp_data,
            territory_image, territory_data,
             province_image,  province_data,
        )

    def on_cont_areas_generated(self,
            cont_area_image: Image.Image,
            cont_area_image_buffer: NDArray[np.uint8],
            cont_area_data: list[RegionMetadata],
        ) -> None: ...
    def on_dens_samps_generated(self,
            dens_samp_image: Image.Image,
            dens_samp_image_buffer: NDArray[np.uint8],
            dens_samp_data: list[RegionMetadata],
        ) -> None: ...
    def on_territories_generated(self,
            territory_image: Image.Image,
            territory_image_buffer: NDArray[np.uint8],
            territory_data: list[RegionMetadata],
        ) -> None: ...
    def on_provinces_generated(self,
            province_image: Image.Image,
            province_image_buffer: NDArray[np.uint8],
            province_data: list[RegionMetadata],
        ) -> None: ...


@grepr_dataclass(validate=False, frozen=True)
class MapToolResult:
    """
    Dataclass Containing Results of the Map Tool
    - continuous areas map
    - density samples, territory and province maps
    - data of continuous areas, density samples, territories & provinces 
    """
    cont_area_image: Image.Image
    cont_area_data: list[RegionMetadata]
    dens_samp_image: Image.Image
    dens_samp_data: list[RegionMetadata]
    territory_image: Image.Image
    territory_data: list[RegionMetadata]
    province_image: Image.Image
    province_data: list[RegionMetadata]
