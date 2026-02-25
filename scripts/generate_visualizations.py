"""
Generate visualization overlays for areas, dens_samps, territories, and provinces.

This script:
1. Loads existing map image/data pairs from examples/output
2. Falls back to generating maps with ProcessMapTool when none are available
3. Writes center, bbox, and density overlays for each available map level
"""

from __future__ import annotations
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

from opengs_maptool import ProcessMapTool, MapToolResult, RegionMetadata, export_to_csv, export_to_json, import_from_json


LEVEL_ORDER = ["areas", "dens_samps", "territories", "provinces"]

LEVEL_STYLE = {
    "areas": {"radius": 8, "color": "lime"},
    "dens_samps": {"radius": 7, "color": "cyan"},
    "territories": {"radius": 6, "color": "blue"},
    "provinces": {"radius": 4, "color": "yellow"},
}

LEVEL_FILES = {
    "areas": {
        "data": "cont_area_data.json",
        "image": "cont_area_image.png",
    },
    "dens_samps": {
        "data": "dens_samp_data.json",
        "image": "dens_samp_image.png",
    },
    "territories": {
        "data": "territory_data.json",
        "image": "territory_image.png",
    },
    "provinces": {
        "data": "province_data.json",
        "image": "province_image.png",
    },
}

EXAMPLES_DIR = Path(__file__).parent.parent / "opengs_maptool" / "examples"


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    if len(color) != 6:
        raise ValueError(f"Invalid color: {color}")
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))


def darken_color(rgb: tuple[int, int, int], factor: float = 0.6) -> tuple[int, int, int]:
    return tuple(max(0, int(c * factor)) for c in rgb)


def density_to_rgb(normalized_density: np.ndarray) -> np.ndarray:
    stops = np.array([0.0, 0.33, 0.66, 1.0], dtype=np.float32)
    ramp = np.array(
        [
            [20, 32, 120],
            [38, 196, 236],
            [250, 224, 77],
            [210, 35, 35],
        ],
        dtype=np.float32,
    )

    r = np.interp(normalized_density, stops, ramp[:, 0])
    g = np.interp(normalized_density, stops, ramp[:, 1])
    b = np.interp(normalized_density, stops, ramp[:, 2])
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


def resolve_existing_path(base_dir: Path, candidate: str) -> Path | None:
    path = base_dir / candidate
    if path.exists():
        return path
    return None


def save_generated_inputs(input_dir: Path, result: MapToolResult) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)

    result.cont_area_image.save(input_dir / LEVEL_FILES["areas"]["image"])
    result.dens_samp_image.save(input_dir / LEVEL_FILES["dens_samps"]["image"])
    result.territory_image.save(input_dir / LEVEL_FILES["territories"]["image"])
    result.province_image.save(input_dir / LEVEL_FILES["provinces"]["image"])

    export_to_json(result.cont_area_data, input_dir / LEVEL_FILES["areas"]["data"])
    export_to_json(result.dens_samp_data, input_dir / LEVEL_FILES["dens_samps"]["data"])
    export_to_json(result.territory_data, input_dir / LEVEL_FILES["territories"]["data"])
    export_to_json(result.province_data, input_dir / LEVEL_FILES["provinces"]["data"])

    export_to_csv(result.cont_area_data, input_dir / LEVEL_FILES["areas"]["data"].replace(".json", ".csv"))
    export_to_csv(result.dens_samp_data, input_dir / LEVEL_FILES["dens_samps"]["data"].replace(".json", ".csv"))
    export_to_csv(result.territory_data, input_dir / LEVEL_FILES["territories"]["data"].replace(".json", ".csv"))
    export_to_csv(result.province_data, input_dir / LEVEL_FILES["provinces"]["data"].replace(".json", ".csv"))


def generate_maps(input_dir: Path) -> None:
    example_input_dir = EXAMPLES_DIR / "input"
    boundary_image_path = example_input_dir / "bound2_orig.png"
    class_image_path = example_input_dir / "class2_clean.png"

    if not example_input_dir.exists():
        raise FileNotFoundError(f"Example input directory not found: {example_input_dir}")
    if not boundary_image_path.exists() or not class_image_path.exists():
        raise FileNotFoundError(f"Required input files not found in {example_input_dir}")

    print("Generating maps with MapTool...")
    maptool = ProcessMapTool(
        class_image=Image.open(class_image_path),
        boundary_image=Image.open(boundary_image_path),
    )
    result = maptool.generate()
    save_generated_inputs(input_dir, result)


def load_available_levels(input_dir: Path) -> dict[str, tuple[list[RegionMetadata], Image.Image]]:
    loaded = {}

    for level in LEVEL_ORDER:
        level_paths = LEVEL_FILES[level]
        data_path = resolve_existing_path(input_dir, level_paths["data"])
        image_path = resolve_existing_path(input_dir, level_paths["image"])

        if data_path is None or image_path is None:
            continue

        data = import_from_json(data_path)
        if not isinstance(data, list):
            continue

        image = Image.open(image_path).convert("RGBA")
        loaded[level] = (data, image)

    return loaded


def draw_centers(
    image: Image.Image,
    data: list[RegionMetadata],
    circle_radius: int,
    outline_color: str,
) -> Image.Image:
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)

    for region in data:
        if region.global_center is not None:
            x, y = region.global_center
        else:
            continue

        r = circle_radius
        draw.ellipse([x - r, y - r, x + r, y + r], outline=outline_color, width=2)

    return img_copy


def draw_bboxes(image: Image.Image, data: list[RegionMetadata], width: int = 2, darken_factor: float = 0.6) -> Image.Image:
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)

    for region in data:
        bbox = region.global_bbox
        if not bbox or len(bbox) != 4:
            continue

        try:
            outline_color = darken_color(hex_to_rgb(str(region.color)), darken_factor)
        except (ValueError, AttributeError):
            outline_color = (128, 128, 128)

        x0, y0, x1, y1 = bbox
        border_width = 1
        # Only draw if box is valid
        if x1 >= x0 and y1 >= y0:
            draw.rectangle([x0, y0, x1, y1], outline=outline_color, width=border_width)

    return img_copy


def make_density_heatmap_from_image(regions: list[RegionMetadata], source_image: Image.Image) -> Image.Image:
    source = np.array(source_image.convert("RGB"))

    density_by_color: dict[tuple[int, int, int], float] = {}
    densities: list[float] = []

    for region in regions:
        color = region.color
        density = region.density_multiplier
        if color is None or density is None:
            continue

        rgb = hex_to_rgb(str(color))
        density_value = float(density)
        density_by_color[rgb] = density_value
        densities.append(density_value)

    if not densities:
        raise ValueError("No density values found")

    min_density = min(densities)
    max_density = max(densities)
    density_range = max(max_density - min_density, 1e-9)

    packed = (
        (source[:, :, 0].astype(np.uint32) << 16)
        | (source[:, :, 1].astype(np.uint32) << 8)
        | source[:, :, 2].astype(np.uint32)
    )
    flat = packed.reshape(-1)
    unique_colors, inverse_indices = np.unique(flat, return_inverse=True)

    density_lookup: dict[int, float] = {
        (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]: density
        for rgb, density in density_by_color.items()
    }

    unique_densities = np.full(unique_colors.shape[0], np.nan, dtype=np.float32)
    for index, color_key in enumerate(unique_colors):
        density_value = density_lookup.get(int(color_key))
        if density_value is not None:
            unique_densities[index] = density_value

    density_map = unique_densities[inverse_indices].reshape(source.shape[0], source.shape[1])
    valid_mask = ~np.isnan(density_map)

    normalized = np.zeros_like(density_map, dtype=np.float32)
    normalized[valid_mask] = (density_map[valid_mask] - min_density) / density_range

    rgb_heat = np.zeros((source.shape[0], source.shape[1], 3), dtype=np.uint8)
    rgb_heat[valid_mask] = density_to_rgb(normalized[valid_mask])

    alpha = np.zeros((source.shape[0], source.shape[1]), dtype=np.uint8)
    alpha[valid_mask] = 255

    rgba = np.dstack([rgb_heat, alpha])
    return Image.fromarray(rgba, mode="RGBA")


def main() -> None:
    input_dir = EXAMPLES_DIR / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir = EXAMPLES_DIR / "visualization"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading available images/data...")
    loaded = load_available_levels(input_dir)

    if not loaded:
        print("No complete image/data pairs found; generating example outputs first...")
        generate_maps(input_dir)
        loaded = load_available_levels(input_dir)

    if not loaded:
        raise RuntimeError("No visualizable outputs found after generation.")

    print("Creating per-level visualizations...")
    for level in LEVEL_ORDER:
        if level not in loaded:
            continue

        region_data, region_image = loaded[level]
        style = LEVEL_STYLE[level]

        centers = draw_centers(
            region_image,
            region_data,
            circle_radius=style["radius"],
            outline_color=style["color"],
        )
        centers_path = output_dir / f"centers_{level}.png"
        centers.save(centers_path)

        bboxes = draw_bboxes(region_image, region_data, width=2)
        bboxes_path = output_dir / f"bboxes_{level}.png"
        bboxes.save(bboxes_path)

        print(f"  Saved: {centers_path.name} ({len(region_data)} centers)")
        print(f"  Saved: {bboxes_path.name} ({len(region_data)} bboxes)")

        try:
            density = make_density_heatmap_from_image(region_data, region_image)
            density_path = output_dir / f"density_{level}.png"
            density.save(density_path)
            print(f"  Saved: {density_path.name}")
        except ValueError:
            pass

    available_levels = [lvl for lvl in LEVEL_ORDER if lvl in loaded]
    if not available_levels:
        return

    base_level = "provinces" if "provinces" in loaded else available_levels[-1]
    base_image = loaded[base_level][1].copy()

    combined_centers = base_image.copy()
    for level in available_levels:
        style = LEVEL_STYLE[level]
        combined_centers = draw_centers(
            combined_centers,
            loaded[level][0],
            circle_radius=max(3, style["radius"] - 1),
            outline_color=style["color"],
        )
    combined_centers.save(output_dir / "centers_all.png")
    print("  Saved: centers_all.png")


if __name__ == "__main__":
    main()
