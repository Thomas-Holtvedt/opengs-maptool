import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from tqdm import tqdm
from logic.utils import ColorSeries, round_float, hex_to_rgb
import opengs_maptool.config as config

NEIGHBOR_OFFSETS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def recalculate_bboxes_from_image(
    image: NDArray[np.uint8],
    metadata: list[dict],
) -> list[dict]:
    """
    Recalculate bounding boxes for all regions from the image.
    
    This is needed when the image has been modified after metadata creation
    (e.g., after border assignment).
    
    Args:
        image: RGBA image where non-black pixels represent area colors
        metadata: List of region metadata dicts with 'color' field
    
    Returns:
        Updated metadata list with recalculated bboxes
    """
    
    updated_metadata = []
    
    for region in metadata:
        color_hex = region.get("color", "")
        try:
            color_rgb = hex_to_rgb(color_hex)
            target_color = np.array(color_rgb, dtype=np.uint8)
        except (ValueError, AttributeError):
            # Color not found, keep original bbox
            updated_metadata.append(region)
            continue
        
        # Find all pixels matching this region's color
        rgb_match = np.all(image[:, :, :3] == target_color, axis=2)
        
        if not np.any(rgb_match):
            # No pixels found, keep original bbox
            updated_metadata.append(region)
            continue
        
        # Calculate new bbox
        rows, cols = np.where(rgb_match)
        bbox_local = [
            int(cols.min()),
            int(rows.min()),
            int(cols.max()) + 1,
            int(rows.max()) + 1,
        ]
        
        # Update bbox in metadata
        region["bbox_local"] = bbox_local
        region["bbox"] = bbox_local
        updated_metadata.append(region)
    
    return updated_metadata

def classify_pixels_by_color(
    land_image: NDArray[np.uint8],
    export_colors: bool = False,
) -> tuple[NDArray[np.uint8], dict[str, int]]:
    """
    Classify each pixel as ocean (0), lake (1), or land (2) based on closest color match.
    Return classification image and count.
    
    Args:
        land_image: Input image
        export_colors: If True, return RGBA image with config colors. If False, return classification indices.
    
    Returns:
        If export_colors=False: 2D uint8 array of shape (h, w) with values: 0=ocean, 1=lake, 2=land
        If export_colors=True: RGBA image (h, w, 4) with actual config colors
    """
    
    # Reference colors from config (shape: 3, 3)
    ref_colors = np.array([
        config.OCEAN_COLOR[:3],
        config.LAKE_COLOR[:3],
        config.LAND_COLOR[:3]
    ], dtype=np.float32)
    
    # Get pixel colors (h, w, 3)
    pixels = land_image[:, :, :3].astype(np.float32)
    
    # Compute squared distances to all 3 colors at once (vectorized)
    diff = pixels[:, :, None, :] - ref_colors[None, None, :, :]
    distances_sq = np.sum(diff ** 2, axis=3)  # (h, w, 3)
    
    # Find index of minimum distance (0=ocean, 1=lake, 2=land)
    classification = np.argmin(distances_sq, axis=2).astype(np.uint8)
    
    result: NDArray[np.uint8]
    if export_colors:
        # Create color image using classification as lookup
        color_lut = np.array(
            [
                [*config.OCEAN_COLOR[:3], 255],
                [*config.LAKE_COLOR[:3], 255],
                [*config.LAND_COLOR[:3], 255],
            ],
            dtype=np.uint8,
        )
        result = color_lut[classification]
    else:
        result = classification

    counts_raw = np.bincount(classification.ravel(), minlength=3)
    counts = {
        "ocean": int(counts_raw[0]),
        "lake": int(counts_raw[1]),
        "land": int(counts_raw[2]),
    }
    return result, counts

def convert_boundaries_to_cont_areas(boundaries_image: NDArray[np.uint8], rng_seed: int, min_area_pixels: int = 50, progress_callback=None) -> tuple[NDArray[np.uint8], list[dict]]:
    """
    Convert the boundary image into an image of continuous areas(usually countries).
    
    Args:
        boundaries_image: Input boundary image
        rng_seed: Random seed for color generation
        min_area_pixels: Minimum pixel count for a continuous area to be kept (smaller areas are merged into background)
        progress_callback: Optional callback function(current, total) for progress reporting
    
    Returns:
        Tuple of (cont_areas_image, metadata) where metadata contains:
        - region_id: Region ID (1-indexed)
        - R, G, B: Area color
    """

    # Vectorized mask creation - use only R and G channels for border/area detection
    # Area detection: R and G channels are bright (ignore B channel)
    is_white: np.ndarray = (
        (boundaries_image[:, :, 3] == 255) &
        (boundaries_image[:, :, 0] > 180) &
        (boundaries_image[:, :, 1] > 180)
    )

    # Use scipy's label function for connected component analysis (rel. fast)
    white_mask = is_white.astype(np.uint8)
    labeled_array, num_features = ndimage.label(white_mask)
    
    if progress_callback:
        progress_callback(10, 100)

    # Filter out small areas
    if min_area_pixels > 0:
        region_sizes = np.bincount(labeled_array.ravel())
        small_regions = np.where(region_sizes < min_area_pixels)[0]
        for small_region in small_regions:
            if small_region > 0:  # Skip background (0)
                labeled_array[labeled_array == small_region] = 0
        
        # Relabel to have consecutive IDs
        unique_labels = np.unique(labeled_array[labeled_array > 0])
        new_labeled_array = np.zeros_like(labeled_array)
        for new_id, old_id in enumerate(unique_labels, start=1):
            new_labeled_array[labeled_array == old_id] = new_id
        labeled_array = new_labeled_array
        num_features = len(unique_labels)
    
    if progress_callback:
        progress_callback(20, 100)

    # Create image from regions using the labeled array
    regions_image = np.full((*boundaries_image.shape[:2], 4), [0, 0, 0, 255], dtype=np.uint8)
    color_series = ColorSeries(rng_seed, exclude_values=[(0, 0, 0)])
    region_to_color = {}
    metadata = []
    
    # Vectorized color assignment
    for idx, region_id in enumerate(tqdm(range(1, num_features + 1), desc="Processing boundaries into areas", unit="areas"), start=1):
        if progress_callback and idx % max(1, num_features // 20) == 0:  # Report every 5%
            progress_callback(20 + int((idx / num_features) * 80), 100)
        
        color_rgb, color_hex = color_series.get_color_rgb_hex(is_water=False)
        region_to_color[region_id] = (*color_rgb, 255)
        regions_image[labeled_array == region_id] = region_to_color[region_id]
        
        # Calculate density multiplier from B channel (0-255)
        # Sample B value from representative points in the region (center and nearby)
        region_mask = labeled_array == region_id
        rows, cols = np.where(region_mask)
        
        if len(rows) > 0:
            # Get center and nearby sample points
            center_row, center_col = int(np.median(rows)), int(np.median(cols))
            sample_points = [
                (center_row, center_col),
                (center_row, max(0, center_col - 5)),
                (center_row, min(boundaries_image.shape[1] - 1, center_col + 5)),
                (max(0, center_row - 5), center_col),
                (min(boundaries_image.shape[0] - 1, center_row + 5), center_col),
            ]
            
            # Sample B channel from these points (avoid out of bounds)
            blue_samples = []
            for r, c in sample_points:
                if 0 <= r < boundaries_image.shape[0] and 0 <= c < boundaries_image.shape[1]:
                    blue_samples.append(boundaries_image[r, c, 2])
            
            avg_blue = float(np.mean(blue_samples)) if blue_samples else 128.0
        else:
            avg_blue = 128.0
        
        # Convert B channel to density multiplier (piecewise linear)
        # B=0 (low blue) -> 0.25 (4x fewer regions)
        # B=128 (mid blue) -> 1.0 (normal)
        # B=255 (high blue) -> 4.0 (4x more regions)
        if avg_blue <= 128.0:
            density_multiplier = (avg_blue / 128) * 0.75 + 0.25
        else:
            density_multiplier = ((avg_blue - 128) / 127) * 3 + 1
        
        # Calculate center of mass (centroid) for local coordinates
        center_x = float(np.mean(cols))
        center_y = float(np.mean(rows))
        
        # BBox as integers: add 1 to max values to include the last pixel (exclusive end bound)
        bbox_local = [
            int(cols.min()),
            int(rows.min()),
            int(cols.max()) + 1,
            int(rows.max()) + 1,
        ]

        center_x = round_float(center_x, 2)
        center_y = round_float(center_y, 2)
        density_multiplier = round_float(density_multiplier, 2)

        metadata.append({
            "region_type": None,
            "region_id": region_id,
            "parent_id": None,
            "color": color_hex,
            "local_x": center_x,
            "local_y": center_y,
            "global_x": center_x,
            "global_y": center_y,
            "bbox_local": bbox_local,
            "bbox": bbox_local,
            "density_multiplier": density_multiplier,
        })
    
    if progress_callback:
        progress_callback(100, 100)
    
    return regions_image, metadata

def classify_continuous_areas(
    cont_areas_image: NDArray[np.uint8],
    class_image: NDArray[np.uint8],
    cont_areas_metadata: list[dict],
) -> list[dict]:
    """
    Classify each continuous area as land, ocean, or lake based on its pixel composition.
    
    Updates the region_type field in metadata by checking which type of pixels
    (land, ocean, lake) are most prevalent in each area.
    
    Args:
        cont_areas_image: Image with continuous areas colored
        class_image: Classification image with land/ocean/lake colors
        cont_areas_metadata: Metadata list for continuous areas
    
    Returns:
        Updated metadata with region_type field set correctly
    """
    updated_metadata = []
    
    ocean_color = np.array(config.OCEAN_COLOR, dtype=np.uint8)
    lake_color = np.array(config.LAKE_COLOR, dtype=np.uint8)
    land_color = np.array(config.LAND_COLOR, dtype=np.uint8)
    
    for region in cont_areas_metadata:
        color_hex = region.get("color", "")
        try:
            color_rgb = hex_to_rgb(color_hex)
            target_color = np.array(color_rgb, dtype=np.uint8)
        except (ValueError, AttributeError):
            region["region_type"] = "unknown"
            updated_metadata.append(region)
            continue
        
        # Find all pixels of this continuous area
        rgb_match = np.all(cont_areas_image[:, :, :3] == target_color, axis=2)
        
        if not np.any(rgb_match):
            region["region_type"] = "unknown"
            updated_metadata.append(region)
            continue
        
        # Get classification of pixels in this area
        class_pixels = class_image[rgb_match, :3]
        
        # Count pixel types
        ocean_pixels = np.sum(np.all(class_pixels == ocean_color, axis=1))
        lake_pixels = np.sum(np.all(class_pixels == lake_color, axis=1))
        land_pixels = np.sum(np.all(class_pixels == land_color, axis=1))
        
        # Determine predominant type
        total = ocean_pixels + lake_pixels + land_pixels
        if total == 0:
            region["region_type"] = "unknown"
        elif land_pixels > ocean_pixels + lake_pixels:
            region["region_type"] = "land"
        elif ocean_pixels > lake_pixels:
            region["region_type"] = "ocean"
        else:
            region["region_type"] = "lake"
        
        updated_metadata.append(region)
    
    return updated_metadata

def assign_borders_to_areas(
    regions_image: NDArray[np.uint8],
    max_iters: int = 50,
    progress_callback = None,
) -> NDArray[np.uint8]:
    """
    Assign black pixels to neighboring areas by 4-neighbor majority vote.

    Args:
        regions_image: RGBA image where non-black pixels represent area colors.
        max_iters: Max number of propagation iterations.
        progress_callback: Optional callable that takes (current, total) for progress updates.

    Returns:
        Updated RGBA image with black pixels filled when possible.
    """

    result = regions_image.copy()
    rgb = result[:, :, :3]
    alpha = result[:, :, 3]

    black_mask = (alpha > 0) & (rgb == 0).all(axis=2)

    if not np.any(black_mask):
        return result

    color_code = (
        rgb[:, :, 0].astype(np.int32) << 16
    ) | (
        rgb[:, :, 1].astype(np.int32) << 8
    ) | rgb[:, :, 2].astype(np.int32)
    color_code[black_mask] = 0

    for iteration in range(max_iters):
        if progress_callback:
            progress_callback(iteration, max_iters)
        
        if not np.any(black_mask):
            break

        padded = np.pad(color_code, pad_width=1, mode="constant", constant_values=0)
        n0 = padded[:-2, 1:-1]
        n1 = padded[2:, 1:-1]
        n2 = padded[1:-1, :-2]
        n3 = padded[1:-1, 2:]

        v0 = n0 != 0
        v1 = n1 != 0
        v2 = n2 != 0
        v3 = n3 != 0

        c0 = v0 * (1 + (n0 == n1) + (n0 == n2) + (n0 == n3))
        c1 = v1 * (1 + (n1 == n0) + (n1 == n2) + (n1 == n3))
        c2 = v2 * (1 + (n2 == n0) + (n2 == n1) + (n2 == n3))
        c3 = v3 * (1 + (n3 == n0) + (n3 == n1) + (n3 == n2))

        counts = np.stack([c0, c1, c2, c3], axis=0)
        max_count = counts.max(axis=0)

        update_mask = black_mask & (max_count > 0)
        if not np.any(update_mask):
            break

        idx = counts.argmax(axis=0)
        best = np.where(idx == 0, n0, np.where(idx == 1, n1, np.where(idx == 2, n2, n3)))

        color_code[update_mask] = best[update_mask]
        black_mask = color_code == 0
    
    if progress_callback:
        progress_callback(max_iters, max_iters)

    result[:, :, 0] = (color_code >> 16) & 255
    result[:, :, 1] = (color_code >> 8) & 255
    result[:, :, 2] = color_code & 255
    result[:, :, 3] = 255

    return result
