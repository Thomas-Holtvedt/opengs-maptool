from __future__ import annotations
from collections import deque
from dataclasses import asdict
from gceutils import grepr_dataclass
import logging
import numpy as np
from numpy.typing import NDArray
from PIL import Image
from scipy.ndimage import distance_transform_edt, label as scipy_label
from scipy.spatial import cKDTree
from scipy.stats import mode
from typing import Any, Iterable, Literal

from opengs_maptool import config


FOUR_CONNECTED = np.array(
    [
        [0, 1, 0],
        [1, 1, 1],
        [0, 1, 0],
    ],
    dtype=np.uint8,
)

FOUR_NEIGHBOR_OFFSETS: tuple[tuple[int, int], ...] = (
    (-1, 0),
    (1, 0),
    (0, -1),
    (0, 1),
)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert RGB values to hex color string (e.g., '#aabbcc')"""
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string (e.g., '#aabbcc') to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def ensure_point_in_mask(mask: NDArray[np.bool_], x: int, y: int) -> tuple[int, int]:
    """Return a point guaranteed to be inside `mask`.

    If (x, y) rounds to a pixel inside the mask, that rounded point is returned.
    Otherwise, the nearest pixel in the mask is returned.
    """
    h, w = mask.shape
    x = max(0, min(w - 1, x))
    y = max(0, min(h - 1, y))

    if mask[y, x]:
        return (x, y)

    ys, xs = np.where(mask)
    if len(xs) == 0:
        return (x, y)

    dx = xs.astype(np.int32) - x
    dy = ys.astype(np.int32) - y
    nearest_idx = int(np.argmin(dx * dx + dy * dy))
    return int(xs[nearest_idx]), int(ys[nearest_idx])


def get_area_pixel_mask(image: NDArray[np.uint8], threshold: int) -> NDArray[np.bool_]:
    """Return mask for area pixels in boundary images.

    Args:
        image: Boundary image (RGB/RGBA).
        threshold: Red-channel cutoff. Use 180 for uncleaned images and 0 for
            cleaned images where borders are exactly 0.
    """
    return image[:, :, 0] > threshold



def calculate_density_multiplier(
    image: NDArray[np.uint8],
    mask: NDArray[np.bool_],
    region_id: Any | None = None,
    fallback: float = 128.0,
    use_rgb_average: bool = True,
    warn_on_empty: bool = True,
) -> float:
    """
    Calculate a density multiplier from the average brightness of masked pixels.
    Uses the red channel by default, or RGB average if use_rgb_average is True.
    If the mask is empty, returns fallback and optionally warns.
    Maps brightness (0-255) to a density multiplier (piecewise linear).
    """
    if not np.any(mask):
        if warn_on_empty:
            logging.warning(
                f"No pixels found for region_id {region_id} while calculating density multiplier.",
            )
        avg_brightness = fallback
    else:
        if use_rgb_average:
            # Use mean of all RGB channels for masked pixels
            avg_brightness = float(np.mean(image[:, :, :3][mask]))
        else:
            # Use mean of red channel for masked pixels
            avg_brightness = float(np.mean(image[:, :, 0][mask]))

    # Map average brightness to density multiplier using config min/max
    min_factor = config.DENSITY_MULTIPLIER_MIN
    mid_factor = config.DENSITY_MULTIPLIER_NORMAL
    max_factor = config.DENSITY_MULTIPLIER_MAX
    if avg_brightness <= 128.0:
        # Linear interpolation from min_factor to mid_factor
        return (avg_brightness / 128.0) * (mid_factor - min_factor) + min_factor
    else:
        # Linear interpolation from mid_factor to max_factor
        return ((avg_brightness - 128.0) / 127.0) * (max_factor - mid_factor) + mid_factor


class NumberSeries:
    def __init__(self, prefix: str, number_start: int, number_end: int) -> None:
        self.prefix: str = prefix
        self.number_end: int = number_end
        self.id_length: int = len(str(number_end))
        self.number_next: int = number_start

    def get_id(self) -> str:
        if self.number_next > self.number_end:
            raise ValueError("No more available numbers in NumberSeries")

        formatted_number: str = self.prefix + \
            str(self.number_next).zfill(self.id_length)
        self.number_next += 1
        return formatted_number


class ColorSeries:
    def __init__(self, rng_seed: int  | np.random.SeedSequence, exclude_values: Iterable[tuple[int, int, int]] | None = None) -> None:
        self.rng = np.random.default_rng(rng_seed)
        self.used_values = set() if exclude_values is None else set(exclude_values) 

    def get_color_rgb(self, is_water: bool) -> tuple[int, int, int]:
        while True:
            if is_water:
                r = self.rng.integers(0, 60)
                g = self.rng.integers(0, 80)
                b = self.rng.integers(100, 180)
            else:
                r, g, b = map(int, self.rng.integers(0, 256, 3))

            color = (int(r), int(g), int(b))
            if color not in self.used_values:
                self.used_values.add(color)
                return color
    
    def get_color_hex(self, is_water: bool) -> str:
        return rgb_to_hex(self.get_color_rgb(is_water=is_water))

    def get_color_rgb_hex(self, is_water: bool) -> tuple[tuple[int, int, int], str]:
        rgb = self.get_color_rgb(is_water=is_water)
        return (rgb, rgb_to_hex(rgb))


@grepr_dataclass(validate=False)
class RegionMetadata:
    region_id: str
    region_type: Literal["land", "ocean", "lake", "unknown"]
    color: str # format: "#00aa99"
    pixel_count: int
    density_multiplier: float | None = None
    parent_id: str | None = None
    local_bbox: tuple[int, int, int, int] | None = None # (x_min, y_min, x_max, y_max)
    local_center: tuple[int, int] | None = None # (x, y)
    local_seed: tuple[int, int] | None = None # (x, y)
    global_bbox: tuple[int, int, int, int] | None = None # (x_min, y_min, x_max, y_max)
    global_center: tuple[int, int] | None = None # (x, y)
    global_seed: tuple[int, int] | None = None # (x, y)
    # See README for an exact description

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    def to_csv_dict(self) -> dict[str, Any]:
        local_bbox = self.local_bbox or (None, None, None, None)
        local_center = self.local_center or (None, None)
        local_seed = self.local_seed or (None, None)
        global_bbox = self.global_bbox or (None, None, None, None)
        global_center = self.global_center or (None, None)
        global_seed = self.global_seed or (None, None)

        return dict(
            region_id=self.region_id,
            region_type=self.region_type,
            color=self.color,
            pixel_count=self.pixel_count,
            parent_id=self.parent_id,
            
            local_bbox_min_x=local_bbox[0],
            local_bbox_min_y=local_bbox[1],
            local_bbox_max_x=local_bbox[2],
            local_bbox_max_y=local_bbox[3],

            local_center_x=local_center[0],
            local_center_y=local_center[1],
            local_seed_x=local_seed[0],
            local_seed_y=local_seed[1],

            global_bbox_min_x=global_bbox[0],
            global_bbox_min_y=global_bbox[1],
            global_bbox_max_x=global_bbox[2],
            global_bbox_max_y=global_bbox[3],

            global_center_x=global_center[0],
            global_center_y=global_center[1],
            global_seed_x=global_seed[0],
            global_seed_y=global_seed[1],
        )

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> RegionMetadata:
        def parse_opt_str(key: str) -> str | None:
            return d.get(key, False) or None # "" -> None

        def parse_num[DT](key: str, default: DT = None, as_float: bool = False) -> int | float | DT:
            val = d.get(key, None)
            if val in {"", None}:
                return default
            try:
                return float(val) if as_float else int(val)
            except ValueError:
                return default
                
        def parse_coords(key: str) -> tuple[int, ...] | None:
            val = d.get(key, None)
            if not val:
                return None
            if isinstance(val, list):
                return tuple(val)
            if isinstance(val, tuple):
                return val
            return None
        
        return cls(
            region_id=parse_opt_str("region_id"),
            region_type=parse_opt_str("region_type"),
            color=parse_opt_str("color"),
            pixel_count=parse_num("pixel_count", default=0),
            density_multiplier=parse_num("density_multiplier", as_float=True),
            parent_id=parse_opt_str("parent_id"),
            local_bbox=parse_coords("local_bbox"),
            local_center=parse_coords("local_center"),
            local_seed=parse_coords("local_seed"),
            global_bbox=parse_coords("global_bbox"),
            global_center=parse_coords("global_center"),
            global_seed=parse_coords("global_seed"),
        )
    
    @classmethod
    def from_csv_dict(cls, d: dict[str, Any]) -> RegionMetadata:
        def parse_opt_str(key: str) -> str | None:
            return d.get(key, False) or None # "" -> None

        def parse_num[DT](key: str, default: DT = None, as_float: bool = False) -> int | float | DT:
            val = d.get(key, None)
            if val in {"", None}:
                return default
            try:
                return float(val) if as_float else int(val)
            except ValueError:
                return default
                
        def parse_coords(*keys: tuple[str]) -> tuple[int, ...] | None:
            vals = tuple(parse_num(key, default=None) for key in keys)
            if not all(vals):
                return None
            return vals

        return cls(
            region_id=parse_opt_str("region_id"),
            region_type=parse_opt_str("region_type"),
            color=parse_opt_str("color"),
            pixel_count=parse_num("pixel_count", default=0),
            density_multiplier=parse_num("density_multiplier", as_float=True),
            parent_id=parse_opt_str("parent_id"),
            local_bbox=parse_coords("local_bbox_min_x", "local_bbox_min_y", "local_bbox_max_x", "local_bbox_max_y"),
            local_center=parse_coords("local_center_x", "local_center_y"),
            local_seed=parse_coords("local_seed_x", "local_seed_y"),
            global_bbox=parse_coords("global_bbox_min_x", "global_bbox_min_y", "global_bbox_max_x", "global_bbox_max_y"),
            global_center=parse_coords("global_center_x", "global_center_y"), 
            global_seed=parse_coords("global_seed_x", "global_seed_y"),
        )

def poisson_disk_samples(
    mask: NDArray[np.bool],
    num_points: int,
    rng_seed: int | np.random.SeedSequence,
    min_dist: float | None = None,
    k: int = 30,
    border_margin: float = 0.0,
    no_distance_limit: bool = False,
) -> list[tuple[int, int]]:
    """
    Generate relatively evenly spaced points inside a boolean mask using Poisson disk sampling.

    Args:
        mask: 2D boolean array indicating valid area.
        num_points: Target number of points.
        rng_seed: RNG seed for reproducibility.
        min_dist: Minimum distance between points. If None, estimated from area/num_points.
        k: Number of attempts per active point.
        border_margin: Minimum distance from the boundary (in pixels). Uses distance transform.
        no_distance_limit: If True, fill remaining points without distance constraint.

    Returns:
        List of (x, y) integer coordinates.
    """
    if num_points <= 0:
        return []
    if mask.ndim != 2:
        raise ValueError("mask must be a 2D boolean array")

    allowed_mask = mask
    if border_margin > 0:
        dist = distance_transform_edt(mask)
        allowed_mask = mask & (dist >= border_margin)
        if not allowed_mask.any():
            allowed_mask = mask

    coords_yx = np.column_stack(np.where(allowed_mask))
    if coords_yx.size == 0:
        return []

    area = coords_yx.shape[0]
    if min_dist is None:
        min_dist = max(1.0, float(np.sqrt(area / max(num_points, 1)) * 0.85))
    min_dist = max(1.0, float(min_dist))

    h, w = mask.shape
    cell_size = min_dist / np.sqrt(2)
    grid_h = int(np.ceil(h / cell_size))
    grid_w = int(np.ceil(w / cell_size))
    grid = -np.ones((grid_h, grid_w), dtype=np.int32)

    rng = np.random.default_rng(rng_seed)

    def grid_coords(px: int, py: int) -> tuple[int, int]:
        return int(py / cell_size), int(px / cell_size)

    samples: list[tuple[int, int]] = []
    active: list[int] = []

    start_idx = int(rng.integers(0, coords_yx.shape[0]))
    sy, sx = coords_yx[start_idx]
    samples.append((int(sx), int(sy)))
    gy, gx = grid_coords(int(sx), int(sy))
    grid[gy, gx] = 0
    active.append(0)

    min_dist_sq = min_dist * min_dist

    while active and len(samples) < num_points:
        idx = int(rng.choice(active))
        base_x, base_y = samples[idx]
        found = False

        for _ in range(k):
            radius = float(rng.uniform(min_dist, 2.0 * min_dist))
            angle = float(rng.uniform(0.0, 2.0 * np.pi))
            x = int(round(base_x + radius * np.cos(angle)))
            y = int(round(base_y + radius * np.sin(angle)))

            if x < 0 or y < 0 or x >= w or y >= h:
                continue
            if not allowed_mask[y, x]:
                continue

            gy, gx = grid_coords(x, y)
            y0 = max(0, gy - 2)
            y1 = min(grid_h, gy + 3)
            x0 = max(0, gx - 2)
            x1 = min(grid_w, gx + 3)

            ok = True
            for ny in range(y0, y1):
                for nx in range(x0, x1):
                    sidx = grid[ny, nx]
                    if sidx == -1:
                        continue
                    sx2, sy2 = samples[sidx]
                    dx = sx2 - x
                    dy = sy2 - y
                    if (dx * dx + dy * dy) < min_dist_sq:
                        ok = False
                        break
                if not ok:
                    break

            if ok:
                samples.append((x, y))
                grid[gy, gx] = len(samples) - 1
                active.append(len(samples) - 1)
                found = True
                break

        if not found:
            active.remove(idx)

    if no_distance_limit and len(samples) < num_points:
        remaining = num_points - len(samples)
        used = set(samples)
        all_pts = [(int(x), int(y)) for y, x in coords_yx]
        rng.shuffle(all_pts)
        for x, y in all_pts:
            if (x, y) in used:
                continue
            samples.append((x, y))
            used.add((x, y))
            remaining -= 1
            if remaining <= 0:
                break

    return samples


def lloyd_relaxation(
        mask: NDArray[np.bool], point_seeds: list[tuple[int, int]], 
        rng_seed: int | np.random.SeedSequence, iterations: int, boundary_mask: NDArray[np.bool] | None = None
    ) -> list[tuple[int, int]]:
    """
    Lloyd relaxation with optional fast mode.
    
    Args:
        mask: Valid region mask
        point_seeds: Initial seed positions
        rng_seed: RNG seed for reproducibility.
        iterations: Number of relaxation iterations
        boundary_mask: Optional boundary mask
    """
    if iterations <= 0 or not point_seeds:
        return point_seeds

    coords_yx = np.column_stack(np.where(mask))
    if coords_yx.size == 0:
        return point_seeds

    # Standard Lloyd relaxation (slower but better quality)
    coords_xy = np.flip(coords_yx, axis=1).copy()
    if coords_xy.dtype != np.float32:
        coords_xy = coords_xy.astype(np.float32, copy=False)
    rng = np.random.default_rng(rng_seed)

    # Cache distance transform (expensive operation)
    _, (ny, nx) = distance_transform_edt(~mask, return_indices=True)

    seeds_arr = np.array(point_seeds, dtype=np.float32)

    for _ in range(iterations):
        # Assign each coordinate to nearest seed
        tree = cKDTree(seeds_arr)
        _, labels = tree.query(coords_xy, k=1)

        counts = np.bincount(labels, minlength=len(seeds_arr))
        sum_x = np.bincount(labels, weights=coords_xy[:, 0], minlength=len(seeds_arr))
        sum_y = np.bincount(labels, weights=coords_xy[:, 1], minlength=len(seeds_arr))

        for i in range(len(seeds_arr)):
            if counts[i] <= 0:
                idx = rng.integers(0, coords_xy.shape[0])
                seeds_arr[i] = coords_xy[idx]
                continue

            mx = sum_x[i] / counts[i]
            my = sum_y[i] / counts[i]

            cx = int(round(mx))
            cy = int(round(my))
            cx = max(0, min(cx, mask.shape[1] - 1))
            cy = max(0, min(cy, mask.shape[0] - 1))

            # Enforce: seed must be in mask AND NOT in boundary
            if mask[cy, cx]:
                if boundary_mask is None or not boundary_mask[cy, cx]:
                    seeds_arr[i] = (cx, cy)
                else:
                    # Snap to nearest non-boundary point
                    cy2 = int(ny[cy, cx])
                    cx2 = int(nx[cy, cx])
                    seeds_arr[i] = (cx2, cy2)
            else:
                cy2 = int(ny[cy, cx])
                cx2 = int(nx[cy, cx])
                seeds_arr[i] = (cx2, cy2)

    return [(int(x), int(y)) for x, y in seeds_arr]


def assign_regions(mask: NDArray[np.bool], seeds: list[tuple[int, int]], start_index: int) -> NDArray[np.int32]:
    """
    Assign each pixel in mask to nearest seed using geodesic (through-mask) distance.
    
    Uses distance transform and Voronoi-like assignment where distance is measured
    through the valid mask pixels only. This naturally handles narrow straits and makes fragments rare.
    
    Args:
        mask: Boolean mask of valid pixels (True = valid)
        seeds: List of (x, y) seed positions
        start_index: Starting index for region IDs
    
    Returns:
        pmap: Region map where each pixel has a region ID (or -1 for invalid)
    """
    
    h, w = mask.shape
    pmap = np.full((h, w), -1, np.int32)

    if not seeds or not mask.any():
        return pmap
    
    # Multi-source BFS: start from all seeds simultaneously, assign based on which reaches first
    # This gives geodesic distance (distance through mask, not straight-line)
    queue = deque()
    distances = np.full((h, w), np.inf, dtype=np.float32)
    
    # Initialize: add all seeds to queue with distance 0
    for idx, (sx, sy) in enumerate(seeds):
        if 0 <= sx < w and 0 <= sy < h and mask[sy, sx]:
            pmap[sy, sx] = start_index + idx
            distances[sy, sx] = 0.0
            queue.append((sy, sx, start_index + idx, 0.0))
    
    # BFS with distance tracking: assign to closest seed by path distance
    while queue:
        y, x, region_id, dist = queue.popleft()
        
        # Skip if already processed with shorter distance
        if dist > distances[y, x]:
            continue
        
        # Check 8-connected neighbors with appropriate distances
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dy == 0 and dx == 0:
                    continue
                
                ny = y + dy
                nx = x + dx
                
                # Calculate distance (diagonal = sqrt(2), orthogonal = 1)
                step_dist = 1.414 if (dy != 0 and dx != 0) else 1.0
                new_dist = dist + step_dist
                
                # Check bounds and mask
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx]:
                    # Update if this path is shorter
                    if new_dist < distances[ny, nx]:
                        distances[ny, nx] = new_dist
                        pmap[ny, nx] = region_id
                        queue.append((ny, nx, region_id, new_dist))
    
    return pmap


def defragment_regions(
    pmap: NDArray[np.int32],
    mask: NDArray[np.bool],
) -> NDArray[np.int32]:
    """
    Fix regions that got fragmented into multiple disconnected components.
    
    Three-phase approach:
    1. Merge small fragments (<size_threshold) to best neighboring region
    2. Reassign remaining fragments to nearest other seeds
    3. Enforce one connected component per seed/region iteratively
    
    Args:
        pmap: Region map with region assignments
        mask: Valid region mask
        seeds: Original seed positions (for reassignment)
        size_threshold: Pixel count below which fragments are considered "small"
    
    Returns:
        Fixed pmap with defragmented regions
    """
    
    # Use fix_region_connectivity to detect islands, but set all islands to -1
    pmap_fixed = pmap.copy()
    h, w = mask.shape
    # Set max_iters proportional to pixel count (at least 50)
    pixel_count = np.count_nonzero(mask)
    max_iters = max(50, int(pixel_count // 2))
    # Explicitly set all fragments to -1 before filling
    h, w = mask.shape
    valid_ids = set(np.unique(pmap[mask])) - {-1}
    for region_id in valid_ids:
        region_mask = (pmap_fixed == region_id)
        components, num_components = scipy_label(region_mask, structure=FOUR_CONNECTED)
        if num_components <= 1:
            continue
        # Find the largest component
        component_sizes = np.bincount(components[region_mask])
        largest_idx = np.argmax(component_sizes)
        # Set all other components (islands) to -1
        for comp_idx in range(1, num_components + 1):
            if comp_idx == largest_idx or comp_idx == 0:
                continue
            comp_mask = (components == comp_idx)
            pmap_fixed[comp_mask] = -1

    for _ in range(max_iters):
        changed = False
        # Find all -1 (fragment) pixels inside the mask
        island_mask = (pmap_fixed == -1) & mask
        if not np.any(island_mask):
            break
        # Pad for neighbor access
        padded = np.pad(pmap_fixed, pad_width=1, mode="constant", constant_values=-1)
        n0 = padded[:-2, 1:-1]
        n1 = padded[2:, 1:-1]
        n2 = padded[1:-1, :-2]
        n3 = padded[1:-1, 2:]

        for y, x in zip(*np.where(island_mask)):
            vals = [n0[y, x], n1[y, x], n2[y, x], n3[y, x]]
            vals = [v for v in vals if v != -1]
            if vals:
                # Assign to majority neighbor
                new_val = mode(vals, keepdims=False).mode
                pmap_fixed[y, x] = new_val
                changed = True
        if not changed:
            break
    return pmap_fixed


def build_metadata(
    pmap: NDArray[np.int32],
    seeds: list[tuple[int, int]],
    start_index: int,
    region_type: str,
    series: NumberSeries,
    color_series: ColorSeries,
    parent_id: str | None = None,
    parent_density_multiplier: float | None = None,
) -> list[RegionMetadata]:
    if pmap.size == 0 or not seeds:
        return []

    valid = pmap >= 0
    if not valid.any():
        return []

    indices = (pmap[valid] - start_index).astype(np.int32)
    # Ensure no negative indices (should not happen, but safeguard against edge cases)
    if np.any(indices < 0):
        indices = np.maximum(indices, 0)
    
    coords_yx = np.column_stack(np.where(valid))
    coords_xy = np.flip(coords_yx, axis=1).astype(np.float32, copy=False)

    min_x = np.full(len(seeds), np.inf, dtype=np.float64)
    min_y = np.full(len(seeds), np.inf, dtype=np.float64)
    max_x = np.full(len(seeds), -np.inf, dtype=np.float64)
    max_y = np.full(len(seeds), -np.inf, dtype=np.float64)

    np.minimum.at(min_x, indices, coords_xy[:, 0])
    np.minimum.at(min_y, indices, coords_xy[:, 1])
    np.maximum.at(max_x, indices, coords_xy[:, 0])
    np.maximum.at(max_y, indices, coords_xy[:, 1])

    counts = np.bincount(indices, minlength=len(seeds))
    sum_x = np.bincount(indices, weights=coords_xy[:, 0], minlength=len(seeds))
    sum_y = np.bincount(indices, weights=coords_xy[:, 1], minlength=len(seeds))

    metadata = []
    for i in range(len(seeds)):
        region_id = series.get_id()

        sx, sy = seeds[i]
        color_hex = color_series.get_color_hex(is_water=(region_type != "land"))
        if counts[i] <= 0:
            cx, cy = sx, sy
            local_bbox = (int(sx), int(sy), int(sx), int(sy))
            pixel_count = 0
        else:
            cx = round(float(sum_x[i] / counts[i]))
            cy = round(float(sum_y[i] / counts[i]))
            region_mask = pmap == (start_index + i)

            h, w = region_mask.shape
            cx = max(0, min(w - 1, cx))
            cy = max(0, min(h - 1, cy))

            if not region_mask[cy, cx]:
                if 0 <= sx < w and 0 <= sy < h and region_mask[sy, sx]:
                    cx, cy = sx, sy
                else:
                    cx, cy = ensure_point_in_mask(region_mask, sx, sy)

            # Convert to integers with floor/ceil for proper pixel coverage
            local_bbox = (int(min_x[i]),  int(min_y[i]), int(max_x[i]), int(max_y[i]))
            pixel_count = int(region_mask.sum())

        # Create Region (e.g. Territory or Province)
        meta = RegionMetadata(
            region_id=region_id,
            region_type=region_type,
            color=color_hex,
            pixel_count=pixel_count,
            density_multiplier=parent_density_multiplier or 1.0,
            parent_id=parent_id,
            local_bbox=local_bbox,
            local_center=(cx, cy),
            local_seed=(int(sx), int(sy)),
            global_bbox=None, # Set later
            global_center=None, # Set later
            global_seed=None, # Set later
        )
        metadata.append(meta)
    return metadata
