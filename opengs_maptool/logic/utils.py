from __future__ import annotations
import numpy as np
from numpy.typing import NDArray
from PIL import Image
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt, label as ndlabel
from typing import Any
import opengs_maptool.config as config
from opengs_maptool.controllers.progress_controller import ProgressController
import opengs_maptool.logic.datastructure as ds
from opengs_maptool.logic.numb_gen import NumberSeries

MAX_LLOYD_SAMPLE = 100_000

used_colors = set()


def clear_used_colors() -> None:
    used_colors.clear()


def color_from_id(index: int, region_type: ds.RegionType) -> ds.ColorTuple:
    rng = np.random.default_rng(index + 1)
    while True:
        if region_type == ds.RegionType.OCEAN:
            r = rng.integers(0, 60)
            g = rng.integers(0, 80)
            b = rng.integers(100, 180)
        elif region_type == ds.RegionType.LAKE:
            r = rng.integers(0, 80)
            g = rng.integers(80, 180)
            b = rng.integers(100, 200)
        else:
            r, g, b = map(int, rng.integers(0, 256, 3))

        color = (int(r), int(g), int(b))
        if color not in used_colors:
            used_colors.add(color)
            return color


def random_seeds(
        mask: ds.BooleanMaskMap, num_points: int, rng_seed: int | None = None,
        density=None, density_strength: float = 1.0,
    ) -> list[ds.IntCoordinate]:
    """Pick num_points random pixels from mask.

    When density is provided (2D uint8 array, same shape as mask),
    darker pixels attract more seeds: weight = (256 - pixel_value) ^ density_strength.
    """
    coords_yx = np.column_stack(np.where(mask))
    if coords_yx.size == 0 or num_points <= 0:
        return []

    rng = np.random.default_rng(rng_seed)
    n = min(num_points, len(coords_yx))

    if density is not None:
        weights = 256.0 - density[coords_yx[:, 0], coords_yx[:, 1]].astype(np.float64)
        weights = weights ** density_strength
        total = weights.sum()
        if total > 0:
            prob = weights / total
            indices = rng.choice(len(coords_yx), size=n, replace=False, p=prob)
        else:
            indices = rng.choice(len(coords_yx), size=n, replace=False)
    else:
        indices = rng.choice(len(coords_yx), size=n, replace=False)

    return [(int(x), int(y)) for y, x in coords_yx[indices]]


def lloyd_relaxation(
        mask: ds.BooleanMaskMap, point_seeds: list[ds.IntCoordinate],
        progress_controller: ProgressController, rng_seed: int | None = None,
        iterations: int = 4,
    ) -> list[ds.IntCoordinate]:
    """
    Improve seed placement by iteratively moving each seed to the centroid
    of its Voronoi cell.
    """
    prep_phase = progress_controller.add_phase(step_weight=1)
    loop_phase = progress_controller.add_phase(step_weight=2*iterations)
        # step_weight can also be set to a constant / doesn't correlate with iterations necessarily
    finish_phase = progress_controller.add_phase(step_weight=1)

    with progress_controller.execute_phase(prep_phase):
        if iterations <= 0 or not point_seeds:
            return point_seeds

        coords_yx = np.column_stack(np.where(mask))
        if coords_yx.size == 0:
            return point_seeds

        coords_xy = np.flip(coords_yx, axis=1).astype(np.float32)
        rng = np.random.default_rng(rng_seed)

        # Subsample for centroid computation
        if len(coords_xy) > MAX_LLOYD_SAMPLE:
            sample_idx = rng.choice(len(coords_xy), size=MAX_LLOYD_SAMPLE, replace=False)
            sample_xy = coords_xy[sample_idx]
        else:
            sample_xy = coords_xy

        seeds_arr = np.array(point_seeds, dtype=np.float32)

    with progress_controller.execute_phase(loop_phase) as loop_progress:
        wrapped_tracker_iterable = loop_progress.track_iteration(range(iterations))
        for _ in wrapped_tracker_iterable:
            tree = cKDTree(seeds_arr)
            _, labels = tree.query(sample_xy, k=1)

            counts = np.bincount(labels, minlength=len(seeds_arr))
            sum_x = np.bincount(labels, weights=sample_xy[:, 0], minlength=len(seeds_arr))
            sum_y = np.bincount(labels, weights=sample_xy[:, 1], minlength=len(seeds_arr))

            for i in range(len(seeds_arr)):
                if counts[i] <= 0:
                    idx = rng.integers(0, len(sample_xy))
                    seeds_arr[i] = sample_xy[idx]
                    continue

                cx = int(round(sum_x[i] / counts[i]))
                cy = int(round(sum_y[i] / counts[i]))
                cx = max(0, min(cx, mask.shape[1] - 1))
                cy = max(0, min(cy, mask.shape[0] - 1))

                if mask[cy, cx]:
                    seeds_arr[i] = (cx, cy)

    with progress_controller.execute_phase(finish_phase):
        point_seeds = [(int(x), int(y)) for x, y in seeds_arr]
    return point_seeds


def _build_jitter_maps(h: int, w: int, seeds_arr: ds.JitterSeedsArray) -> tuple[ds.JitterSeedsArray, ds.JitterSeedsArray] | tuple[None, None]:
    """Build spatially-correlated noise maps for jagged border effect.

    Returns (jitter_x, jitter_y) arrays of shape (h, w), or (None, None)
    if jagged borders cannot be applied.
    """
    if len(seeds_arr) < 2:
        return None, None

    from scipy.ndimage import zoom as ndzoom

    rng = np.random.default_rng(42)
    seed_tree = cKDTree(seeds_arr)
    nn_dists, _ = seed_tree.query(seeds_arr, k=2)
    avg_dist = float(nn_dists[:, 1].mean())
    amplitude = avg_dist * config.JAGGED_BORDER_AMPLITUDE

    # Coarse noise grid — each cell covers ~avg_dist/4 pixels
    cell = max(4, int(avg_dist / 4))
    ch = (h + cell - 1) // cell + 1
    cw = (w + cell - 1) // cell + 1
    jx = ndzoom(rng.uniform(-amplitude, amplitude, (ch, cw)),
                cell, order=1)[:h, :w].astype(np.float32)
    jy = ndzoom(rng.uniform(-amplitude, amplitude, (ch, cw)),
                cell, order=1)[:h, :w].astype(np.float32)
    return jx, jy


def _jitter_coords(
        coords_xy: ds.JitterSeedsArray, coords_yx: ds.JitterSeedsArray, jitter_x: ds.JitterSeedsArray, jitter_y: ds.JitterSeedsArray
    ) -> ds.JitterSeedsArray:
    """Return a copy of coords_xy with spatially-correlated noise added."""
    out = coords_xy.copy()
    out[:, 0] += jitter_x[coords_yx[:, 0], coords_yx[:, 1]]
    out[:, 1] += jitter_y[coords_yx[:, 0], coords_yx[:, 1]]
    return out


def _remove_enclaves(pmap: ds.RegionPixelMap, mask: ds.BooleanMaskMap, progress_controller: ProgressController) -> None:
    """Reassign disconnected region fragments to surrounding regions.

    For each region, keeps only the largest connected component.
    Smaller fragments are cleared and then filled from their nearest
    assigned neighbor, eliminating enclaves.
    """
    unique_ids = np.unique(pmap[mask])
    unique_ids = unique_ids[unique_ids >= 0]

    cleared = np.zeros(pmap.shape, dtype=bool)

    if len(unique_ids) > 0:
        # Track loop iteration through unique region IDs (dominates ~95% of enclave removal)
        for rid in progress_controller.track_iteration(unique_ids):
            region_mask = pmap == rid
            labeled, n = ndlabel(region_mask)
            if n <= 1:
                continue
            # Keep only the largest component
            comp_sizes = np.bincount(labeled.ravel())[1:]  # skip background 0
            largest = comp_sizes.argmax() + 1
            small = region_mask & (labeled != largest)
            pmap[small] = -1
            cleared |= small

    # Fill cleared pixels from nearest assigned neighbor
    if cleared.any() and (pmap >= 0).any():
        _, (ny, nx) = distance_transform_edt(pmap < 0, return_indices=True)
        pmap[cleared] = pmap[ny[cleared], nx[cleared]]


def assign_regions(
        mask: ds.BooleanMaskMap, seeds: list[ds.IntCoordinate], start_index: int,
        progress_controller: ProgressController, jagged: bool = False
    ) -> ds.RegionPixelMap:
    """
    Assign each pixel in mask to the nearest seed, respecting boundaries.

    Connected components of mask are identified — gaps left by boundary
    pixels split the mask into separate components. Seeds can only claim
    pixels within their own component, preventing assignments from crossing
    boundary lines. Seedless components are filled by nearest assigned
    pixel (Euclidean fallback).

    When jagged=True, spatially-correlated noise is added to pixel
    coordinates before the nearest-seed query, producing irregular
    borders instead of straight Voronoi edges. A post-processing pass
    removes any enclaves created by the noise.
    """

    """
    A test run (24 July 2026) with default settings gave roughly the following distribution of time
        Jitter generation / Preperation              0.130 seconds ->  5 steps
        Mask connected components labeling           0.014 seconds ->  5 steps
        KDTree spatial mapping & query               0.900 seconds -> 28 steps
        Distance transform fill for seedless areas   0.004 seconds ->  5 steps
        Enclave removal pass                         2.170 seconds -> 66 steps
    """
    jitter_phase = progress_controller.add_phase(step_weight=5)
    label_phase = progress_controller.add_phase(step_weight=5)
    assign_phase = progress_controller.add_phase(step_weight=28)
    fallback_phase = progress_controller.add_phase(step_weight=5)
    enclave_phase = progress_controller.add_phase(step_weight=66)

    with progress_controller.execute_phase(jitter_phase):
        h, w = mask.shape
        pmap: ds.RegionPixelMap = np.full((h, w), -1, np.int32)

        if not seeds or not mask.any():
            return pmap

        seeds_arr: ds.JitterSeedsArray = np.array(seeds, dtype=np.float32)

        jitter_x = jitter_y = None
        if jagged:
            jitter_x, jitter_y = _build_jitter_maps(h, w, seeds_arr)

    with progress_controller.execute_phase(label_phase):
        labeled, num_components = ndlabel(mask)

    # 3. KDTree Region Assignments
    with progress_controller.execute_phase(assign_phase) as assign_progress:
        if num_components <= 1:
            # Single component - direct KDTree query
            coords_yx: NDArray[np.intp] = np.column_stack(np.where(mask))
            coords_xy = np.flip(coords_yx, axis=1).astype(np.float32)
            query_xy = coords_xy
            if jitter_x is not None:
                query_xy = _jitter_coords(coords_xy, coords_yx, jitter_x, jitter_y)
            tree = cKDTree(seeds_arr)
            _, labels = tree.query(query_xy, k=1)
            pmap[coords_yx[:, 0], coords_yx[:, 1]] = labels + start_index
        else:
            # Map each seed to its component
            comp_seeds = {}
            for i, (x, y) in enumerate(seeds):
                comp = labeled[y, x]
                if comp > 0:
                    comp_seeds.setdefault(comp, []).append(i)

            # Per-component KDTree assignment with progress tracking
            components_iter = assign_progress.track_iteration(range(1, num_components + 1))
            for comp_id in components_iter:
                seed_indices = comp_seeds.get(comp_id)
                if not seed_indices:
                    continue

                comp_mask = labeled == comp_id
                coords_yx = np.column_stack(np.where(comp_mask))
                coords_xy = np.flip(coords_yx, axis=1).astype(np.float32)
                query_xy = coords_xy
                if jitter_x is not None:
                    query_xy = _jitter_coords(coords_xy, coords_yx, jitter_x, jitter_y)

                local_seeds = seeds_arr[seed_indices]
                tree = cKDTree(local_seeds)
                _, labels = tree.query(query_xy, k=1)

                global_indices = np.array(seed_indices, dtype=np.int32)
                pmap[coords_yx[:, 0], coords_yx[:, 1]] = (
                    global_indices[labels] + start_index
                )

    # 4. Fill seedless components via nearest assigned pixel
    with progress_controller.execute_phase(fallback_phase):
        unassigned = mask & (pmap < 0)
        if unassigned.any() and (pmap >= 0).any():
            _, (ny, nx) = distance_transform_edt(
                pmap < 0, return_indices=True
            )
            ua = unassigned
            pmap[ua] = pmap[ny[ua], nx[ua]]

    # 5. Remove enclaves created by jitter
    with progress_controller.execute_phase(enclave_phase) as enclave_progress:
        if jitter_x is not None:
            _remove_enclaves(pmap, mask, enclave_progress)

    return pmap


def is_sea_color(arr: ds.ColorPixelMap) -> ds.BooleanMaskMap:
    r, g, b = config.OCEAN_COLOR
    return (arr[..., 0] == r) & (arr[..., 1] == g) & (arr[..., 2] == b)


def is_lake_color(arr: ds.ColorPixelMap) -> ds.BooleanMaskMap:
    r, g, b = config.LAKE_COLOR
    return (arr[..., 0] == r) & (arr[..., 1] == g) & (arr[..., 2] == b)


def assign_borders(pmap: ds.RegionPixelMap, border_mask: ds.BooleanMaskMap) -> None:
    valid = pmap >= 0
    if not valid.any() or not border_mask.any():
        return

    _, (ny, nx) = distance_transform_edt(~valid, return_indices=True)
    bm = border_mask
    pmap[bm] = pmap[ny[bm], nx[bm]]


def combine_maps(
        land_map: ds.RegionPixelMap, sea_map: ds.RegionPixelMap,
        metadata: list[ds.RegionMetadata],
        land_mask: ds.BooleanMaskMap, sea_mask: ds.BooleanMaskMap,
        progress_controller: ProgressController,
    ) -> tuple[ds.TerritoryImage, ds.RegionPixelMap]:
    """Merge land/sea maps into RGB image. Returns (image, combined_pmap)."""

    """
    A test run (23 July 2026) with default settings gave roughly the following distribution of time
        combined map created               0.05 seconds ->  5 steps
        distance_transform_edt completed   0.64 seconds -> 64 steps
        color assignment completed         0.26 seconds -> 26 steps
    """
    combined_map_phase = progress_controller.add_phase(step_weight=5)
    distance_transform_phase = progress_controller.add_phase(step_weight=64)
    color_assignment_phase = progress_controller.add_phase(step_weight=26)

    with progress_controller.execute_phase(combined_map_phase):
        if land_map is not None and land_map.size > 0:
            h, w = land_map.shape
        else:
            h, w = sea_map.shape

        combined: ds.RegionPixelMap = np.full((h, w), -1, np.int32)

        if land_map is not None:
            lm = (land_map >= 0) & land_mask
            combined[lm] = land_map[lm]

        if sea_map is not None:
            sm = (sea_map >= 0) & sea_mask
            combined[sm] = sea_map[sm]

    with progress_controller.execute_phase(distance_transform_phase):
        if (combined >= 0).any():
            valid = combined >= 0
            _, (ny, nx) = distance_transform_edt(~valid, return_indices=True) # Standard t: 0.58s

            missing = combined < 0
            combined[missing] = combined[ny[missing], nx[missing]]

    with progress_controller.execute_phase(color_assignment_phase):
        out = np.zeros((h, w, 3), np.uint8)

        if metadata:
            color_lut = np.zeros((len(metadata), 3), np.uint8)

            for index, d in enumerate(metadata):
                color_lut[index] = (d.R, d.G, d.B)

            valid = combined >= 0
            out[valid] = color_lut[combined[valid]]
        image = Image.fromarray(out, mode="RGB")

    return image, combined


def extract_masks(boundary_image: ds.BoundaryImage | None, land_image: ds.LandImage | None) -> ds.Masks:
    """Extract all masks from boundary and land images.

    Returns dict with keys: boundary_mask, land_mask, sea_mask,
    land_fill, land_border, sea_fill, sea_border, map_h, map_w
    """
    if project.boundary_image is None and project.land_image is None:
        raise ValueError(
            "Need at least boundary OR ocean image to determine map size.")

    # BOUNDARY MASK
    if project.boundary_image is not None:
        b_arr = np.array(project.boundary_image, copy=False)

        if b_arr.ndim == 3:
            r, g, b = config.BOUNDARY_COLOR
            boundary_mask = (
                (b_arr[..., 0] == r) &
                (b_arr[..., 1] == g) &
                (b_arr[..., 2] == b)
            )
        else:
            (val,) = config.BOUNDARY_COLOR[:1]
            boundary_mask = (b_arr == val)

        map_h, map_w = boundary_mask.shape
    else:
        boundary_mask = None

    # LAND / SEA / LAKE MASKS
    if project.land_image is not None:
        o_arr = np.array(project.land_image, copy=False)
        sea_mask = is_sea_color(project, o_arr)
        lake_mask = is_lake_color(project, o_arr)
        land_mask = ~sea_mask  # lake pixels are part of land

        if boundary_mask is None:
            map_h, map_w = sea_mask.shape
    else:
        if boundary_mask is None:
            raise ValueError("Could not determine map size.")

        sea_mask = np.zeros((map_h, map_w), dtype=bool)
        lake_mask = np.zeros((map_h, map_w), dtype=bool)
        land_mask = np.ones((map_h, map_w), dtype=bool)

    if boundary_mask is None:
        land_fill = land_mask
        land_border = sea_mask

        sea_fill = sea_mask
        sea_border = land_mask
    else:
        land_fill = land_mask & ~boundary_mask
        land_border = boundary_mask | sea_mask

        sea_fill = sea_mask & ~boundary_mask
        sea_border = boundary_mask | land_mask

    return ds.Masks(
        boundary_mask=boundary_mask,
        land_mask=land_mask,
        sea_mask=sea_mask,
        lake_mask=lake_mask,
        land_fill=land_fill,
        land_border=land_border,
        sea_fill=sea_fill,
        sea_border=sea_border,
        map_h=map_h,
        map_w=map_w,
    )


def create_region_map(
        fill_mask: ds.BooleanMaskMap, border_mask: ds.BooleanMaskMap,
        num_points: int, start_index: int,
        series: NumberSeries,
        region_type: ds.RegionType, region_level: ds.RegionLevel,
        progress_controller: ProgressController,
        density: NDArray[Any] | None = None, density_strength: float = 1.0,
        jagged: bool = False,
    ) -> tuple[ds.RegionPixelMap, list[ds.RegionMetadata], int]:
    """
    Unified region map creator for both provinces and territories.
    """

    """
    A test run (19 August 2026) with default settings (Sliders: 3000, 300, 2.0) gave roughly the following distribution of time
    (generate_territory_map->Creating land region map): Phase completed: 'Phase 1', duration: 0.13 seconds
    (generate_territory_map->Creating land region map): Phase completed: 'Phase 2', duration: 0.38 seconds
    (generate_territory_map->Creating land region map): Phase completed: 'Phase 3', duration: 2.70 seconds
    (generate_territory_map->Creating land region map): Phase completed: 'Phase 4', duration: 0.64 seconds
    (generate_territory_map): Phase completed: 'Creating land region map', duration: 3.86 seconds

    (generate_territory_map->Creating ocean region map): Phase completed: 'Phase 1', duration: 0.09 seconds
    (generate_territory_map->Creating ocean region map): Phase completed: 'Phase 2', duration: 0.35 seconds
    (generate_territory_map->Creating ocean region map): Phase completed: 'Phase 3', duration: 1.35 seconds
    (generate_territory_map->Creating ocean region map): Phase completed: 'Phase 4', duration: 0.53 seconds
    (generate_territory_map): Phase completed: 'Creating ocean region map', duration: 2.32 seconds
    Out of this, the following step distribution is concluded:
    """

    sampling_phase = progress_controller.add_phase(step_weight=36)
    lloyd_phase = progress_controller.add_phase(step_weight=round(118 * (config.LLOYD_ITERATIONS / 4)))
    assign_phase = progress_controller.add_phase(step_weight=656)
    borders_phase = progress_controller.add_phase(step_weight=190)

    with progress_controller.execute_phase(sampling_phase):
        if num_points <= 0 or not fill_mask.any():
            empty = np.full(fill_mask.shape, -1, np.int32)
            return empty, [], start_index

        seeds = random_seeds(
            fill_mask, num_points, density=density, density_strength=density_strength
        )

    with progress_controller.execute_phase(lloyd_phase) as lloyd_progress:
        if not seeds:
            empty = np.full(fill_mask.shape, -1, np.int32)
            return empty, [], start_index
        else:
            seeds = lloyd_relaxation( # TODO: provide an rng seed for reproducibility
                mask=fill_mask, point_seeds=seeds,
                progress_controller=lloyd_progress,
                iterations=config.LLOYD_ITERATIONS,
            )

    with progress_controller.execute_phase(assign_phase) as assign_progress:
        pmap = assign_regions(fill_mask, seeds, start_index, assign_progress, jagged=jagged)

    with progress_controller.execute_phase(borders_phase) as borders_progress:
        build_phase = borders_progress.add_phase(step_weight=100)
        assign_phase = borders_progress.add_phase(step_weight=900)

        with borders_progress.execute_phase(build_phase):
            # Should be very fast, probably no substeps needed
            metadata = _build_region_metadata(
                pmap, seeds, start_index, series, region_type, region_level,
            )

        with borders_progress.execute_phase(assign_phase):
            # assign_borders is not able to create sub progress (based mostly on external functions)
            assign_borders(pmap, border_mask)
            next_index = start_index + len(seeds)

    return pmap, metadata, next_index


def _build_region_metadata(
        pmap: ds.RegionPixelMap, seeds: list[ds.IntCoordinate], start_index: int,
        series: NumberSeries, region_type: ds.RegionType, region_level: ds.RegionLevel,
    ) -> list[ds.RegionMetadata]:
    valid_mask = pmap >= 0
    ys, xs = np.where(valid_mask)
    flat = pmap[valid_mask]
    n = len(seeds)
    shifted = flat - start_index

    counts = np.bincount(shifted, minlength=n)
    sum_x = np.bincount(shifted, weights=xs.astype(float), minlength=n)
    sum_y = np.bincount(shifted, weights=ys.astype(float), minlength=n)

    metadata = []
    for i in range(n):
        if counts[i] == 0:
            continue
        index = start_index + i
        rid = series.get_id()
        if rid is None:
            continue
        r, g, b = color_from_id(index, region_type)
        metadata.append(ds.RegionMetadata(
            # For both territories & provinces
            region_level=region_level,
            R=r, G=g, B=b,
            x=sum_x[i] / counts[i],
            y=sum_y[i] / counts[i],
            _pmap_index=index,
            territory_id=rid if region_level == ds.RegionLevel.TERRITORY else None, # usually would be parent id in provinces

            # Only for provinces
            province_id=rid if region_level == ds.RegionLevel.PROVINCE else None,
            province_type=region_type if region_level == ds.RegionLevel.PROVINCE else None,
            province_terrain=None,

            # Only for territories
            territory_type=region_type if region_level == ds.RegionLevel.TERRITORY else None,
            province_ids=None,
        ))
    return metadata
