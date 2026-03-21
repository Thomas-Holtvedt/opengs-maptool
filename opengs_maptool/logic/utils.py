from __future__ import annotations
from typing import Any, Callable, TypeAlias

import opengs_maptool.config as config
import numpy as np
from numpy.typing import NDArray
from PIL import Image
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt, label as ndlabel
from PyQt6.QtWidgets import QApplication

MAX_LLOYD_SAMPLE = 100_000

# Steps per create_region_map: sampling=1, lloyd=LLOYD_ITERATIONS, assign=1, meta+borders=1
STEPS_PER_REGION_MAP: int = 1 + config.LLOYD_ITERATIONS + 1 + 1

used_colors = set()


def clear_used_colors() -> None:
    used_colors.clear()


def color_from_id(index: int, ptype: str) -> tuple[int, int, int]:
    rng = np.random.default_rng(index + 1)
    while True:
        if ptype == "ocean":
            r = rng.integers(0, 60)
            g = rng.integers(0, 80)
            b = rng.integers(100, 180)
        elif ptype == "lake":
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
        mask: NDArray[np.bool_], num_points: int, rng_seed: int | None = None,
        density: NDArray[np.uint8] | None = None, density_strength: float = 1.0,
    ) -> list[tuple[int, int]]:
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
        mask: NDArray[np.bool], point_seeds: list[tuple[int, int]], rng_seed: int | None = None,
        iterations: int = 4, step_fn: Callable[[int], None] | None = None,
    ) -> list[tuple[int, int]]:
    """
    Improve seed placement by iteratively moving each seed to the centroid
    of its Voronoi cell.
    """
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

    for _ in range(iterations):
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

        if step_fn is not None:
            step_fn(1)

    return [(int(x), int(y)) for x, y in seeds_arr]


def _build_jitter_maps(h: int, w: int, seeds_arr: NDArray[np.float32]) -> tuple[NDArray[np.float32] | None, NDArray[np.float32] | None]:
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
        coords_xy: NDArray[np.float32], coords_yx: NDArray[np.intp],
        jitter_x: NDArray[np.float32], jitter_y: NDArray[np.float32],
    ) -> NDArray[np.float32]:
    """Return a copy of coords_xy with spatially-correlated noise added."""
    out = coords_xy.copy()
    out[:, 0] += jitter_x[coords_yx[:, 0], coords_yx[:, 1]]
    out[:, 1] += jitter_y[coords_yx[:, 0], coords_yx[:, 1]]
    return out


def _remove_enclaves(pmap: NDArray[np.int32], mask: NDArray[np.bool]) -> None:
    """Reassign disconnected region fragments to surrounding regions.

    For each region, keeps only the largest connected component.
    Smaller fragments are cleared and then filled from their nearest
    assigned neighbor, eliminating enclaves.
    """
    unique_ids = np.unique(pmap[mask])
    unique_ids = unique_ids[unique_ids >= 0]

    cleared = np.zeros(pmap.shape, dtype=bool)

    for rid in unique_ids:
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
        mask: NDArray[np.bool], seeds: list[tuple[int, int]],
        start_index: int, jagged: bool = False
    ) -> NDArray[np.int32]:
    """
    Assign each pixel in mask to the nearest seed, respecting boundaries.

    Connected components of mask are identified — gaps left by boundary
    pixels split the mask into separate components.  Seeds can only claim
    pixels within their own component, preventing assignments from crossing
    boundary lines.  Seedless components are filled by nearest assigned
    pixel (Euclidean fallback).

    When jagged=True, spatially-correlated noise is added to pixel
    coordinates before the nearest-seed query, producing irregular
    borders instead of straight Voronoi edges.  A post-processing pass
    removes any enclaves created by the noise.
    """
    h, w = mask.shape
    pmap = np.full((h, w), -1, np.int32)

    if not seeds or not mask.any():
        return pmap

    seeds_arr = np.array(seeds, dtype=np.float32)

    # Precompute jitter noise maps if jagged borders enabled
    jitter_x = jitter_y = None
    if jagged:
        jitter_x, jitter_y = _build_jitter_maps(h, w, seeds_arr)

    # Label connected components of mask
    labeled, num_components = ndlabel(mask)

    if num_components <= 1:
        # Single component (or empty) — fast global KDTree
        coords_yx = np.column_stack(np.where(mask))
        coords_xy = np.flip(coords_yx, axis=1).astype(np.float32)
        query_xy = coords_xy
        if jitter_x is not None:
            query_xy = _jitter_coords(coords_xy, coords_yx,
                                      jitter_x, jitter_y)
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

        # Per-component KDTree assignment
        for comp_id in range(1, num_components + 1):
            seed_indices = comp_seeds.get(comp_id)
            if not seed_indices:
                continue

            comp_mask = labeled == comp_id
            coords_yx = np.column_stack(np.where(comp_mask))
            coords_xy = np.flip(coords_yx, axis=1).astype(np.float32)
            query_xy = coords_xy
            if jitter_x is not None:
                query_xy = _jitter_coords(coords_xy, coords_yx,
                                          jitter_x, jitter_y)

            local_seeds = seeds_arr[seed_indices]
            tree = cKDTree(local_seeds)
            _, labels = tree.query(query_xy, k=1)

            global_indices = np.array(seed_indices, dtype=np.int32)
            pmap[coords_yx[:, 0], coords_yx[:, 1]] = (
                global_indices[labels] + start_index)

        # Fill seedless components via nearest assigned pixel
        unassigned = mask & (pmap < 0)
        if unassigned.any() and (pmap >= 0).any():
            _, (ny, nx) = distance_transform_edt(
                pmap < 0, return_indices=True)
            ua = unassigned
            pmap[ua] = pmap[ny[ua], nx[ua]]

    # Remove enclaves created by jitter
    if jitter_x is not None:
        _remove_enclaves(pmap, mask)

    return pmap


def is_sea_color(arr: NDArray[np.uint8]) -> NDArray[np.bool]:
    r, g, b = config.OCEAN_COLOR
    return (arr[..., 0] == r) & (arr[..., 1] == g) & (arr[..., 2] == b)


def is_lake_color(arr: NDArray[np.uint8]) -> NDArray[np.bool]:
    r, g, b = config.LAKE_COLOR
    return (arr[..., 0] == r) & (arr[..., 1] == g) & (arr[..., 2] == b)


def assign_borders(pmap: NDArray[np.int32], border_mask: NDArray[np.bool]) -> None:
    valid = pmap >= 0
    if not valid.any() or not border_mask.any():
        return

    _, (ny, nx) = distance_transform_edt(~valid, return_indices=True)
    bm = border_mask
    pmap[bm] = pmap[ny[bm], nx[bm]]


def combine_maps(
        land_map: NDArray[np.int32] | None,
        sea_map: NDArray[np.int32] | None,
        metadata: list[dict],
        land_mask: NDArray[np.bool_],
        sea_mask: NDArray[np.bool_],
    ) -> tuple[Image.Image, NDArray[np.int32]]:
    """Merge land/sea maps into RGB image. Returns (image, combined_pmap)."""
    if land_map is not None and land_map.size > 0:
        h, w = land_map.shape
    else:
        h, w = sea_map.shape

    combined = np.full((h, w), -1, np.int32)

    if land_map is not None:
        lm = (land_map >= 0) & land_mask
        combined[lm] = land_map[lm]

    if sea_map is not None:
        sm = (sea_map >= 0) & sea_mask
        combined[sm] = sea_map[sm]

    if (combined >= 0).any():
        valid = combined >= 0
        _, (ny, nx) = distance_transform_edt(~valid, return_indices=True)
        missing = combined < 0
        combined[missing] = combined[ny[missing], nx[missing]]

    out = np.zeros((h, w, 3), np.uint8)

    if not metadata:
        return Image.fromarray(out), combined

    color_lut = np.zeros((len(metadata), 3), np.uint8)

    for index, d in enumerate(metadata):
        color_lut[index] = (d["R"], d["G"], d["B"])

    valid = combined >= 0
    out[valid] = color_lut[combined[valid]]

    return Image.fromarray(out), combined


def make_progress_updater(set_progress: Callable[[int], None], total_steps: int) -> Callable[[int], None]:
    done = [0]

    def step(n=1) -> None:
        done[0] = min(done[0] + n, total_steps)
        set_progress(int(done[0] * 100 / total_steps))
        QApplication.processEvents()

    return step


def extract_masks(
        boundary_image: Image.Image | None, land_image: Image.Image | None,
    ) -> dict[str, NDArray[np.bool] | int | None]:
    """Extract all masks from boundary and land images.

    Returns dict with keys: boundary_mask, land_mask, sea_mask,
    land_fill, land_border, sea_fill, sea_border, map_h, map_w
    """
    if boundary_image is None and land_image is None:
        raise ValueError(
            "Need at least boundary OR ocean image to determine map size.")

    # BOUNDARY MASK
    if boundary_image is not None:
        b_arr = np.array(boundary_image, copy=False)

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
    if land_image is not None:
        o_arr = np.array(land_image, copy=False)
        sea_mask = is_sea_color(o_arr)
        lake_mask = is_lake_color(o_arr)
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

    return {
        "boundary_mask": boundary_mask,
        "land_mask": land_mask,
        "sea_mask": sea_mask,
        "lake_mask": lake_mask,
        "land_fill": land_fill,
        "land_border": land_border,
        "sea_fill": sea_fill,
        "sea_border": sea_border,
        "map_h": map_h,
        "map_w": map_w,
    }


def create_region_map(fill_mask: NDArray[np.bool_], border_mask: NDArray[np.bool_],
                      num_points: int, start_index: int, ptype: str,
                      series, id_key: str, type_key: str,
                      step_fn: Callable[[int], None] | None = None,
                      density: NDArray[np.uint8] | None = None,
                      density_strength: float = 1.0, jagged: bool = False
    ) -> tuple[NDArray[np.int32], list[dict], int]:
    """Unified region map creator for both provinces and territories.

    id_key/type_key control metadata key names (e.g. "province_id"/"province_type"
    or "territory_id"/"territory_type").
    """
    _step = step_fn if step_fn is not None else (lambda n=1: None)

    if num_points <= 0 or not fill_mask.any():
        _step(STEPS_PER_REGION_MAP)
        empty = np.full(fill_mask.shape, -1, np.int32)
        return empty, [], start_index

    seeds = random_seeds(fill_mask, num_points, density=density,
                         density_strength=density_strength)
    _step(1)  # sampling done

    if not seeds:
        _step(config.LLOYD_ITERATIONS + 1 + 1)
        empty = np.full(fill_mask.shape, -1, np.int32)
        return empty, [], start_index

    seeds = lloyd_relaxation(fill_mask, seeds,
                             iterations=config.LLOYD_ITERATIONS, step_fn=_step)

    pmap = assign_regions(fill_mask, seeds, start_index, jagged=jagged)
    _step(1)  # assign done

    metadata = _build_region_metadata(pmap, seeds, start_index, ptype,
                                      series, id_key, type_key)
    assign_borders(pmap, border_mask)
    _step(1)  # meta + borders done

    next_index = start_index + len(seeds)
    return pmap, metadata, next_index


def _build_region_metadata(pmap: NDArray[np.int32], seeds: list[tuple[int, int]],
        start_index: int, ptype: str,
        series: Any, id_key: str, type_key: str,
    ) -> list[dict]:
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
        r, g, b = color_from_id(index, ptype)
        metadata.append({
            id_key: rid,
            type_key: ptype,
            "R": r, "G": g, "B": b,
            "x": sum_x[i] / counts[i],
            "y": sum_y[i] / counts[i],
            "_pmap_index": index,
        })
    return metadata
