from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from opengs_maptool.logic.map_tool_protocol import MapToolProtocol

import numpy as np
from PIL import Image
from scipy.ndimage import label as ndlabel
import opengs_maptool.config as config
from opengs_maptool.logic.numb_gen import NumberSeries
from opengs_maptool.logic.utils import (
    clear_used_colors, color_from_id, create_region_map, make_progress_updater,
)


def generate_province_map(map_tool: MapToolProtocol) -> None:
    clear_used_colors()
    map_tool.start_progress()
    territory_pmap, territory_data = map_tool.get_territory_pmap_and_data()
    masks = map_tool.get_cached_masks()
    density_arr = np.array(map_tool.get_density_image().convert("L"))
    
    density_strength = map_tool.get_province_density_strength()
    exclude_ocean_density = map_tool.get_province_exclude_ocean_density()
    jagged_land = map_tool.get_province_jagged_land()
    jagged_ocean = map_tool.get_province_jagged_ocean()
    map_h, map_w = masks["map_h"], masks["map_w"]

    total_land_provs = map_tool.get_province_land_province_density()
    total_ocean_provs = map_tool.get_province_ocean_province_density()
    lake_mask = masks.get("lake_mask")

    # Separate territories by type
    land_terrs = [d for d in territory_data if d["territory_type"] == "land"]
    ocean_terrs = [d for d in territory_data if d["territory_type"] == "ocean"]

    # Build set of ocean territory indices for density exclusion
    ocean_terr_indices = set()
    if exclude_ocean_density:
        for d in ocean_terrs:
            ocean_terr_indices.add(d["_pmap_index"])

    # Count pixels per territory for proportional distribution
    unique, counts = np.unique(
        territory_pmap[territory_pmap >= 0], return_counts=True)
    pixel_counts = dict(zip(unique.tolist(), counts.tolist()))

    # Compute average density weight per territory (darker = higher weight)
    # Ocean territories get normalized weight when excluded
    density_weights = {}
    for idx in unique:
        if int(idx) in ocean_terr_indices:
            density_weights[int(idx)] = 1.0
        else:
            terr_mask = territory_pmap == idx
            mean_val = density_arr[terr_mask].mean()
            density_weights[int(idx)] = (256.0 - mean_val) ** density_strength

    land_alloc = _distribute(land_terrs, total_land_provs, pixel_counts,
                             density_weights)
    ocean_alloc = _distribute(ocean_terrs, total_ocean_provs, pixel_counts,
                              density_weights)

    all_terrs = ([(d, land_alloc[i]) for i, d in enumerate(land_terrs)] +
                 [(d, ocean_alloc[i]) for i, d in enumerate(ocean_terrs)])

    # Progress: one step per territory + setup/finalize
    total_steps = 2 + len(all_terrs) + 2
    step = make_progress_updater(map_tool.set_progress, total_steps)
    step(2)

    series = NumberSeries(
        config.PROVINCE_ID_PREFIX,
        config.PROVINCE_ID_START,
        config.PROVINCE_ID_END
    )

    province_pmap = np.full((map_h, map_w), -1, np.int32)
    all_metadata = []
    start_index = 0
    boundary_mask = masks.get("boundary_mask")
    if boundary_mask is None:
        boundary_mask = np.zeros((map_h, map_w), dtype=bool)

    # Build territory lookup by _pmap_index
    terr_by_index = {d["_pmap_index"]: d for d in territory_data}

    # Create lake provinces globally — each connected lake is one province,
    # assigned to the territory that contains its center
    if lake_mask is not None and lake_mask.any():
        labeled, num_lakes = ndlabel(lake_mask)
        for comp_id in range(1, num_lakes + 1):
            comp_mask = labeled == comp_id
            rid = series.get_id()
            if rid is None:
                continue
            r, g, b = color_from_id(start_index, "lake")
            ys, xs = np.where(comp_mask)
            cx, cy = int(round(xs.mean())), int(round(ys.mean()))
            terr_idx = int(territory_pmap[cy, cx])
            terr = terr_by_index.get(terr_idx)
            tid = terr["territory_id"] if terr else ""
            lake_entry = {
                "province_id": rid,
                "province_type": "lake",
                "R": r, "G": g, "B": b,
                "x": xs.mean(),
                "y": ys.mean(),
                "territory_id": tid,
                "_pmap_index": start_index,
            }
            province_pmap[comp_mask] = start_index
            all_metadata.append(lake_entry)
            if terr is not None:
                terr.setdefault("province_ids", []).append(rid)
            start_index += 1

    for terr, prov_count in all_terrs:
        terr_mask = territory_pmap == terr["_pmap_index"]
        ptype = terr["territory_type"]
        tid = terr["territory_id"]

        # Subdivide non-lake pixels in this territory
        if lake_mask is not None:
            terr_fill = terr_mask & ~lake_mask & ~boundary_mask
            terr_border = (terr_mask & boundary_mask) | (terr_mask & lake_mask)
        else:
            terr_fill = terr_mask & ~boundary_mask
            terr_border = terr_mask & boundary_mask

        if exclude_ocean_density and ptype == "ocean":
            terr_density = None
            terr_density_strength = 1.0
        else:
            terr_density = density_arr
            terr_density_strength = density_strength

        jagged = jagged_land if ptype == "land" else jagged_ocean
        pmap, meta, next_index = create_region_map(
            terr_fill, terr_border, prov_count, start_index,
            ptype, series, "province_id", "province_type",
            density=terr_density, density_strength=terr_density_strength,
            jagged=jagged
        )

        # Tag each province with its parent territory
        for m in meta:
            m["territory_id"] = tid

        # Merge into global province pmap (don't overwrite lake provinces)
        valid = (pmap >= 0) & (province_pmap < 0)
        province_pmap[valid] = pmap[valid]

        # Collect province_ids for territory (append to any existing lake ids)
        existing = terr.get("province_ids", [])
        terr["province_ids"] = existing + [m["province_id"] for m in meta]

        all_metadata.extend(meta)
        start_index = next_index
        step(1)

    # Build province image via color lookup
    out = np.zeros((map_h, map_w, 3), np.uint8)
    if all_metadata and start_index > 0:
        color_lut = np.zeros((start_index, 3), np.uint8)
        for d in all_metadata:
            idx = d["_pmap_index"]
            color_lut[idx] = (d["R"], d["G"], d["B"])
        valid = province_pmap >= 0
        out[valid] = color_lut[province_pmap[valid]]
    province_image = Image.fromarray(out)
    step(1)

    # Assign terrain from terrain image, or use defaults
    terrain_image = map_tool.get_terrain_image()
    if terrain_image is not None:
        terrain_arr = np.array(terrain_image)
        _assign_terrain(all_metadata, terrain_arr)
    else:
        for prov in all_metadata:
            ptype = prov["province_type"]
            if ptype == "lake":
                prov["province_terrain"] = config.DEFAULT_TERRAIN_LAKE
            elif ptype == "ocean":
                prov["province_terrain"] = config.DEFAULT_TERRAIN_OCEAN
            else:
                prov["province_terrain"] = config.DEFAULT_TERRAIN_LAND

    map_tool.set_province_image(province_image)
    map_tool.set_province_data(all_metadata)
    step(1)

    map_tool.set_progress(100)
    map_tool.set_province_export_available(True)
    map_tool.set_territory_history_export_available(True)

    return province_image, all_metadata


def _distribute(territories, total_provinces, pixel_counts,
                density_weights=None) -> list[int]:
    """Distribute total_provinces proportionally across territories.

    When density_weights is provided, each territory's pixel count is scaled
    by its density weight so darker regions receive more provinces.
    Each territory gets at least 1 province.
    """
    n = len(territories)
    if n == 0 or total_provinces <= 0:
        return [0] * n

    terr_pixels = [pixel_counts.get(d["_pmap_index"], 0) for d in territories]

    if density_weights is not None:
        terr_pixels = [px * density_weights.get(d["_pmap_index"], 1.0)
                       for px, d in zip(terr_pixels, territories)]

    total_pixels = sum(terr_pixels)

    if total_pixels == 0:
        return [1] * n

    # Initial proportional allocation (minimum 1)
    alloc = [max(1, round(px / total_pixels * total_provinces))
             for px in terr_pixels]

    # Adjust to match total (skip if more territories than provinces)
    diff = sum(alloc) - total_provinces
    if diff != 0 and total_provinces >= n:
        # Sort by pixel count: shrink largest first, grow smallest first
        indices = sorted(range(n), key=lambda i: terr_pixels[i],
                         reverse=(diff > 0))
        for i in indices:
            if diff == 0:
                break
            if diff > 0 and alloc[i] > 1:
                alloc[i] -= 1
                diff -= 1
            elif diff < 0:
                alloc[i] += 1
                diff += 1

    return alloc


def _assign_terrain(metadata, terrain_arr) -> None:
    """Look up terrain color at each province center and assign province_terrain.

    Enforces category constraints: land provinces only get land terrains,
    ocean provinces only get naval terrains, lake provinces get lake terrain.
    Falls back to the configured default for each province type.
    """
    h, w = terrain_arr.shape[:2]

    # Build per-category lookups: (R, G, B) -> terrain name
    land_lookup = {color: name for name, color in config.LAND_TERRAIN_TYPES.items()}
    naval_lookup = {color: name for name, color in config.NAVAL_TERRAIN_TYPES.items()}
    lake_lookup = {color: name for name, color in config.LAKE_TERRAIN_TYPES.items()}

    for prov in metadata:
        px = int(round(prov["x"]))
        py = int(round(prov["y"]))
        px = max(0, min(px, w - 1))
        py = max(0, min(py, h - 1))
        pixel = (int(terrain_arr[py, px, 0]),
                 int(terrain_arr[py, px, 1]),
                 int(terrain_arr[py, px, 2]))

        ptype = prov["province_type"]
        if ptype == "lake":
            prov["province_terrain"] = lake_lookup.get(pixel, config.DEFAULT_TERRAIN_LAKE)
        elif ptype == "ocean":
            prov["province_terrain"] = naval_lookup.get(pixel, config.DEFAULT_TERRAIN_OCEAN)
        else:
            prov["province_terrain"] = land_lookup.get(pixel, config.DEFAULT_TERRAIN_LAND)
