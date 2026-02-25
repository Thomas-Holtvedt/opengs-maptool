from gceutils import grepr_dataclass
from multiprocessing import Pool, cpu_count
import numpy as np
from numpy.typing import NDArray
from tqdm import tqdm
from typing import Callable

from opengs_maptool.logic.utils import (
    NumberSeries, ColorSeries, RegionMetadata,
    poisson_disk_samples, lloyd_relaxation, assign_regions, build_metadata, hex_to_rgb,
    defragment_regions, get_area_pixel_mask,
    calculate_density_multiplier, ensure_point_in_mask,
)


@grepr_dataclass(validate=False, frozen=True)
class AreaProcessingArgs:
    """
    Arguments for processing a single continuous area into regions.
    Args:
        parent_area: Metadata for this area
        cont_area_image: Continuous areas image
        density_image: Greyscale density image used for density multiplier calculations
        pixels_per_land_region: Average pixels per region for land areas
        pixels_per_water_region: Average pixels per region for ocean/lake areas
        filter_color: RGBA color to filter for
        number_series: NumberSeries for generating region IDs
        color_series: ColorSeries instance for generating unique colors per process
        poisson_rng_seed: RNG seed for Poisson disk sampling
        lloyd_rng_seed: RNG seed for Lloyd relaxation
        lloyd_iterations: Number of Lloyd relaxation iterations
        override_density_multiplier: Use own average density instead of parent density
    """
    parent_area: RegionMetadata
    cont_area_image: NDArray[np.uint8]
    density_image: NDArray[np.uint8] | None
    pixels_per_land_region: int
    pixels_per_water_region: int
    filter_color: tuple[int, int, int, int]
    number_series: NumberSeries
    color_series: ColorSeries
    poisson_rng_seed: np.random.SeedSequence
    lloyd_rng_seed: np.random.SeedSequence
    lloyd_iterations: int
    override_density_multiplier: bool

def convert_all_cont_areas_to_regions(
        cont_area_image: NDArray[np.uint8],
        cont_area_metadata: list[RegionMetadata],
        density_image: NDArray[np.uint8] | None,
        pixels_per_land_region: int,
        pixels_per_water_region: int,
        fn_new_number_series: Callable[[RegionMetadata], NumberSeries],
        rng_seed: int,
        lloyd_iterations: int,
        override_density_multiplier: bool = False,
        num_processes: int | None = None,
        tqdm_description: str = "Converting areas to regions",
        tqdm_unit: str = "area",
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[NDArray[np.uint8], list[RegionMetadata]]:
    """
    Convert all continuous areas into regions and combine into a single image.
    Uses multiprocessing to parallelize processing of independent areas.
    Each process gets its own ColorSeries instance seeded uniquely to avoid color collisions.
    
    Args:
        cont_area_image: Continuous areas image
        cont_area_metadata: Metadata list with area colors
        density_image: Optional greyscale density image for density multiplier calculations
        pixels_per_land_region: Average pixels per region for land areas
        pixels_per_water_region: Average pixels per region for ocean/lake areas
        fn_new_number_series: A function to produce a new number series
        rng_seed: Master RNG seed for color series seeding
        lloyd_iterations: Number of iterations for Lloyd relaxation
        override_density_multiplier: Use region average density instead of parent density
        num_processes: Number of processes to use. If None, uses number of CPU cores
        tqdm_description: Description for tqdm progress bar
        tqdm_unit: Unit name for tqdm progress bar
        progress_callback: Optional callback function for progress updates
    
    Returns:
        Tuple of (combined_image, combined_metadata) where:
        - combined_image: Full-size region image (same dimensions as input)
        - combined_metadata: Flattened list of all region metadata
    """    
    if num_processes is None:
        num_processes = cpu_count()
        
    # Prepare arguments for each area
    ss = np.random.SeedSequence(rng_seed)
    color_seeds = ss.spawn(len(cont_area_metadata))
    lloyd_seeds = ss.spawn(len(cont_area_metadata))
    poisson_seeds = ss.spawn(len(cont_area_metadata))
    
    task_args = [
        AreaProcessingArgs(
            parent_area=parent_area,
            cont_area_image=cont_area_image,
            density_image=density_image,
            pixels_per_land_region=pixels_per_land_region,
            pixels_per_water_region=pixels_per_water_region,
            filter_color=(*hex_to_rgb(parent_area.color), 255),
            number_series=fn_new_number_series(parent_area),
            color_series=ColorSeries(color_seed, exclude_values=[(0, 0, 0)]),
            poisson_rng_seed=poisson_seed,
            lloyd_rng_seed=lloyd_seed,
            lloyd_iterations=lloyd_iterations,
            override_density_multiplier=override_density_multiplier,
        )
        for parent_area, color_seed, poisson_seed, lloyd_seed 
        in zip(cont_area_metadata, color_seeds, poisson_seeds, lloyd_seeds)
    ]
    
    # Process areas in parallel with progress bar
    with Pool(num_processes) as pool:
        tqdm_iter = tqdm(
            pool.imap_unordered(convert_cont_area_to_regions, task_args),
            total=len(cont_area_metadata),
            desc=tqdm_description,
            unit=tqdm_unit,
        )
        results = [
            (result, progress_callback(i, len(cont_area_metadata)))[0] # keep result, call progress callback
            for i, result in enumerate(tqdm_iter, 1)
        ]
    

    h, w = cont_area_image.shape[:2]
    combined_image = np.zeros((h, w, 4), dtype=np.uint8)
    combined_metadata = []
    existing_colors = set()

    # Combine results
    for region_image, region_metadata, bbox, color_series in results:
        if bbox is not None and len(region_metadata) > 0:
            x_min, y_min, x_max, y_max = bbox
            
            # Check for color collisions and replace with new colors
            updated_region_metadata = []
            for region in region_metadata:
                color_hex = region.color
                
                # If color collision detected, find a new color
                while color_hex in existing_colors:
                    new_color_rgb, new_color_hex = color_series.get_color_rgb_hex(is_water=(region.region_type != "land"))
                    r_old, g_old, b_old = hex_to_rgb(color_hex)
                    r_new, g_new, b_new = new_color_rgb
                    region.color = new_color_hex
                    
                    # Update region_image pixels with new color
                    old_rgb = np.array([r_old, g_old, b_old], dtype=np.uint8)
                    mask_old = np.all(region_image[:, :, :3] == old_rgb, axis=2)
                    region_image[mask_old] = [r_new, g_new, b_new, 255]

                    color_hex = new_color_hex
                
                existing_colors.add(color_hex)
                
                # local fields are guaranteed to not be None for these regions:
                region.global_bbox = ( 
                    region.local_bbox[0] + x_min,
                    region.local_bbox[1] + y_min,
                    region.local_bbox[2] + x_min,
                    region.local_bbox[3] + y_min,
                )
                region.global_center = (
                    region.local_center[0] + x_min,
                    region.local_center[1] + y_min,
                )
                region.global_seed = [
                    region.local_seed[0] + x_min,
                    region.local_seed[1] + y_min,
                ]
                
                updated_region_metadata.append(region)
            
            # Only copy pixels with alpha > 0 to avoid overwriting with transparency
            alpha_mask = region_image[:, :, 3] > 0
            combined_image[y_min:(y_max+1), x_min:(x_max+1)][alpha_mask] = region_image[alpha_mask]
            combined_metadata.extend(updated_region_metadata)
    
    return combined_image, combined_metadata

def convert_cont_area_to_regions(args: AreaProcessingArgs) -> tuple[
        NDArray[np.uint8], list[RegionMetadata], 
        tuple[int, int, int, int] | None, ColorSeries,
    ]:
    """
    Convert a single continuous area (usually a country) into an image of regions.
    Args: see AreaProcessingArgs dataclass.
    """
    # Mask a single country based on filter color
    exact_color = np.array(args.filter_color, dtype=np.uint8)
    mask = np.all(args.cont_area_image == exact_color, axis=2)

    # Find bounding box and crop to region (MUCH faster Lloyd on small regions)
    rows, cols = np.where(mask)
    if len(rows) == 0:
        return np.zeros((10, 10, 4), dtype=np.uint8), [], None, args.color_series
    
    y_min, y_max = int(rows.min()), int(rows.max())
    x_min, x_max = int(cols.min()), int(cols.max())
    bbox = (x_min, y_min, x_max, y_max)
    cropped_mask = mask[y_min:(y_max+1), x_min:(x_max+1)]
    
    region_type = args.parent_area.region_type
    pixel_count = args.parent_area.pixel_count
    pixels_per_region = args.pixels_per_land_region if (region_type == "land") else args.pixels_per_water_region
    
    # Compute average density for the whole parent area to calculate subdivision count
    if args.override_density_multiplier:
        density_src = args.density_image[y_min:(y_max+1), x_min:(x_max+1)]
        density_mask = cropped_mask & get_area_pixel_mask(density_src, threshold=0)
        density_multiplier = calculate_density_multiplier(
            density_src,
            mask=density_mask,
            region_id=args.parent_area.region_id,
            use_rgb_average=True,
        )
    else:
        density_multiplier = args.parent_area.density_multiplier or 1.0
    
    # Calculate regions: areas smaller than 0.5 regions get 0 territories (skip them)
    num_subdivision_regions = max(1, round(pixel_count / pixels_per_region * density_multiplier))

    # Optimization: if only one region, assign entire area to it
    if num_subdivision_regions == 1:
        region_id = args.number_series.get_id()
        color_rgb, color_hex = args.color_series.get_color_rgb_hex(is_water=(region_type != "land"))
                
        # Compute centroid of entire area
        cx = round(float(np.mean(cols)))
        cy = round(float(np.mean(rows)))
        
        # Adjust centroid to cropped coordinates
        cx_cropped = cx - x_min
        cy_cropped = cy - y_min
        cx_cropped, cy_cropped = ensure_point_in_mask(cropped_mask, cx_cropped, cy_cropped)

        # Store center as rounded integer pixel coordinates
        cx_cropped = int(round(cx_cropped))
        cy_cropped = int(round(cy_cropped))
        seed_x = cx_cropped
        seed_y = cy_cropped

        # Create Single Region (e.g. Territory or Province) within its parent
        metadata = [RegionMetadata(
            region_id=region_id,
            region_type=region_type,
            color=color_hex,
            pixel_count=pixel_count,
            density_multiplier=round(density_multiplier, ndigits=2), # Can be kept as region has same pixels as parent area
            parent_id=args.parent_area.region_id,
            local_bbox=(0, 0, x_max - x_min, y_max - y_min), # full cropped area
            local_center=(cx_cropped, cy_cropped),
            local_seed=(seed_x, seed_y),
            global_bbox=None,  # Set later
            global_center=None, # Set later
            global_seed=None, # Set later
        )]
        
        # Fill only masked pixels with single region color
        h, w = cropped_mask.shape
        cropped_image = np.zeros((h, w, 4), dtype=np.uint8)
        cropped_image[cropped_mask] = [*color_rgb, 255]
        
        return cropped_image, metadata, bbox, args.color_series
    
    # Use grid-based seeding for large areas to improve distribution
    seeds = poisson_disk_samples(
        cropped_mask,
        num_subdivision_regions,
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

    # Detect and fix territories split e.g. by narrow passages
    pmap = defragment_regions(pmap, cropped_mask)
    
    metadata = build_metadata(
        pmap, seeds, 0, region_type, args.number_series, args.color_series,
        parent_id=args.parent_area.region_id,
        parent_density_multiplier=args.parent_area.density_multiplier or 1.0,
    )

    # For density samples, compute average density **per generated region** from the density image.
    if args.override_density_multiplier:
        for i, region_meta in enumerate(metadata):
            region_density_multiplier = calculate_density_multiplier(
                density_src,
                mask=(pmap == i) & density_mask,
                region_id=args.parent_area.region_id,
                use_rgb_average=True,
            )

            region_meta.density_multiplier = round(region_density_multiplier, ndigits=2)
    
    # Convert province map to colored image
    h, w = cropped_mask.shape
    cropped_image = np.zeros((h, w, 4), dtype=np.uint8)
    
    if metadata:
        color_lut = np.array([[*hex_to_rgb(d.color), 255] for d in metadata], dtype=np.uint8)
        valid = pmap >= 0
        cropped_image[valid] = color_lut[pmap[valid]]
    
    return cropped_image, metadata, bbox, args.color_series

