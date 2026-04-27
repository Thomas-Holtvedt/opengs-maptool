# Main Window
TITLE = "OpenGS - Map Tool"
WINDOW_SIZE_WIDTH = 1100
WINDOW_SIZE_HEIGHT = 950
VERSION = "0.3.5"

# Land Province slider
LAND_PROVINCES_MIN = 100
LAND_PROVINCES_MAX = 100000
LAND_PROVINCES_DEFAULT = 3000
LAND_PROVINCES_TICK = 200
LAND_PROVINCES_STEP = 100

# Ocean Province slider
OCEAN_PROVINCES_MIN = 10
OCEAN_PROVINCES_MAX = 10000
OCEAN_PROVINCES_DEFAULT = 300
OCEAN_PROVINCES_TICK = 20
OCEAN_PROVINCES_STEP = 10

# Land Territory slider
LAND_TERRITORIES_MIN = 100
LAND_TERRITORIES_MAX = 10000
LAND_TERRITORIES_DEFAULT = 3000
LAND_TERRITORIES_TICK = 200
LAND_TERRITORIES_STEP = 100

# Ocean Territory slider
OCEAN_TERRITORIES_MIN = 10
OCEAN_TERRITORIES_MAX = 1000
OCEAN_TERRITORIES_DEFAULT = 300
OCEAN_TERRITORIES_TICK = 20
OCEAN_TERRITORIES_STEP = 10

# Land Map Color Code
OCEAN_COLOR = (5, 20, 18)  # RGB
LAKE_COLOR = (0, 255, 0)

# Boundary Map Color Code
BOUNDARY_COLOR = (0, 0, 0)

# Image Import
MAX_IMAGE_PIXELS = 300000000

# Generation algorithm
LLOYD_ITERATIONS = 4
JAGGED_BORDER_AMPLITUDE = 0.12  # fraction of avg seed spacing used as noise

# Number Series
PROVINCE_ID_PREFIX = "PRV"
PROVINCE_ID_START = 1
PROVINCE_ID_END = 999999
TERRITORY_ID_PREFIX = "TRT"
TERRITORY_ID_START = 1
TERRITORY_ID_END = 999999

# Density Image
DEFAULT_DENSITY_GREY = 128
DENSITY_STRENGTH_DEFAULT = 20  # Slider value (divided by 10 = 2.0)
DENSITY_STRENGTH_MIN = 0
DENSITY_STRENGTH_MAX = 50
DENSITY_STRENGTH_TICK = 5
DENSITY_STRENGTH_STEP = 1

# Terrain Types — color: (R, G, B)
LAND_TERRAIN_TYPES = {
    "forest":   (89, 199, 85),
    "hills":    (248, 255, 153),
    "mountain": (157, 192, 208),
    "plains":   (255, 129, 66),
    "urban":    (120, 120, 120),
    "jungle":   (127, 191, 0),
    "marsh":    (76, 96, 35),
    "desert":   (255, 127, 0),
}

NAVAL_TERRAIN_TYPES = {
    "deep_ocean":   (2, 38, 150),
    "shallow_sea":  (56, 118, 217),
    "fjords":       (75, 162, 198),
}

LAKE_TERRAIN_TYPES = {
    "lakes": (58, 91, 255),
}

# All terrain types combined (for color lookup)
TERRAIN_TYPES = {**LAND_TERRAIN_TYPES, **NAVAL_TERRAIN_TYPES, **LAKE_TERRAIN_TYPES}

# Default terrain per province type (used when no terrain image or no color match)
DEFAULT_TERRAIN_LAND = "plains"
DEFAULT_TERRAIN_OCEAN = "deep_ocean"
DEFAULT_TERRAIN_LAKE = "lakes"
