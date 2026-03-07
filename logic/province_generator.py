import config
import numpy as np
from PIL import Image
from logic.numb_gen import NumberSeries
from logic.utils import (
    clear_used_colors, create_region_map, make_progress_updater,
    STEPS_PER_REGION_MAP
)


def generate_province_map(main_layout):
    clear_used_colors()
    main_layout.progress.setVisible(True)
    main_layout.progress.setValue(0)

    territory_pmap = main_layout.territory_pmap
    territory_data = main_layout.territory_data
    masks = main_layout.cached_masks
    map_h, map_w = masks["map_h"], masks["map_w"]

    total_land_provs = main_layout.land_slider.value()
    total_ocean_provs = main_layout.ocean_slider.value()

    # Separate territories by type
    land_terrs = [d for d in territory_data if d["territory_type"] == "land"]
    ocean_terrs = [d for d in territory_data if d["territory_type"] == "ocean"]

    # Count pixels per territory for proportional distribution
    unique, counts = np.unique(
        territory_pmap[territory_pmap >= 0], return_counts=True)
    pixel_counts = dict(zip(unique.tolist(), counts.tolist()))

    land_alloc = _distribute(land_terrs, total_land_provs, pixel_counts)
    ocean_alloc = _distribute(ocean_terrs, total_ocean_provs, pixel_counts)

    all_terrs = ([(d, land_alloc[i]) for i, d in enumerate(land_terrs)] +
                 [(d, ocean_alloc[i]) for i, d in enumerate(ocean_terrs)])

    # Progress: one step per territory + setup/finalize
    total_steps = 2 + len(all_terrs) + 2
    step = make_progress_updater(main_layout, total_steps)
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

    for terr, prov_count in all_terrs:
        terr_mask = territory_pmap == terr["_pmap_index"]
        ptype = terr["territory_type"]
        tid = terr["territory_id"]

        # Use boundary lines within this territory to split provinces,
        # just like territory generation uses them to split territories.
        terr_fill = terr_mask & ~boundary_mask
        terr_border = terr_mask & boundary_mask

        pmap, meta, next_index = create_region_map(
            terr_fill, terr_border, prov_count, start_index,
            ptype, series, "province_id", "province_type"
        )

        # Tag each province with its parent territory
        for m in meta:
            m["territory_id"] = tid

        # Merge into global province pmap
        valid = pmap >= 0
        province_pmap[valid] = pmap[valid]

        # Collect province_ids for territory
        terr["province_ids"] = [m["province_id"] for m in meta]

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

    main_layout.province_image_display.set_image(province_image)
    main_layout.province_data = all_metadata
    step(1)

    main_layout.progress.setValue(100)
    main_layout.button_exp_prov_img.setEnabled(True)
    main_layout.button_exp_prov_def.setEnabled(True)
    main_layout.button_exp_terr_hist.setEnabled(True)

    return province_image, all_metadata


def _distribute(territories, total_provinces, pixel_counts):
    """Distribute total_provinces proportionally across territories by pixel count.

    Each territory gets at least 1 province.
    """
    n = len(territories)
    if n == 0 or total_provinces <= 0:
        return [0] * n

    terr_pixels = [pixel_counts.get(d["_pmap_index"], 0) for d in territories]
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
