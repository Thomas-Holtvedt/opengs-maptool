import opengs_maptool.config as config
from opengs_maptool.models.project import Project

def get_land_informations(project: Project) -> tuple[float, float, float]:
    if project.land_image is None:
        return (0.0, 0.0, 0.0)
    
    image = project.land_image.convert("RGB")

    width, height = image.size
    total_pixels = width * height

    colors = image.getcolors(total_pixels)
    color_dict = {color: count for count, color in colors}

    ocean_color_count = color_dict.get(project.ocean_color, 0)
    lake_color_count = color_dict.get(project.lake_color, 0)

    ocean_percentage = (ocean_color_count / total_pixels) * 100
    lake_percentage = (lake_color_count / total_pixels) * 100
    land_percentage = 100.0 - (ocean_percentage + lake_percentage)

    return (
        land_percentage,
        ocean_percentage,
        lake_percentage
    )
