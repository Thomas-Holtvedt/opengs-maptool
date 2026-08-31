from opengs_maptool.models.project import Project

def get_land_informations(project: Project) -> tuple[float, float, float]:
    if project.land_image is None:
        return (0.0, 0.0, 0.0)
    
    image = project.land_image.convert("RGB")

    width, height = image.size
    total_pixels = width * height

    colors = image.getcolors(total_pixels)
    color_dict = {color: count for count, color in colors}

    land_color_count = color_dict.get(project.land_color, 0)
    ocean_color_count = color_dict.get(project.ocean_color, 0)
    lake_color_count = color_dict.get(project.lake_color, 0)

    # Measured per configured color rather than inferred, so pixels that match
    # none of the three (anti-aliased edges, stray colors) show up as a
    # shortfall instead of being silently folded into the land share.
    land_percentage = (land_color_count / total_pixels) * 100
    ocean_percentage = (ocean_color_count / total_pixels) * 100
    lake_percentage = (lake_color_count / total_pixels) * 100

    return (
        land_percentage,
        ocean_percentage,
        lake_percentage
    )
