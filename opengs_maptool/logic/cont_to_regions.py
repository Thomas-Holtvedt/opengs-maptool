import numpy as np
from numpy.typing import NDArray
from typing import Any, Callable
from gceutils import grepr_dataclass
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
from logic.utils import (
    NumberSeries, ColorSeries,
    poisson_disk_samples, lloyd_relaxation, assign_regions, build_metadata, hex_to_rgb,
    round_float, round_bbox, defragment_regions,
)
import opengs_maptool.config as config


@grepr_dataclass(validate=False, frozen=True)
class AreaProcessingArgs:
    """
    Arguments for processing a single continuous area into regions.
    Args:
        cont_areas_image: Continuous areas image
        class_image: Type/classification image
        class_counts: Pixel counts per type
        pixels_per_land_region: Average pixels per region for land areas
        pixels_per_water_region: Average pixels per region for ocean/lake areas
        filter_color: RGBA color to filter for
        number_series: NumberSeries for generating region IDs
        color_series: ColorSeries instance for generating unique colors per process
        poisson_rng_seed: RNG seed for Poisson disk sampling
        lloyd_rng_seed: RNG seed for Lloyd relaxation
    """
    area_meta: dict[str, Any]
    cont_areas_image: NDArray[np.uint8]
    class_image: NDArray[np.uint8]
    class_counts: dict[str, int]
    pixels_per_land_region: int
    pixels_per_water_region: int
    filter_color: tuple[int, int, int, int]
    number_series: NumberSeries
    color_series: ColorSeries
    poisson_rng_seed: int
    lloyd_rng_seed: int
    lloyd_iterations: int


def convert_all_cont_areas_to_regions(
        cont_areas_image: NDArray[np.uint8],
        cont_areas_metadata: list[dict[str, Any]],
        class_image: NDArray[np.uint8],
        class_counts: dict[str, int],
        pixels_per_land_region: int,
        pixels_per_water_region: int,
        fn_new_number_series: Callable[[dict[str, Any]], NumberSeries],
        rng_seed: int,
        lloyd_iterations: int,
        num_processes: int | None = None,
        tqdm_description: str = "Converting areas to regions",
        tqdm_unit: str = "area",
        progress_callback=None,
    ) -> tuple[NDArray[np.uint8], list[dict[str, Any]]]:
    """
    Convert all continuous areas into regions and combine into a single image.
    Uses multiprocessing to parallelize processing of independent areas.
    Each process gets its own ColorSeries instance seeded uniquely to avoid color collisions.
    
    Args:
        cont_areas_image: Continuous areas image (from convert_boundaries_to_cont_areas)
        cont_areas_metadata: Metadata list with area colors (from convert_boundaries_to_cont_areas)
        class_image: Type/classification image
        class_counts: Pixel counts per type
        pixels_per_land_region: Average pixels per region for land areas
        pixels_per_water_region: Average pixels per region for ocean/lake areas
        fn_new_number_series: A function to produce a new number series
        rng_seed: Master RNG seed for color series seeding
        lloyd_iterations: Number of iterations for Lloyd relaxation
        num_processes: Number of processes to use. If None, uses number of CPU cores
    
    Returns:
        Tuple of (combined_image, combined_metadata) where:
        - combined_image: Full-size region image (same dimensions as input)
        - combined_metadata: Flattened list of all region metadata
    """    
    if num_processes is None:
        num_processes = cpu_count()
        
    # Prepare arguments for each area
    ss = np.random.SeedSequence(rng_seed)
    color_seeds = ss.spawn(len(cont_areas_metadata))
    lloyd_seeds = ss.spawn(len(cont_areas_metadata))
    poisson_seeds = ss.spawn(len(cont_areas_metadata))
    
    task_args = [
        AreaProcessingArgs(
            area_meta=area_meta,
            cont_areas_image=cont_areas_image,
            class_image=class_image,
            class_counts=class_counts,
            pixels_per_land_region=pixels_per_land_region,
            pixels_per_water_region=pixels_per_water_region,
            filter_color=(*hex_to_rgb(area_meta["color"]), 255),
            number_series=fn_new_number_series(area_meta),
            color_series=ColorSeries(color_seed, exclude_values=[(0, 0, 0)]),
            poisson_rng_seed=poisson_seed,
            lloyd_rng_seed=lloyd_seed,
            lloyd_iterations=lloyd_iterations,
        )
        for area_meta, color_seed, poisson_seed, lloyd_seed 
        in zip(cont_areas_metadata, color_seeds, poisson_seeds, lloyd_seeds)
    ]
    
    # Process areas in parallel with progress bar
    with Pool(num_processes) as pool:
        tqdm_iter = tqdm(
            pool.imap_unordered(convert_cont_area_to_regions, task_args),
            total=len(cont_areas_metadata),
            desc=tqdm_description,
            unit=tqdm_unit,
        )
        results = []
        for i, result in enumerate(tqdm_iter, 1):
            results.append(result)
            if progress_callback:
                progress_callback(i, len(cont_areas_metadata))
    

    h, w = cont_areas_image.shape[:2]
    combined_image = np.zeros((h, w, 4), dtype=np.uint8)
    combined_metadata = []
    existing_colors = set()

    # Combine results
    for region_image, region_metadata, bbox, color_series in results:
        if bbox is not None and len(region_metadata) > 0:
            y_min, y_max, x_min, x_max = bbox
            
            # Check for color collisions and replace with new colors
            updated_region_metadata = []
            for region in region_metadata:
                color_hex = region["color"]
                
                # If color collision detected, find a new color
                while color_hex in existing_colors:
                    new_color_rgb, new_color_hex = color_series.get_color_rgb_hex(is_water=(region["region_type"] != "land"))
                    r_old, g_old, b_old = hex_to_rgb(color_hex)
                    r_new, g_new, b_new = new_color_rgb
                    region["color"] = new_color_hex
                    
                    # Update region_image pixels with new color
                    old_rgb = np.array([r_old, g_old, b_old], dtype=np.uint8)
                    mask_old = np.all(region_image[:, :, :3] == old_rgb, axis=2)
                    region_image[mask_old] = [r_new, g_new, b_new, 255]

                    color_hex = new_color_hex
                
                existing_colors.add(color_hex)
                
                # Calculate global coordinates from local coordinates
                region["global_x"] = round_float(region["local_x"] + x_min, 2)
                region["global_y"] = round_float(region["local_y"] + y_min, 2)
                if region.get("bbox_local") is not None:
                    bx0, by0, bx1, by1 = region["bbox_local"]
                    region["bbox"] = round_bbox(
                        [
                            float(bx0 + x_min),
                            float(by0 + y_min),
                            float(bx1 + x_min),
                            float(by1 + y_min),
                        ],
                        0,
                    )
                
                updated_region_metadata.append(region)
            
            # Only copy pixels with alpha > 0 to avoid overwriting with transparency
            alpha_mask = region_image[:, :, 3] > 0
            combined_image[y_min:y_max, x_min:x_max][alpha_mask] = region_image[alpha_mask]
            combined_metadata.extend(updated_region_metadata)
    
    return combined_image, combined_metadata

def convert_cont_area_to_regions(args: AreaProcessingArgs) -> tuple[
        NDArray[np.uint8], list[dict[str, Any]], 
        tuple[int, int, int, int] | None, ColorSeries,
    ]:
    """
    Convert a single continuous area (usually a country) into an image of regions.
    Args: see AreaProcessingArgs dataclass.
    """
    # Mask a single country based on filter color
    exact_color = np.array(args.filter_color, dtype=np.uint8)
    mask = np.all(args.cont_areas_image == exact_color, axis=2)

    # Find bounding box and crop to region (MUCH faster Lloyd on small regions)
    rows, cols = np.where(mask)
    if len(rows) == 0:
        return np.zeros((10, 10, 4), dtype=np.uint8), [], None, args.color_series
    
    y_min, y_max = rows.min(), rows.max() + 1
    x_min, x_max = cols.min(), cols.max() + 1
    bbox = (y_min, y_max, x_min, x_max)
    cropped_mask = mask[y_min:y_max, x_min:x_max]
    cropped_class_image = args.class_image[y_min:y_max, x_min:x_max]

    # Determine area type by checking the most common type in this area
    ocean_color = np.array(config.OCEAN_COLOR, dtype=np.uint8)
    lake_color = np.array(config.LAKE_COLOR, dtype=np.uint8)
    land_color = np.array(config.LAND_COLOR, dtype=np.uint8)
    
    # Get only RGB channels (first 3) for comparison
    cropped_rgb = cropped_class_image[:, :, :3]
    
    ocean_pixels = np.sum(np.all(cropped_rgb[cropped_mask] == ocean_color, axis=1))
    lake_pixels = np.sum(np.all(cropped_rgb[cropped_mask] == lake_color, axis=1))
    water_pixels = ocean_pixels + lake_pixels
    land_pixels = np.sum(np.all(cropped_rgb[cropped_mask] == land_color, axis=1))
    
    # Determine predominant type and calculate number of regions
    if land_pixels > water_pixels:
        area_type = "land"
        pixels_per_region = args.pixels_per_land_region
        pixel_count = land_pixels
    else:
        area_type = "ocean" if ocean_pixels > lake_pixels else "lake"
        pixels_per_region = args.pixels_per_water_region
        pixel_count = water_pixels
    
    # Apply density multiplier from boundary metadata
    density_multiplier = args.area_meta.get("density_multiplier", 1.0)
    
    # Calculate regions: areas smaller than 0.5 regions get 0 territories (skip them)
    num_area_regions = max(1, round(pixel_count / pixels_per_region * density_multiplier))
        
    # Skip this area if it's too small to warrant any regions
    if num_area_regions == 0:
        return np.zeros((10, 10, 4), dtype=np.uint8), [], None, args.color_series
    
    # Optimization: if only one region, assign entire area to it
    if num_area_regions == 1:
        region_id = args.number_series.get_id()
        color_rgb, color_hex = args.color_series.get_color_rgb_hex(is_water=(area_type != "land"))
                
        # Compute centroid of entire area
        cx = float(np.mean(cols))
        cy = float(np.mean(rows))
        
        # Adjust centroid to cropped coordinates
        cx_cropped = cx - x_min
        cy_cropped = cy - y_min
        
        # Bbox as integers: add 1 to max values to include the last pixel (exclusive end bound)
        local_bbox = [
            int(cols.min() - x_min),
            int(rows.min() - y_min),
            int(cols.max() - x_min) + 1,
            int(rows.max() - y_min) + 1,
        ]

        cx_cropped = round_float(cx_cropped, 2)
        cy_cropped = round_float(cy_cropped, 2)
        local_bbox = round_bbox(local_bbox, 0)

        metadata = [{
            "region_type": area_type,
            "region_id": region_id,
            "parent_id": args.area_meta["region_id"],
            "color": color_hex,
            "local_x": cx_cropped,
            "local_y": cy_cropped,
            "global_x": None, # Set later
            "global_y": None,
            "bbox_local": local_bbox,
            "bbox": None,  # Set later (global bbox)
            "density_multiplier": density_multiplier,
        }]
        
        # Fill only masked pixels with single region color
        h, w = cropped_mask.shape
        cropped_image = np.zeros((h, w, 4), dtype=np.uint8)
        cropped_image[cropped_mask] = [*color_rgb, 255]
        
        return cropped_image, metadata, bbox, args.color_series
    
    seeds = poisson_disk_samples(
        cropped_mask,
        num_area_regions,
        rng_seed=args.poisson_rng_seed,
        min_dist=None,
        k=30,
        border_margin=0.0,
        no_distance_limit=True,
    )
    
    if not seeds:
        return np.zeros((10, 10, 4), dtype=np.uint8), [], None, args.color_series
    
    # Use Lloyd relaxation on the seeds for better spacing
    seeds = lloyd_relaxation(
        mask=cropped_mask,
        point_seeds=seeds,
        rng_seed=args.lloyd_rng_seed,
        iterations=args.lloyd_iterations,
        boundary_mask=None,
    )
    
    pmap = assign_regions(cropped_mask, seeds, start_index=0)
    
    # Detect and fix territories split by narrow passages
    pmap = defragment_regions(pmap, cropped_mask, seeds, size_threshold=100)
    
    metadata = build_metadata(
        pmap, seeds, 0, area_type, args.number_series, args.color_series,
        parent_id=args.area_meta["region_id"],
        parent_density_multiplier=args.area_meta.get("density_multiplier", 1.0)
    )
    
    # Convert province map to colored image
    h, w = cropped_mask.shape
    cropped_image = np.zeros((h, w, 4), dtype=np.uint8)
    
    if metadata:
        color_lut = np.array([[*hex_to_rgb(d["color"]), 255] for d in metadata], dtype=np.uint8)
        valid = pmap >= 0
        cropped_image[valid] = color_lut[pmap[valid]]
    
    return cropped_image, metadata, bbox, args.color_series

