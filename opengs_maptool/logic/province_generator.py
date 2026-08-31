from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from opengs_maptool.context import LimitedTaskContext

import opengs_maptool.config as config
import numpy as np
from numpy.typing import NDArray
from typing import Any
from PIL import Image
from scipy.ndimage import label as ndlabel
from opengs_maptool.controllers.progress_controller import ProgressController
from opengs_maptool.logic.numb_gen import NumberSeries
from opengs_maptool.logic.utils import (
    clear_used_colors, color_from_id, create_region_map,
)
import opengs_maptool.logic.datastructure as ds
from opengs_maptool.simple_types import TabName


def generate_province_map(
        task_ctx: LimitedTaskContext, progress_controller: ProgressController
    ) -> tuple[ds.ProvinceImage, list[ds.RegionMetadata]] | tuple[None, None]:
    # Safety check matching the button setEnabled condition
    if not task_ctx.project.can_province_image_be_generated():
        return None, None

    # Define phases weighted according to expected workload relative distribution
    phase1 = progress_controller.add_phase(step_weight= 20, msg="Setup data & masks")
    phase2 = progress_controller.add_phase(step_weight= 10, msg="Distribution calculation")
    phase3 = progress_controller.add_phase(step_weight= 50, msg="Lake processing")
    phase4 = progress_controller.add_phase(step_weight=820, msg="Province generation")
    phase5 = progress_controller.add_phase(step_weight= 80, msg="Image building & terrain assignment")
    phase6 = progress_controller.add_phase(step_weight= 20, msg="Finalizing")

    with progress_controller.execute_phase(phase1):
        project = task_ctx.project
        clear_used_colors()

        # See can check above for type hints
        territory_pmap: ds.RegionPixelMap = project.territory_pmap
        territory_data: list[ds.RegionMetadata] = project.territory_data
        masks: ds.Masks = project.cached_masks
        density_arr: NDArray[Any] = np.array(project.density_image)
        
        density_strength = project.province_density_strength / 10.0
        exclude_ocean_density = project.province_exclude_ocean
        jagged_land_strength = project.province_jagged_land_amplitude / 100.0
        jagged_ocean_strength = project.province_jagged_ocean_amplitude / 100.0
        map_h, map_w = masks.map_h, masks.map_w

        total_land_provs = project.land_province_density
        total_ocean_provs = project.oceanic_province_density
        lake_mask = masks.lake_mask

        # Reset province_ids from any previous generation
        for d in territory_data:
            d.province_ids = []

        # Separate territories by type
        land_terrs = [d for d in territory_data if d.territory_type == ds.RegionType.LAND]
        ocean_terrs = [d for d in territory_data if d.territory_type == ds.RegionType.OCEAN]

        # Build set of ocean territory indices for density exclusion
        ocean_terr_indices = set()
        if exclude_ocean_density:
            for d in ocean_terrs:
                ocean_terr_indices.add(d._pmap_index)

        series = NumberSeries(
            config.PROVINCE_ID_PREFIX,
            config.PROVINCE_ID_START,
            config.PROVINCE_ID_END
        )

        province_pmap = np.full((map_h, map_w), -1, np.int32)
        all_metadata: list[ds.RegionMetadata] = []
        start_index = 0
        boundary_mask = masks.boundary_mask
        if boundary_mask is None:
            boundary_mask = np.zeros((map_h, map_w), dtype=bool)

        # Build territory lookup by _pmap_index
        terr_by_index = {d._pmap_index: d for d in territory_data}

    with progress_controller.execute_phase(phase2) as sub_progress2:
        count_phase = sub_progress2.add_phase(step_weight=100)
        compute_phase = sub_progress2.add_phase(step_weight=100)
        land_phase = sub_progress2.add_phase(step_weight=100)
        ocean_phase = sub_progress2.add_phase(step_weight=100)
        gather_phase = sub_progress2.add_phase(step_weight=100)

        with sub_progress2.execute_phase(count_phase):
            # Count pixels per territory for proportional distribution
            unique, counts = np.unique(
                territory_pmap[territory_pmap >= 0], return_counts=True
            )
            pixel_counts: ds.RegionIdToPixelCounts = dict(zip(unique.tolist(), counts.tolist()))

        with sub_progress2.execute_phase(compute_phase) as compute_progress:
            # Compute average density weight per territory (darker = higher weight)
            density_weights = dict[int, float]()
            for idx in compute_progress.track_iteration(unique):
                if int(idx) in ocean_terr_indices:
                    density_weights[int(idx)] = 1.0
                else:
                    terr_mask = territory_pmap == idx
                    mean_val = density_arr[terr_mask].mean()
                    density_weights[int(idx)] = (256.0 - mean_val) ** density_strength

        with sub_progress2.execute_phase(land_phase) as land_progress:
            land_alloc = _distribute(
                land_terrs, total_land_provs, pixel_counts, land_progress, density_weights
            )

        with sub_progress2.execute_phase(ocean_phase) as ocean_progress:
            ocean_alloc = _distribute(
                ocean_terrs, total_ocean_provs, pixel_counts, ocean_progress, density_weights
            )

        with sub_progress2.execute_phase(gather_phase):
            all_terrs = ([(d, land_alloc[i]) for i, d in enumerate(land_terrs)] +
                         [(d, ocean_alloc[i]) for i, d in enumerate(ocean_terrs)])

    with progress_controller.execute_phase(phase3) as sub_progress3:
        # Create lake provinces globally — each connected lake is one province,
        # assigned to the territory that contains its center
        if lake_mask is not None and lake_mask.any():
            labeled, num_lakes = ndlabel(lake_mask)
            for comp_id in sub_progress3.track_iteration(range(1, num_lakes + 1)):
                comp_mask = labeled == comp_id
                rid = series.get_id()
                if rid is None:
                    continue
                r, g, b = color_from_id(start_index, ds.RegionType.LAKE)
                ys, xs = np.where(comp_mask)
                cx, cy = int(round(xs.mean())), int(round(ys.mean()))
                terr_idx = int(territory_pmap[cy, cx])
                terr = terr_by_index.get(terr_idx)
                tid = terr.territory_id if terr else ""
                lake_entry = ds.RegionMetadata(
                    # For both territories & provinces
                    region_level=ds.RegionLevel.PROVINCE,
                    R=r, G=g, B=b,
                    x=xs.mean(),
                    y=ys.mean(),
                    _pmap_index=start_index,
                    territory_id=tid,
                    
                    # Only for provinces
                    province_id=rid,
                    province_type=ds.RegionType.LAKE,
                    province_terrain=None,

                    # Only for territories
                    territory_type=None,
                    province_ids=None,
                )
                province_pmap[comp_mask] = start_index
                all_metadata.append(lake_entry)
                if terr is not None:
                    terr.province_ids = terr.province_ids or []
                    terr.province_ids.append(rid)
                start_index += 1

    with progress_controller.execute_phase(phase4) as sub_progress4:
        # Loop through all territories using iteration tracking
        for terr, prov_count in sub_progress4.track_iteration(all_terrs):
            terr_mask = territory_pmap == terr._pmap_index
            region_type = terr.territory_type
            tid = terr.territory_id

            # Subdivide non-lake pixels in this territory
            if lake_mask is not None:
                terr_fill = terr_mask & ~lake_mask & ~boundary_mask
                terr_border = (terr_mask & boundary_mask) | (terr_mask & lake_mask)
            else:
                terr_fill = terr_mask & ~boundary_mask
                terr_border = terr_mask & boundary_mask

            if exclude_ocean_density and region_type == ds.RegionType.OCEAN:
                terr_density = None
                terr_density_strength = 1.0
            else:
                terr_density = density_arr
                terr_density_strength = density_strength

            amplitude_factor = jagged_land_strength if region_type == ds.RegionType.LAND else jagged_ocean_strength

            # Pass None for inner progress controller to create_region_map here
            # to keep granular updates balanced across territory iterations
            pmap, metadata, next_index = create_region_map(
                terr_fill, terr_border, prov_count, start_index,
                series, region_type, ds.RegionLevel.PROVINCE,
                ProgressController(), # ignore sub progress as we already track loop progress
                density=terr_density, density_strength=terr_density_strength, 
                amplitude_factor=amplitude_factor
            )

            # Tag each province with its parent territory
            for m in metadata:
                m.territory_id = tid

            # Merge into global province pmap (don't overwrite lake provinces)
            valid = (pmap >= 0) & (province_pmap < 0)
            province_pmap[valid] = pmap[valid]

            # Collect province_ids for territory (append to any existing lake ids)
            existing = terr.province_ids or []
            terr.province_ids = existing + [m.province_id for m in metadata]

            all_metadata.extend(metadata)
            start_index = next_index

    with progress_controller.execute_phase(phase5) as sub_progress5:
        render_phase = sub_progress5.add_phase(step_weight=50)
        terrain_phase = sub_progress5.add_phase(step_weight=50)

        # Step 1: Render province output map
        with sub_progress5.execute_phase(render_phase):
            out = np.zeros((map_h, map_w, 3), np.uint8)
            if all_metadata and start_index > 0:
                color_lut = np.zeros((start_index, 3), np.uint8)
                for d in all_metadata:
                    idx = d._pmap_index
                    color_lut[idx] = (d.R, d.G, d.B)
                valid = province_pmap >= 0
                out[valid] = color_lut[province_pmap[valid]]
            province_image = Image.fromarray(out)

        # Step 2: Assign terrain
        with sub_progress5.execute_phase(terrain_phase) as terrain_progress:
            terrain_image = project.terrain_image
            if terrain_image is not None:
                terrain_arr = np.array(terrain_image)
                _assign_terrain(all_metadata, terrain_arr, terrain_progress)
            else:
                for prov in terrain_progress.track_iteration(all_metadata):
                    region_type = prov.province_type
                    if region_type == ds.RegionType.LAKE:
                        prov.province_terrain = config.DEFAULT_TERRAIN_LAKE
                    elif region_type == ds.RegionType.OCEAN:
                        prov.province_terrain = config.DEFAULT_TERRAIN_OCEAN
                    else:
                        prov.province_terrain = config.DEFAULT_TERRAIN_LAND

    with progress_controller.execute_phase(phase6):
        project.province_image = province_image
        project.province_data = all_metadata
        project.modified = True
        task_ctx.refresh_tab_view(TabName.PROVINCE)

    return province_image, all_metadata


def _distribute(
        territories: list[ds.RegionMetadata], total_provinces: int, pixel_counts: ds.RegionIdToPixelCounts,
        progress_controller: ProgressController, density_weights: dict[int, float] | None = None,
    ) -> list[int]:
    """Distribute total_provinces proportionally across territories.

    When density_weights is provided, each territory's pixel count is scaled
    by its density weight so darker regions receive more provinces.
    Each territory gets at least 1 province.
    """
    n = len(territories)
    if n == 0 or total_provinces <= 0:
        return [0] * n

    terr_pixels = [pixel_counts.get(d._pmap_index, 0) for d in territories]

    if density_weights is not None:
        terr_pixels = [
            px * density_weights.get(d._pmap_index, 1.0)
            for px, d in zip(terr_pixels, territories)
        ]

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


def _assign_terrain(metadata: list[ds.RegionMetadata], terrain_arr: NDArray[Any], progress_controller: ProgressController) -> None:
    """Look up terrain color at each province center and assign province_terrain.

    Enforces category constraints: land provinces only get land terrains,
    ocean provinces only get naval terrains, lake provinces get lake terrain.
    Falls back to the configured default for each province type.
    """
    lookup_phase = progress_controller.add_phase(step_weight=10)
    province_phase = progress_controller.add_phase(step_weight=max(len(metadata), 1))

    with progress_controller.execute_phase(lookup_phase):
        h, w = terrain_arr.shape[:2]

        # Build per-category lookups: (R, G, B) -> terrain name
        land_lookup = {color: name for name, color in config.LAND_TERRAIN_TYPES.items()}
        naval_lookup = {color: name for name, color in config.NAVAL_TERRAIN_TYPES.items()}
        lake_lookup = {color: name for name, color in config.LAKE_TERRAIN_TYPES.items()}

    with progress_controller.execute_phase(province_phase) as province_progress:
        for prov in province_progress.track_iteration(metadata):
            px = int(round(prov.x))
            py = int(round(prov.y))
            px = max(0, min(px, w - 1))
            py = max(0, min(py, h - 1))
            pixel = (int(terrain_arr[py, px, 0]),
                     int(terrain_arr[py, px, 1]),
                     int(terrain_arr[py, px, 2]))

            region_type = prov.province_type
            if region_type == ds.RegionType.LAKE:
                prov.province_terrain = lake_lookup.get(pixel, config.DEFAULT_TERRAIN_LAKE)
            elif region_type == ds.RegionType.OCEAN:
                prov.province_terrain = naval_lookup.get(pixel, config.DEFAULT_TERRAIN_OCEAN)
            else:
                prov.province_terrain = land_lookup.get(pixel, config.DEFAULT_TERRAIN_LAND)
