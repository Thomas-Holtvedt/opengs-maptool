import logging
import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from tqdm import tqdm

from opengs_maptool.logic.utils import ColorSeries, RegionMetadata, hex_to_rgb, get_area_pixel_mask, ensure_point_in_mask
from opengs_maptool import config

NEIGHBOR_OFFSETS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def clean_boundary_image(boundary_image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """
    Convert a boundary image to a strict two-color RGBA format.
XI
    - Boundary pixels are set to pitch black: (0, 0, 0, 255)
    - All other pixels are set to medium gray: (128, 128, 128, 255)

        Supported input format:
        - Grayscale/flat boundary images where borders can be any value less than 180
            and area pixels are bright (greater than 180) in the red channel.

    Args:
        boundary_image: Input boundary image as RGB/RGBA numpy array.

    Returns:
        RGBA uint8 image with standardized boundary and area colors.
    """
    if boundary_image.ndim != 3 or boundary_image.shape[2] < 3:
        raise ValueError("boundary_image must have shape (H, W, C) with at least 3 channels")

    area_mask = get_area_pixel_mask(boundary_image, threshold=180)
    result = np.zeros((*area_mask.shape, 4), dtype=np.uint8)
    result[area_mask] = (128, 128, 128, 255)
    result[~area_mask] = (0, 0, 0, 255)
    return result


def classify_pixels_by_color(class_image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """
    Classify each pixel as ocean (0), lake (1), or land (2) based on closest color match.
    Return classification image.
    
    Args:
        class_image: Input image
    
    Returns:
        RGBA image (h, w, 4) with actual config colors
    """
    
    # Reference colors from config (shape: 3, 3)
    ref_colors = np.array([
        config.OCEAN_COLOR[:3],
        config.LAKE_COLOR[:3],
        config.LAND_COLOR[:3]
    ], dtype=np.float32)
    
    # Get pixel colors (h, w, 3)
    pixels = class_image[:, :, :3].astype(np.float32)
    
    # Compute squared distances to all 3 colors at once (vectorized)
    diff = pixels[:, :, None, :] - ref_colors[None, None, :, :]
    distances_sq = np.sum(diff ** 2, axis=3)  # (h, w, 3)
    
    # Find index of minimum distance (0=ocean, 1=lake, 2=land)
    classification = np.argmin(distances_sq, axis=2).astype(np.uint8)
    
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
    return result

def convert_boundaries_to_cont_areas(
        class_image: NDArray[np.uint8], boundary_image: NDArray[np.uint8], 
        rng_seed: int, min_area_pixels: int = 50, progress_callback=None,
    ) -> tuple[NDArray[np.uint8], list[RegionMetadata]]:
    """
    Convert the boundary image into an image of continuous areas(usually countries).
    
    Args:
        class_image: Type/classification image
        boundary_image: Input boundary image
        rng_seed: Random seed for color generation
        min_area_pixels: Minimum pixel count for a continuous area to be kept (smaller areas are merged into background)
        progress_callback: Optional callback function(current, total) for progress reporting
    
    Returns:
        Tuple of (cont_area_image, metadata) where metadata contains:
        - region_id: Region ID (1-indexed)
        - R, G, B: Area color
    """

    # Vectorized mask creation for both legacy and grayscale boundary formats.
    is_white = get_area_pixel_mask(boundary_image, threshold=0)

    # Use scipy's label function for connected component analysis (rel. fast)
    white_mask = is_white.astype(np.uint8)
    labeled_array, num_features = ndimage.label(white_mask)
    
    if progress_callback:
        progress_callback(10, 100)

    # Filter out small areas
    if min_area_pixels > 0:
        area_sizes = np.bincount(labeled_array.ravel())
        small_areas = np.where(area_sizes < min_area_pixels)[0]
        for small_area in small_areas:
            if small_area > 0:  # Skip background (0)
                labeled_array[labeled_array == small_area] = 0
        
        # Relabel to have consecutive IDs
        unique_labels = np.unique(labeled_array[labeled_array > 0])
        new_labeled_array = np.zeros_like(labeled_array)
        for new_id, old_id in enumerate(unique_labels, start=1):
            new_labeled_array[labeled_array == old_id] = new_id
        labeled_array = new_labeled_array
        num_features = len(unique_labels)
    
    if progress_callback:
        progress_callback(20, 100)

    # Create image from areas using the labeled array
    area_image = np.full((*boundary_image.shape[:2], 4), [0, 0, 0, 255], dtype=np.uint8)
    color_series = ColorSeries(rng_seed, exclude_values=[(0, 0, 0)])
    area_to_color = {}
    metadata = []
    
    # Determine area type by checking the most common type in this area
    ocean_color = np.array(config.OCEAN_COLOR, dtype=np.uint8)
    lake_color = np.array(config.LAKE_COLOR, dtype=np.uint8)
    land_color = np.array(config.LAND_COLOR, dtype=np.uint8)

    # Vectorized color assignment
    for idx, area_id in enumerate(tqdm(range(1, num_features + 1), desc="Processing boundaries into areas", unit="areas"), start=1):
        if progress_callback and idx % max(1, num_features // 20) == 0:  # Report every 5%
            progress_callback(20 + int((idx / num_features) * 80), 100)

        area_mask = labeled_array == area_id
        rows, cols = np.where(area_mask)
        
        # Calculate global bounding box for this area
        y_min, y_max = int(rows.min()), int(rows.max())
        x_min, x_max = int(cols.min()), int(cols.max())
        global_bbox = (x_min, y_min, x_max, y_max)
        cropped_mask = area_mask[y_min:(y_max+1), x_min:(x_max+1)]
        cropped_class_image = class_image[y_min:(y_max+1), x_min:(x_max+1)]

        # Get only RGB channels (first 3) for comparison
        cropped_rgb = cropped_class_image[:, :, :3]

        ocean_pixels = int(np.sum(np.all(cropped_rgb[cropped_mask] == ocean_color, axis=1)))
        lake_pixels = int(np.sum(np.all(cropped_rgb[cropped_mask] == lake_color, axis=1)))
        water_pixels = ocean_pixels + lake_pixels
        land_pixels = int(np.sum(np.all(cropped_rgb[cropped_mask] == land_color, axis=1)))
        
        # Determine predominant type and calculate number of areas
        if land_pixels > water_pixels:
            area_type = "land"
        else:
            area_type = "ocean" if ocean_pixels > lake_pixels else "lake"

        color_rgb, color_hex = color_series.get_color_rgb_hex(is_water=(area_type != "land"))
        area_to_color[area_id] = (*color_rgb, 255)
        area_image[labeled_array == area_id] = area_to_color[area_id]

        # Calculate center of mass (centroid) for local coordinates and round to integer pixel coordinates
        center_x = round(float(np.mean(cols)))
        center_y = round(float(np.mean(rows)))
        center_x, center_y = ensure_point_in_mask(area_mask, center_x, center_y)

        # Create Area
        metadata.append(RegionMetadata(
            region_id=area_id,
            region_type=area_type,
            color=color_hex,
            pixel_count=land_pixels + water_pixels,
            density_multiplier=None,
            parent_id=None, # Areas have no parent
            local_bbox=None, # "
            local_center=None, # "
            local_seed=None, # "
            global_bbox=global_bbox,
            global_center=(center_x, center_y),
            global_seed=(center_x, center_y),
        ))
    
    if progress_callback:
        progress_callback(100, 100)
    
    metadata = classify_continuous_areas(area_image, class_image, metadata)
    
    return area_image, metadata

def classify_continuous_areas(
    cont_area_image: NDArray[np.uint8],
    class_image: NDArray[np.uint8],
    cont_area_metadata: list[RegionMetadata],
) -> list[RegionMetadata]:
    """
    Classify each continuous area as land, ocean, or lake based on its pixel composition.
    
    Updates the region_type field in metadata by checking which type of pixels
    (land, ocean, lake) are most prevalent in each area.
    
    Args:
        cont_area_image: Image with continuous areas colored
        class_image: Classification image with land/ocean/lake colors
        cont_area_metadata: Metadata list for continuous areas
    """
    updated_metadata = []
    
    ocean_color = np.array(config.OCEAN_COLOR, dtype=np.uint8)
    lake_color = np.array(config.LAKE_COLOR, dtype=np.uint8)
    land_color = np.array(config.LAND_COLOR, dtype=np.uint8)
    
    for region in cont_area_metadata:
        color_hex = region.color
        try:
            color_rgb = hex_to_rgb(color_hex)
            target_color = np.array(color_rgb, dtype=np.uint8)
        except (ValueError, AttributeError):
            region.region_type = "unknown"
            updated_metadata.append(region)
            continue
        
        # Use bounding box to crop for efficiency
        if region.global_bbox is not None:
            x_min, y_min, x_max, y_max = region.global_bbox
            cropped_area = cont_area_image[y_min:y_max+1, x_min:x_max+1, :3]
            cropped_class = class_image[y_min:y_max+1, x_min:x_max+1, :3]
            rgb_match = np.all(cropped_area == target_color, axis=2)
        else:
            # Fallback to full image if bbox missing
            rgb_match = np.all(cont_area_image[:, :, :3] == target_color, axis=2)
            cropped_class = class_image[:, :, :3]

        if not np.any(rgb_match):
            logging.warning(
                f"No pixels found for region_id {region.region_id} (color={color_hex}) while classifying continuous areas.",
            )
            region.region_type = "unknown"
            updated_metadata.append(region)
            continue

        # Get classification of pixels in this area
        class_pixels = cropped_class[rgb_match]

        # Count pixel types
        ocean_pixels = np.sum(np.all(class_pixels == ocean_color, axis=1))
        lake_pixels = np.sum(np.all(class_pixels == lake_color, axis=1))
        land_pixels = np.sum(np.all(class_pixels == land_color, axis=1))
        
        # Determine predominant type
        total = ocean_pixels + lake_pixels + land_pixels
        if total == 0:
            region.region_type = "unknown"
        elif land_pixels > ocean_pixels + lake_pixels:
            region.region_type = "land"
        elif ocean_pixels > lake_pixels:
            region.region_type = "ocean"
        else:
            region.region_type = "lake"
        
        updated_metadata.append(region)
    
    return updated_metadata

def assign_borders_to_areas(
    area_image: NDArray[np.uint8],
    area_data: list[RegionMetadata],
    max_iters: int = 50,
    progress_callback = None,
) -> NDArray[np.uint8]:
    """
    Assign black pixels to neighboring areas by 4-neighbor majority vote.

    Args:
        area_image: RGBA image where non-black pixels represent area colors.
        area_data: List of RegionMetadata for each area (will be updated with new bbox after border assignment)
        max_iters: Max number of propagation iterations.
        progress_callback: Optional callable that takes (current, total) for progress updates.

    Returns:
        Updated RGBA image with black pixels filled when possible.
    """

    result = area_image.copy()
    rgb = result[:, :, :3]
    alpha = result[:, :, 3]

    black_mask = (alpha > 0) & (rgb == 0).all(axis=2)

    if not np.any(black_mask):
        return result

    def rgb_to_color_code(rgb_arr):
        """Convert (H, W, 3) uint8 RGB array to (H, W) int32 color code array."""
        return (
            rgb_arr[:, :, 0].astype(np.int32) << 16
        ) | (
            rgb_arr[:, :, 1].astype(np.int32) << 8
        ) | rgb_arr[:, :, 2].astype(np.int32)

    def color_code_to_rgb(color_code_arr):
        """Convert (H, W) int32 color code array to (H, W, 3) uint8 RGB array."""
        rgb_arr = np.empty((*color_code_arr.shape, 3), dtype=np.uint8)
        rgb_arr[:, :, 0] = (color_code_arr >> 16) & 255
        rgb_arr[:, :, 1] = (color_code_arr >> 8) & 255
        rgb_arr[:, :, 2] = color_code_arr & 255
        return rgb_arr

    color_code = rgb_to_color_code(rgb)
    color_code[black_mask] = 0

    # Map color code (int) to area object for reverse lookup
    color_code_to_area = {
        rgb_to_color_code(np.array(hex_to_rgb(area.color), dtype=np.uint8).reshape(1, 1, 3))[0, 0]: area
        for area in area_data
    }

    # Initialize bbox tracking for each area
    area_bbox = {}
    for area in area_data:
        if area.global_bbox is not None:
            min_x, min_y, max_x, max_y = area.global_bbox
            area_bbox[area.region_id] = [min_x, min_y, max_x, max_y]
        else:
            area_bbox[area.region_id] = [None, None, None, None]

    border_tqdm = tqdm(range(max_iters), desc="Border assignment", unit="rounds")
    for iteration in border_tqdm:
        if progress_callback:
            progress_callback(iteration, max_iters)
        if not np.any(black_mask):
            break

        padded = np.pad(color_code, pad_width=1, mode="constant", constant_values=0)
        n0 = padded[:-2, 1:-1] # Up
        n1 = padded[2:, 1:-1] # Down
        n2 = padded[1:-1, :-2] # Left
        n3 = padded[1:-1, 2:] # Right

        v0 = n0 != 0
        v1 = n1 != 0
        v2 = n2 != 0
        v3 = n3 != 0

        # Efficient neighbor voting: count how many neighbors have the same color as each neighbor
        # For each pixel, count how many of the 4 neighbors have the same color code as n0, n1, n2, n3
        # This avoids redundant comparisons
        c0 = v0.astype(np.int32)
        c1 = v1.astype(np.int32)
        c2 = v2.astype(np.int32)
        c3 = v3.astype(np.int32)

        # Only compare each pair once
        eq_01 = (n0 == n1) & v0 & v1
        eq_02 = (n0 == n2) & v0 & v2
        eq_03 = (n0 == n3) & v0 & v3
        eq_12 = (n1 == n2) & v1 & v2
        eq_13 = (n1 == n3) & v1 & v3
        eq_23 = (n2 == n3) & v2 & v3

        c0 += eq_01 + eq_02 + eq_03
        c1 += eq_01 + eq_12 + eq_13
        c2 += eq_02 + eq_12 + eq_23
        c3 += eq_03 + eq_13 + eq_23

        counts = np.stack([c0, c1, c2, c3], axis=0)
        max_count = counts.max(axis=0)

        update_mask = black_mask & (max_count > 0)
        if not np.any(update_mask):
            break

        idx = counts.argmax(axis=0)
        best = np.where(idx == 0, n0, np.where(idx == 1, n1, np.where(idx == 2, n2, n3)))

        color_code[update_mask] = best[update_mask]
        # Update bbox for each area as new pixels are assigned
        update_indices = np.flatnonzero(update_mask)
        for idx in update_indices:
            y, x = np.unravel_index(idx, update_mask.shape)
            assigned_code = color_code[y, x]
            area = color_code_to_area.get(assigned_code)
            if area is not None:
                bbox = area_bbox[area.region_id]
                if bbox[0] is None:
                    bbox[0] = x
                    bbox[1] = y
                    bbox[2] = x
                    bbox[3] = y
                else:
                    bbox[0] = min(bbox[0], x)
                    bbox[1] = min(bbox[1], y)
                    bbox[2] = max(bbox[2], x)
                    bbox[3] = max(bbox[3], y)
        black_mask = color_code == 0
    border_tqdm.close()
    
    if progress_callback:
        progress_callback(max_iters, max_iters)


    result[:, :, :3] = color_code_to_rgb(color_code)
    result[:, :, 3] = 255

    # --- BBOX UPDATING LOGIC ---
    # Set global_bbox for each region in metadata from tracked bboxes
    for area in area_data:
        bbox = area_bbox.get(area.region_id)
        if bbox is not None and None not in bbox:
            area.global_bbox = tuple(int(v) for v in bbox)
        # else leave as is (None)
    return result
