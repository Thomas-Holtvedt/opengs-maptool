from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from opengs_maptool.logic.map_tool_protocol import MapToolProtocol

import opengs_maptool.config as config
import numpy as np
from opengs_maptool.logic.numb_gen import NumberSeries
from opengs_maptool.logic.utils import (
    clear_used_colors, extract_masks, create_region_map, combine_maps,
    make_progress_updater, STEPS_PER_REGION_MAP
)


def generate_territory_map(map_tool: MapToolProtocol) -> None:
    clear_used_colors()
    map_tool.start_progress()

    boundary_image = map_tool.get_boundary_image()
    land_image = map_tool.get_land_image()

    masks = extract_masks(boundary_image, land_image)

    series = NumberSeries(
        config.TERRITORY_ID_PREFIX,
        config.TERRITORY_ID_START,
        config.TERRITORY_ID_END
    )

    density_arr = np.array(map_tool.get_density_image().convert("L"))
    density_strength = map_tool.get_territory_density_strength()
    exclude_ocean_density = map_tool.get_territory_exclude_ocean_density()
    jagged_land = map_tool.get_territory_jagged_land()
    jagged_ocean = map_tool.get_territory_jagged_ocean()

    land_points = map_tool.get_territory_land_density()
    sea_points = map_tool.get_territory_ocean_density()
    has_sea = sea_points > 0 and land_image is not None

    sea_step_budget = STEPS_PER_REGION_MAP if has_sea else 2
    total_steps = 2 + STEPS_PER_REGION_MAP + sea_step_budget + 2
    step = make_progress_updater(map_tool.set_progress, total_steps)
    step(2)  # setup complete

    land_map, land_meta, next_index = create_region_map(
        masks["land_fill"], masks["land_border"], land_points, 0,
        "land", series, "territory_id", "territory_type", step_fn=step,
        density=density_arr, density_strength=density_strength,
        jagged=jagged_land
    )

    sea_density = None if exclude_ocean_density else density_arr
    sea_density_strength = 1.0 if exclude_ocean_density else density_strength

    if has_sea:
        sea_map, sea_meta, _ = create_region_map(
            masks["sea_fill"], masks["sea_border"], sea_points, next_index,
            "ocean", series, "territory_id", "territory_type", step_fn=step,
            density=sea_density, density_strength=sea_density_strength,
            jagged=jagged_ocean
        )
    else:
        sea_map = np.full((masks["map_h"], masks["map_w"]), -1, np.int32)
        sea_meta = []
        step(2)

    metadata = land_meta + sea_meta

    territory_image, combined_pmap = combine_maps(
        land_map, sea_map, metadata, masks["land_mask"], masks["sea_mask"]
    )
    step(1)

    map_tool.set_territory_image(territory_image)
    map_tool.set_territory_pmap_and_data(combined_pmap, metadata)
    map_tool.set_cached_masks(masks)
    step(1)

    map_tool.set_progress(100)

    # Enable province generation and territory image export
    map_tool.set_province_gen_available(True)
    map_tool.set_territory_export_available(True)

    # Reset province state if re-generating territories
    map_tool.set_province_data(None)
    map_tool.set_province_export_available(False)
    map_tool.set_territory_history_export_available(False)

    return territory_image, metadata
