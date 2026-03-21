<img width="350" height="350" alt="ogs-mt-logo" src="https://github.com/user-attachments/assets/d03854c8-c2e1-468f-9f8a-269f498d169c" />

# Open Grand Strategy - Map Tool 
The OpenGS Map Tool is a specialized utility designed to streamline the creation of map data for use in grand strategy games. 
Province and territory maps form the backbone of these games, defining the geographical regions that players interact with.

## Features
- Generate and Export province maps
- Generate and Export province data
- Generate and Export territory maps
- Generate and Export territory data
- Density image support for controlling province/territory distribution
- Lake support — lakes are automatically detected and become individual provinces
- Exclude ocean from density influence per generation step
- Jagged borders — optional natural-looking borders for land and ocean regions
- Terrain system — import a terrain image to assign terrain types to provinces

## Showcase
Output territory Map:
![example](opengs_maptool/examples/output/territories.png)
Output Province Map:
![example2](opengs_maptool/examples/output/provinces.png)


## How to install
### Option 1 (Windows only):
1. "Releases" section in Github
2. Download and unpack "ogs_maptool.zip"
3. Run the Executable

### Option 2 (recommended):
1. [Download Python](https://www.python.org/downloads/) if not installed (Version 3.12 and up)
2. Clone the repository
3. Download the necessary libraries and install by running `pip install .` in your terminal, 
inside the project directory

## How to use the tool

### Launching the User Interface (Only works for Option 2)
You can start the OpenGS Map Tool with its graphical interface using the following from any directory(except if you use a venv):

```sh
opengs-maptool-main-gui
```

Or, if running from source:

```sh
python -m opengs_maptool.main --mode gui
```

This will open the main window, allowing you to use all features through an interactive interface.

---

### Python Interface and `main_terminal` Mode (Only works for Option 2)

The OpenGS Map Tool can also be used programmatically via its Python interface, or run in batch mode using the `main_terminal` mode. This is useful for automation, scripting, or running example workflows without the graphical interface.

You can import and use the main logic in your own Python scripts. The core class is `MainProgram` in `opengs_maptool.logic.main_program`.

Example:

```python
from opengs_maptool.logic.main_program import MainProgram
import opengs_maptool.config as config
from pathlib import Path

input_dir = Path("opengs_maptool/examples/input/")
output_dir = Path("opengs_maptool/examples/output/")
mp = MainProgram()
mp.load_land_image(input_dir / "land.png")
mp.load_boundary_image(input_dir / "bound.png")
mp.load_density_image(input_dir / "density.png")
mp.load_terrain_image(input_dir / "terrain.png")

# Set parameters and generate territories
mp.set_territory_params(
	land_density=config.LAND_TERRITORIES_MIN,
	ocean_density=config.OCEAN_TERRITORIES_MIN,
	density_strength=config.DENSITY_STRENGTH_DEFAULT / 10.0,
	jagged_land_borders=False,
	jagged_ocean_borders=False
)
mp.generate_territories()
mp.export_territory_image(output_dir / "territories.png")

# Set parameters and generate provinces
mp.set_province_params(
	land_density=config.LAND_PROVINCES_DEFAULT,
	ocean_density=config.OCEAN_PROVINCES_DEFAULT,
	density_strength=config.DENSITY_STRENGTH_DEFAULT / 10.0,
	jagged_land_borders=False,
	jagged_ocean_borders=False
)
mp.generate_provinces()
mp.export_province_image(output_dir / "provinces.png")
```

### main_terminal Mode (Only works for Option 2)
You can run the tool in batch mode from the command line, which will process example input images and export all output files automatically. This is useful for testing or automation.

**Command:**

```sh
python -m opengs_maptool.main --mode main_terminal
```

This will:
- Load example images from `opengs_maptool/examples/input/`
- Generate territories and provinces
- Export all output files to `opengs_maptool/examples/output/`

You can also use the installed script (if installed via pip):

```sh
opengs-maptool-main-terminal
```


### Land Image
The first tab takes an image that specifies the ocean and lake areas of the map.
- **Ocean** must be RGB color (5, 20, 18)
- **Lakes** must be RGB color (0, 255, 0)
- Everything else is considered land

See examples in the folder "opengs_maptool/examples/input".

### Boundary Image
The second tab defines the bounds that the provinces and territories need to adhere to.
Typical use would be borders for countries, states or other administrative units.
The boundary borders must be pure black, RGB (0, 0, 0), everything else will be ignored.

### Density Image
The third tab allows you to import a density image that controls how provinces and territories are distributed.
Darker areas attract more seeds, resulting in smaller and denser regions. A normalize preset and an equator distribution preset are available.

The "Exclude Ocean" checkboxes on this tab let you ignore the density image for ocean regions during territory and/or province generation.

### Terrain Image
The fourth tab allows you to import a terrain image that assigns terrain types to provinces after generation.
Each pixel color maps to a specific terrain type. The terrain is sampled at each province's center point and constrained by province type (land provinces only receive land terrains, ocean provinces only receive naval terrains, etc.).

**Land terrains** and their RGB colors:
| Terrain  | RGB |
|----------|-----|
| forest   | (89, 199, 85) |
| hills    | (248, 255, 153) |
| mountain | (157, 192, 208) |
| plains   | (255, 129, 66) |
| urban    | (120, 120, 120) |
| jungle   | (127, 191, 0) |
| marsh    | (76, 96, 35) |
| desert   | (255, 127, 0) |

**Naval terrains:**
| Terrain     | RGB |
|-------------|-----|
| deep_ocean  | (2, 38, 150) |
| shallow_sea | (56, 118, 217) |
| fjords      | (75, 162, 198) |

**Lake terrain:**
| Terrain | RGB |
|---------|-----|
| lakes   | (58, 91, 255) |

If no terrain image is provided, defaults are used: plains for land, deep_ocean for ocean, and lakes for lake provinces.

### Territory Image
The fifth tab generates the territory map, based on the input in tab 1 and 2.
NB! You dont need both inputs, but you need at least one.
Ex. A map without any ocean does not need to have input in tab 1, but then there must be input in tab 2, and vice versa.
Both input images must have the same dimensions/size for a good result.

Use the sliders to adjust the number of territories on land and ocean.
The density strength slider controls how strongly the density image influences seed placement.

Check "Jagged Land Borders" or "Jagged Ocean Borders" to produce natural-looking, irregular borders instead of straight Voronoi edges.

Territory map and the file containing territory information (id, rgb, type, coordinates) can be exported after generation.

### Province Image
The sixth tab generates the province map, based on the generated territories.
NB! You need to generate territories before you can generate provinces.

Use the sliders to adjust the number of provinces on land and ocean.
Lakes are automatically detected and each connected lake region becomes its own province, assigned to the overlapping territory.

Check "Jagged Land Borders" or "Jagged Ocean Borders" to produce natural-looking, irregular borders instead of straight Voronoi edges.

Province map and the file containing province information (id, rgb, type, coordinates, terrain) can be exported after generation. The terrain field is included when a terrain image has been imported.
Territory history files (defining the belonging provinces per territory) can be exported after generation.

## Contributions
Contributions can come in many forms and all are appreciated:
- Feedback
- Code improvements
- Added functionality

## Discord 
Follow and/or support the project on [OpenGS Discord Server](https://discord.gg/6pRc9f6g6S)

## Delivered and maintained by 
<img width="350" height="350" alt="gsi-logo" src="https://github.com/user-attachments/assets/e7210566-7997-4d82-845e-48f249d439a0" />
