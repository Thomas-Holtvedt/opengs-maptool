<img width="350" height="350" alt="ogs-mt-logo" src="https://github.com/user-attachments/assets/d03854c8-c2e1-468f-9f8a-269f498d169c" />

# Open Grand Strategy - Map Tool 
The OpenGS Map Tool is a specialized utility designed to streamline the creation of map data for use in grand strategy games. 
Province and territory maps form the backbone of these games, defining the geographical regions that players interact with.

## Features
- Generate and Export province maps
- Generate and Export province data
- Generate and Export territory maps
- Generate and Export territory data

## Showcase
<img width="2200" height="2318" alt="image" src="https://github.com/user-attachments/assets/1ad0250a-0a50-4bbd-b616-0e215a7ed2bc" />
<img width="2200" height="2308" alt="image" src="https://github.com/user-attachments/assets/7afe9e4c-648d-4e63-9636-a8df47bfba27" />

## How to install
### Option 1 (Windows only):
1. "Releases" section in Github
2. Download and unpack "ogs_maptool.zip"
3. Run the Executable

### Option 2:
1. Clone the repository
2. Download the necessary libraries by running "pip install -r requirements.txt" in your terminal, 
inside the project directory
3. Start project by running "python main.py"

## How to use the tool

### GUI Usage

The graphical interface provides an interactive, step-by-step workflow:

#### 1. **Getting Started**
   - Read the README and familiarize yourself with the workflow

#### 2. **Adapt Boundary Image** (Optional)
   - Import your boundary image (black lines on transparent background, RGB 0,0,0)
   - Click "Normalize Territory and Province Density" to prepare it for density editing
   - Use the blue channel to control region density:
     - **B=255 (white)** → 4x more regions
     - **B=128 (light yellow)** → normal density
     - **B=0 (dark yellow)** → 4x fewer regions
     - anything inbetween for nuanced control
   - Keep or modify the generated boundary image

#### 3. **Input Images**
   - Import your final boundary image
   - Import and clean your land/ocean image
     - Ocean must be RGB `(5, 20, 18)`
     - Everything else is considered land
   - Both images must have the same dimensions

#### 4. **Generate Continuous Areas**
   - Generates intermediate region divisions from your boundary image
   - Adjust the RNG seed to try different layouts
   - The same seed and input images will always generate the same output

#### 5. **Generate Territories**
   - Creates larger regional divisions
   - Adjust sliders for land and water territory sizes
   - Change RNG seed for different randomization
   - Export territory map and data (JSON/CSV) when satisfied

#### 6. **Generate Provinces**
   - Creates smaller subdivisions from territories
   - Adjust sliders for land and water province sizes
   - Change RNG seed for different randomization
   - Export province map and data (JSON/CSV) when satisfied

**Tips:**
- Territories must be generated before provinces
- Use the "Normalize Density" feature for better control over region distribution
- Try different RNG seeds to explore different layouts
- All exports (maps and data files) are available after each generation step

---

### Python/Terminal Usage

For programmatic map generation, use the `MapTool` class directly:

```python
from pathlib import Path
from PIL import Image
from logic.maptool import MapTool
import json

# Define input/output directories
input_dir = Path("examples/input")
output_dir = Path("examples/output")

# Create MapTool instance
maptool = MapTool(
    land_image=Image.open(input_dir / "land2.png"),
    boundary_image=Image.open(input_dir / "bound2_density.png"),
    pixels_per_land_territory=6000,      # Adjust territory size
    pixels_per_water_territory=35000,
    pixels_per_land_province=1200,       # Adjust province size
    pixels_per_water_province=7000,
    lloyd_iterations=2,                  # Quality of Voronoi relaxation
    cont_areas_rng_seed=int(1e6),
    territories_rng_seed=int(2e6),
    provinces_rng_seed=int(3e6),
)

# Generate all maps
result = maptool.generate()

# Save result images
result.cont_areas_image.save(output_dir / "cont_areas_image.png")
result.territory_image.save(output_dir / "territory_image.png")
result.province_image.save(output_dir / "province_image.png")
result.class_image.save(output_dir / "class_image.png")

# Save result data
output_data = {
    "cont_areas": result.cont_areas_data,
    "territories": result.territory_data,
    "provinces": result.province_data,
    "class_counts": result.class_counts,
}
(output_dir / "map_data.json").write_text(json.dumps(output_data, indent=2))
```

**Key Parameters:**
- `pixels_per_land_territory` / `pixels_per_water_territory`: Controls territory size (higher = fewer, larger territories)
- `pixels_per_land_province` / `pixels_per_water_province`: Controls province size
- `lloyd_iterations`: Number of Lloyd relaxation iterations (1-10, higher = better spacing but slower)
- `*_rng_seed`: Random seeds for reproducible results (change to explore different layouts)

---

## MapToolResult - Understanding the Output

The `generate()` method returns a `MapToolResult` object containing both images and metadata:

```python
result = maptool.generate()
```

### Result Images
- `result.cont_areas_image` - Colored continuous areas (if boundary provided)
- `result.territory_image` - Colored territory map
- `result.province_image` - Colored province map
- `result.class_image` - Cleaned land/ocean/lake classification

### Result Data

Each data field (`cont_areas_data`, `territory_data`, `province_data`) is a list of dictionaries representing regions. Each region dict contains:

| Field | Type | Description |
|-------|------|-------------|
| `region_id` | str \| int | Unique identifier (e.g., "area-001", "ter-001", "prv-042") |
| `region_type` | str | Type of region: "land", "ocean", or "lake" (determined by predominant pixel type) |
| `color` | str | Hex color code (e.g., "#a1b2c3") used in the map image |
| `parent_id` | str \| int \| None | ID of parent region (territory for provinces, area for territories, None for areas) |
| `density_multiplier` | float | Density factor applied (from boundary blue channel, only set for areas and inherited by territories) |
| `local_x`, `local_y` | float | Centroid coordinates: for territories/provinces = within parent(see `parent_id`) area; for areas = global |
| `global_x`, `global_y` | float | Centroid coordinates in the full map |
| `bbox_local` | list[int] | Bounding box: for territories/provinces = within parent area; for areas = global |
| `bbox` | list[int] | Bounding box in global coordinates |

**Example region:**
```python
{
   "region_type": "land",
   "region_id": "ter-000235",
   "parent_id": 113,
   "color": "#b12a8c",
   "local_x": 150.75,
   "local_y": 96.39,
   "global_x": 2892.75,
   "global_y": 470.39,
   "bbox_local": [119, 66, 193, 129],
   "bbox": [2861, 440, 2935, 503],
   "density_multiplier": 2.23
}
```

### Class Data

`result.class_counts` is a dictionary showing pixel distribution:
```python
{
    "land": 450000,    # Pixels classified as land
    "ocean": 300000,   # Pixels classified as ocean
    "lake": 50000      # Pixels classified as lake
}
```

### Using the Data in GUI

When you export CSV/JSON from the GUI or via Python, this field data is included, allowing you to:
- Map region IDs to visual colors
- Calculate region areas (from bounding boxes)
- Track parent-child relationships (territory → provinces)
- Access precise centroid coordinates for game logic

---

## Image Specifications Reference

### Boundary Image
The boundary image defines regions that provinces/territories must respect.
Boundaries must be **pure black, RGB (0,0,0)**, everything else is ignored.
<br>**Examples:**
![](examples/input/bound.png)
![](examples/input/bound2_orig.png)

**Density Multiplier:**
Use the blue channel to control region density in different areas:
![](examples/input/bound2_yellow.png)
<br>After editing with density multipliers:
![](examples/input/bound2_density.png)

**Best Practices:**
1. Divide large oceans and countries for better results
2. Use density control to create varied region sizes (e.g., small provinces in densely populated areas, large ones in sparse regions)

### Land Image
Specifies ocean vs. land areas. Ocean pixels should be **RGB `(5, 20, 18)`** (dark teal).
Everything else is considered land.
<br>**Examples:**
![](examples/input/land.png)
![](examples/input/land2.png)

**Note:** You need at least one input image (boundary or land). Both are optional but must have the same dimensions if used together.

## Contributions
Contributions can come in many forms and all are appreciated:
- Feedback
- Code improvements
- Added functionality

## Discord 
Follow and/or support the project on [OpenGS Discord Server](https://discord.gg/6pRc9f6g6S)

## Delivered and maintained by 
<img width="350" height="350" alt="gsi-logo" src="https://github.com/user-attachments/assets/e7210566-7997-4d82-845e-48f249d439a0" />
