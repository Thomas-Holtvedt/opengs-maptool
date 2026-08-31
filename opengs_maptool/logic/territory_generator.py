from __future__ import annotations
from typing import TYPE_CHECKING, Any
if TYPE_CHECKING:
    from opengs_maptool.context import LimitedTaskContext

import numpy as np
from numpy.typing import NDArray
import opengs_maptool.config as config
from opengs_maptool.controllers.progress_controller import ProgressController
from opengs_maptool.logic.numb_gen import NumberSeries
from opengs_maptool.logic.utils import (
    clear_used_colors, extract_masks, create_region_map, combine_maps,
)
import opengs_maptool.logic.datastructure as ds
from opengs_maptool.simple_types import TabName

def generate_territory_map(
        task_ctx: LimitedTaskContext, progress_controller: ProgressController
    ) -> tuple[ds.TerritoryImage, list[ds.RegionMetadata]] | tuple[None, None]:
    """
    Generate a territory map for the given project, updating the progress with "virtually calculated step numbers" as it goes.
    """
    # Safety check matching the button setEnabled condition
    if not task_ctx.project.can_territory_image_be_generated():
        return None, None

    """
    A test run (23. July 2026) with default settings gave roughly the following distribution of time
    (every step is rounded up to at least 20/1000 steps to be visible)
    ("‰" means 1/1000)
       20‰: phase1
       20‰: phase2
      495‰: phase3
      341‰: phase4
      104‰: phase5
       20‰: phase6
    """
    phase1 = progress_controller.add_phase(step_weight=20, msg="Extracting masks")
    phase2 = progress_controller.add_phase(step_weight=20, msg="Setting up data")
    phase3 = progress_controller.add_phase(step_weight=495, msg="Creating land region map")
    phase4 = progress_controller.add_phase(step_weight=341, msg="Creating ocean region map")
    phase5 = progress_controller.add_phase(step_weight=104, msg="Combining land & ocean maps")
    phase6 = progress_controller.add_phase(step_weight=20, msg="Finalizing")

    # Pretty much instant, sub-steps are not worth it
    with progress_controller.execute_phase(phase1):
        project = task_ctx.project
        clear_used_colors()
        masks = extract_masks(project)

        series = NumberSeries(
            config.TERRITORY_ID_PREFIX,
            config.TERRITORY_ID_START,
            config.TERRITORY_ID_END
        )

    with progress_controller.execute_phase(phase2):
        density_arr: NDArray[Any] = np.array(project.density_image)
        density_strength = project.territory_density_strength / 10.0
        exclude_ocean_density = project.territory_exclude_ocean
        jagged_land = project.territory_jagged_land
        jagged_ocean = project.territory_jagged_ocean

        land_points = project.land_territory_density
        sea_points = project.oceanic_territory_density
        has_sea = sea_points > 0 and project.land_image is not None


    with progress_controller.execute_phase(phase3) as sub_progress3:
        land_map, land_meta, next_index = create_region_map(
            masks.land_fill, masks.land_border, land_points, 0,
            series, ds.RegionType.LAND, ds.RegionLevel.TERRITORY,
            sub_progress3,
            density=density_arr, density_strength=density_strength,
            jagged=jagged_land,
        )

    with progress_controller.execute_phase(phase4) as sub_progress4:
        if has_sea:
            # next two lines: instant, sub-steps are not worth it
            sea_density = None if exclude_ocean_density else density_arr
            sea_density_strength = 1.0 if exclude_ocean_density else density_strength

            sea_map, sea_meta, next_index = create_region_map(
                masks.sea_fill, masks.sea_border, sea_points, next_index,
                series, ds.RegionType.OCEAN, ds.RegionLevel.TERRITORY,
                sub_progress4,
                density=sea_density, density_strength=sea_density_strength,
                jagged=jagged_ocean,
            )
        else:
            # Consume sub_progress4 (which surprisingly isn't nededed) to keep the progress bar moving
            sea_map: ds.RegionPixelMap = np.full((masks.map_h, masks.map_w), -1, np.int32)
            sea_meta = []

    with progress_controller.execute_phase(phase5) as sub_progress5:
        metadata = land_meta + sea_meta

        territory_image, combined_pmap = combine_maps(
            land_map, sea_map, metadata, masks.land_mask, masks.sea_mask,
            sub_progress5,
        )

    with progress_controller.execute_phase(phase6):
        # Is instant, sub-steps are not worth it
        project.territory_image = territory_image
        project.territory_data = metadata
        project.territory_pmap = combined_pmap
        project.cached_masks = masks
        project.modified = True
        task_ctx.refresh_tab_view(TabName.TERRITORY)

    return territory_image, metadata
