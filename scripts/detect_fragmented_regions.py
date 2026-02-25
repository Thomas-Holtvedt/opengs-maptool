"""
Detect fragmented regions from a region image + metadata.

Output image convention:
- Non-fragmented pixels are rendered in grayscale.
- Fragment pixels are rendered in colorful highlight colors.

The script uses the metadata `seed` field to decide which connected component
is the primary component of a region. Any other component of the same region
is treated as a fragment.
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any
import numpy as np
from PIL import Image
from scipy import ndimage

from opengs_maptool import RegionMetadata, import_from_json


STRICT_FOUR_CONNECTED = np.array(
    [
        [0, 1, 0],
        [1, 1, 1],
        [0, 1, 0],
    ],
    dtype=np.uint8,
)


REGION_FILE_SPECS = {
    "areas": {
        "image": "cont_area_image.png",
        "metadata": "cont_area_data.json",
        "output": "fragments_cont_areas.png",
    },
    "dens_samps": {
        "image": "dens_samp_image.png",
        "metadata": "dens_samp_data.json",
        "output": "fragments_dens_samp.png",
    },
    "territories": {
        "image": "territory_image.png",
        "metadata": "territory_data.json",
        "output": "fragments_territory.png",
    },
    "provinces": {
        "image": "province_image.png",
        "metadata": "province_data.json",
        "output": "fragments_province.png",
    },
}

EXAMPLES_DIR = Path(__file__).parent.parent / "opengs_maptool" / "examples"


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    if len(color) != 6:
        raise ValueError(f"Invalid hex color: {color}")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def to_grayscale_value(rgb: tuple[int, int, int]) -> int:
    r, g, b = rgb
    return int(round(0.299 * r + 0.587 * g + 0.114 * b))


def highlight_color(region_index: int, fragment_index: int) -> tuple[int, int, int]:
    key = (region_index + 1) * 92821 + (fragment_index + 1) * 68917
    r = (key * 73 + 17) % 256
    g = (key * 151 + 59) % 256
    b = (key * 199 + 101) % 256
    return int(r), int(g), int(b)


def resolve_seed(region: RegionMetadata, width: int, height: int) -> tuple[int, int] | None:
    seed = region.global_seed
    if isinstance(seed, (list, tuple)) and len(seed) == 2:
        sx = int(round(float(seed[0])))
        sy = int(round(float(seed[1])))
    elif region.global_center is not None:
        sx = int(round(float(region.global_center[0])))
        sy = int(round(float(region.global_center[1])))
    elif region.local_center is not None:
        sx = int(round(float(region.local_center[0])))
        sy = int(round(float(region.local_center[1])))
    else:
        return None

    sx = max(0, min(width - 1, sx))
    sy = max(0, min(height - 1, sy))
    return sx, sy


def choose_seed_component(
    labels: np.ndarray,
    region_mask: np.ndarray,
    seed_xy: tuple[int, int],
) -> int:
    sx, sy = seed_xy
    h, w = labels.shape
    sx = max(0, min(w - 1, int(sx)))
    sy = max(0, min(h - 1, int(sy)))
    comp = int(labels[sy, sx])
    if comp > 0:
        return comp

    ys, xs = np.where(region_mask)
    if len(xs) == 0:
        return 0

    dx = xs.astype(np.float64) - float(sx)
    dy = ys.astype(np.float64) - float(sy)
    nearest_idx = int(np.argmin(dx * dx + dy * dy))
    return int(labels[int(ys[nearest_idx]), int(xs[nearest_idx])])


def resolve_bbox(region: RegionMetadata, width: int, height: int) -> tuple[int, int, int, int]:
    bbox = region.global_bbox
    if bbox is None:
        raise Exception(f"Expected global bounding box for Region {region.region_id}")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return 0, 0, width, height

    x0 = int(bbox[0])
    y0 = int(bbox[1])
    x1 = int(bbox[2]) + 1
    y1 = int(bbox[3]) + 1

    x0 = max(0, min(width, x0))
    y0 = max(0, min(height, y0))
    x1 = max(x0, min(width, x1))
    y1 = max(y0, min(height, y1))
    return x0, y0, x1, y1


def detect_fragmented_regions(
    image_rgba: np.ndarray,
    metadata: list[RegionMetadata],
) -> tuple[np.ndarray, dict[str, int], list[dict[str, Any]]]:
    height, width = image_rgba.shape[:2]
    rgb_image = image_rgba[:, :, :3]

    output = np.zeros((height, width, 4), dtype=np.uint8)
    output[:, :, 3] = 255

    stats = {
        "regions_checked": 0,
        "regions_fragmented": 0,
        "fragment_components": 0,
        "fragment_pixels": 0,
        "regions_missing_seed": 0,
    }
    fragment_details: list[dict[str, Any]] = []

    for region_index, region in enumerate(metadata):
        color_hex = region.color
        if not isinstance(color_hex, str):
            continue

        try:
            region_rgb = hex_to_rgb(color_hex)
        except ValueError:
            continue

        x0, y0, x1, y1 = resolve_bbox(region, width, height)
        if x1 <= x0 or y1 <= y0:
            continue

        rgb_window = rgb_image[y0:y1, x0:x1]
        region_mask = np.all(rgb_window == np.array(region_rgb, dtype=np.uint8), axis=2)
        if not np.any(region_mask):
            continue

        stats["regions_checked"] += 1

        labels, num_components = ndimage.label(region_mask, structure=STRICT_FOUR_CONNECTED)

        gray = to_grayscale_value(region_rgb)
        window_out = output[y0:y1, x0:x1]
        window_out[region_mask] = [gray, gray, gray, 255]

        if num_components <= 1:
            continue

        seed_xy = resolve_seed(region, width, height)
        if seed_xy is None:
            stats["regions_missing_seed"] += 1
            component_sizes = np.bincount(labels[region_mask])
            if component_sizes.size <= 1:
                continue
            component_sizes[0] = 0
            primary_component = int(np.argmax(component_sizes))
        else:
            sx, sy = seed_xy
            local_seed = (sx - x0, sy - y0)
            primary_component = choose_seed_component(labels, region_mask, local_seed)
            if primary_component <= 0:
                component_sizes = np.bincount(labels[region_mask])
                if component_sizes.size <= 1:
                    continue
                component_sizes[0] = 0
                primary_component = int(np.argmax(component_sizes))

        has_fragments = False
        for component_id in range(1, num_components + 1):
            if component_id == primary_component:
                continue

            fragment_mask = labels == component_id
            if not np.any(fragment_mask):
                continue

            has_fragments = True
            stats["fragment_components"] += 1
            stats["fragment_pixels"] += int(np.count_nonzero(fragment_mask))

            r, g, b = highlight_color(region_index, component_id)
            window_out[fragment_mask] = [r, g, b, 255]
            fragment_details.append(
                {
                    "region_id": region.region_id,
                    "component_id": int(component_id),
                    "pixel_count": int(np.count_nonzero(fragment_mask)),
                    "fragment_color": rgb_to_hex((r, g, b)),
                    "source_region_color": color_hex,
                }
            )

        if has_fragments:
            stats["regions_fragmented"] += 1

    return output, stats, fragment_details


def process_region_type(region_type: str, input_dir: Path, visualization_dir: Path) -> bool:
    spec = REGION_FILE_SPECS[region_type]
    image_path = input_dir / spec["image"]
    metadata_path = input_dir / spec["metadata"]
    output_path = visualization_dir / spec["output"]

    if not image_path.exists() or not metadata_path.exists():
        print(f"Skipping {region_type}: missing {image_path.name} or {metadata_path.name}")
        return False

    image_rgba = np.array(Image.open(image_path).convert("RGBA"), dtype=np.uint8)
    metadata = import_from_json(metadata_path)

    if not isinstance(metadata, list):
        raise ValueError(f"Metadata JSON for {region_type} must be a list of regions")

    visualization, stats, fragment_details = detect_fragmented_regions(image_rgba, metadata)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(visualization).save(output_path)

    print(f"Saved [{region_type}]: {output_path}")
    print(
        f"stats [{region_type}]:",
        json.dumps(stats, indent=2),
    )
    print(
        f"fragment_colors [{region_type}]:",
        json.dumps(fragment_details, indent=2),
    )
    return True


def main() -> None:
    input_dir = EXAMPLES_DIR / "output"
    visualization_dir = EXAMPLES_DIR / "visualization"
    visualization_dir.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description="Detect fragmented regions from map image and metadata")
    parser.add_argument(
        "--region-type",
        choices=["all", *REGION_FILE_SPECS.keys()],
        default="all",
        help="Region type to process. Default: all available region types",
    )
    args = parser.parse_args()

    requested_types = (
        list(REGION_FILE_SPECS.keys())
        if args.region_type == "all"
        else [args.region_type]
    )

    processed_count = 0
    for region_type in requested_types:
        if process_region_type(region_type, input_dir, visualization_dir):
            processed_count += 1

    if processed_count == 0:
        print("No region types processed. Generate outputs first, then rerun this script.")


if __name__ == "__main__":
    main()
