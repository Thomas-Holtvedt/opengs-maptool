import config
import numpy as np
from collections import deque
from PIL import Image
from scipy.ndimage import distance_transform_edt


def generate_province_map(main_layout):
    boundary_image = main_layout.boundary_image_display.get_image()
    land_image = main_layout.land_image_display.get_image()

    if boundary_image is None and land_image is None:
        raise ValueError(
            "Need at least boundary OR ocean image to determine map size."
        )

    # BOUNDARY MASK
    if boundary_image is not None:
        b_arr = np.array(boundary_image, copy=False)
        if b_arr.ndim == 3:
            boundary_mask = b_arr[..., 0] < 128
        else:
            boundary_mask = b_arr < 128

        map_h, map_w = boundary_mask.shape

    else:
        boundary_mask = None

    if land_image is not None:
        o_arr = np.array(land_image, copy=False)
        sea_mask = is_sea_color(o_arr)
        land_mask = ~sea_mask

        # If boundary does not exist, define size from land image
        if boundary_mask is None:
            map_h, map_w = sea_mask.shape
    else:
        # No land_image means "treat everything as land"
        if boundary_mask is None:
            raise ValueError("Could not determine map size.")

        sea_mask = np.zeros((map_h, map_w), dtype=bool)
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

    # GENERATE PROVINCES
    start_id = 0
    land_points = main_layout.land_slider.value()
    sea_points = main_layout.ocean_slider.value()

    land_map, land_meta, next_id = create_province_map(
        land_fill, land_border, land_points, start_id, "land"
    )

    if sea_points > 0 and land_image is not None:
        sea_map, sea_meta, _ = create_province_map(
            sea_fill, sea_border, sea_points, next_id, "ocean"
        )
    else:
        sea_map = np.full((map_h, map_w), -1, np.int32)
        sea_meta = []

    metadata = land_meta + sea_meta

    province_image = combine_maps(
        land_map, sea_map, metadata, land_mask, sea_mask
    )

    main_layout.province_image_display.set_image(province_image)
    main_layout.province_data = metadata

    return province_image, metadata


#  BASIC UTILITIES
def is_sea_color(arr):
    r, g, b = config.OCEAN_COLOR
    return (arr[..., 0] == r) & (arr[..., 1] == g) & (arr[..., 2] == b)


def _color_from_id(pid: int):
    rng = np.random.default_rng(pid + 1)
    r, g, b = map(int, rng.integers(1, 256, 3))

    # Avoid extremely dark colors
    if r < 20 and g < 20 and b < 20:
        r = (r + 50) % 256
        g = (g + 50) % 256
        b = (b + 50) % 256

    return r, g, b


def generate_jitter_seeds(mask: np.ndarray, num_points: int):
    if num_points <= 0:
        return []

    h, w = mask.shape
    grid = max(1, int(np.sqrt(num_points)))

    cell_h = h / grid
    cell_w = w / grid

    rng = np.random.default_rng(12345)
    seeds = []

    for gy in range(grid):
        y0 = int(gy * cell_h)
        y1 = int((gy + 1) * cell_h)

        for gx in range(grid):
            x0 = int(gx * cell_w)
            x1 = int((gx + 1) * cell_w)

            cell = mask[y0:y1, x0:x1]
            ys, xs = np.where(cell)

            if xs.size == 0:
                continue

            i = rng.integers(xs.size)
            seeds.append((x0 + xs[i], y0 + ys[i]))

    return seeds


def create_province_map(fill_mask, border_mask, num_points, start_id, ptype):
    if num_points <= 0 or not fill_mask.any():
        empty = np.full(fill_mask.shape, -1, np.int32)
        return empty, [], start_id

    seeds = generate_jitter_seeds(fill_mask, num_points)
    seeds = [(x, y) for x, y in seeds if fill_mask[y, x]]  # safety

    if not seeds:
        empty = np.full(fill_mask.shape, -1, np.int32)
        return empty, [], start_id

    pmap, metadata = flood_fill(fill_mask, seeds, start_id, ptype)
    assign_borders(pmap, border_mask)
    finalize_metadata(metadata)

    next_id = max(metadata.keys()) + 1 if metadata else start_id
    return pmap, list(metadata.values()), next_id


def flood_fill(fill_mask, seeds, start_id, ptype):
    h, w = fill_mask.shape
    pmap = np.full((h, w), -1, np.int32)

    metadata = {}
    q = deque()

    neighbors = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    _color = _color_from_id

    for i, (sx, sy) in enumerate(seeds):
        pid = start_id + i
        pmap[sy, sx] = pid

        r, g, b = _color(pid)
        metadata[pid] = {
            "province_id": pid,
            "province_type": ptype,
            "R": r, "G": g, "B": b,
            "sum_x": sx,
            "sum_y": sy,
            "count": 1
        }

        q.append((sx, sy, pid))

    while q:
        x, y, pid = q.popleft()
        d = metadata[pid]

        for dx, dy in neighbors:
            nx = x + dx
            ny = y + dy

            if 0 <= nx < w and 0 <= ny < h:
                if pmap[ny, nx] == -1 and fill_mask[ny, nx]:
                    pmap[ny, nx] = pid
                    d["sum_x"] += nx
                    d["sum_y"] += ny
                    d["count"] += 1
                    q.append((nx, ny, pid))

    return pmap, metadata


def assign_borders(pmap, border_mask):
    valid = pmap >= 0
    if not valid.any() or not border_mask.any():
        return

    _, (ny, nx) = distance_transform_edt(~valid, return_indices=True)
    bm = border_mask
    pmap[bm] = pmap[ny[bm], nx[bm]]


def finalize_metadata(metadata):
    for d in metadata.values():
        c = d["count"]
        d["x"] = d["sum_x"] / c
        d["y"] = d["sum_y"] / c
        del d["sum_x"], d["sum_y"], d["count"]


def combine_maps(land_map, sea_map, metadata, land_mask, sea_mask):
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

    # Fill remaining areas by nearest province
    if (combined >= 0).any():
        valid = combined >= 0
        _, (ny, nx) = distance_transform_edt(~valid, return_indices=True)
        missing = combined < 0
        combined[missing] = combined[ny[missing], nx[missing]]

    out = np.zeros((h, w, 3), np.uint8)

    if not metadata:
        return Image.fromarray(out)

    max_id = max(d["province_id"] for d in metadata)
    color_lut = np.zeros((max_id + 1, 3), np.uint8)

    for d in metadata:
        pid = d["province_id"]
        color_lut[pid] = (d["R"], d["G"], d["B"])

    valid = combined >= 0
    out[valid] = color_lut[combined[valid]]

    return Image.fromarray(out)
