from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from opengs_maptool.context import ApplicationContext

from opengs_maptool.logic.import_module import load_input_image, ImageLoadingError, ImageLoadingConfigurationError
from opengs_maptool.simple_types import TabName

class ImportService:
    """Service for importing images into the project without UI or console-specific logic."""

    def __init__(self, context: ApplicationContext):
        self._context = context

    def import_land_image(self, path: str) -> None | ImageLoadingError | ImageLoadingConfigurationError:
        try:
            image = load_input_image(path, image_channel_mode="RGBA")
            self._context.project_controller.set_land_image(image)
            self._context.project_controller.set_density_image(None) # I didn't think of this, i only kept it.
        except (ImageLoadingError, ImageLoadingConfigurationError) as error:
            return error

    def import_boundary_image(self, path: str) -> None | ImageLoadingError | ImageLoadingConfigurationError:
        try:
            image = load_input_image(path, image_channel_mode="RGB")
            self._context.project_controller.set_boundary_image(image)
        except (ImageLoadingError, ImageLoadingConfigurationError) as error:
            return error

    def import_density_image(self, path: str) -> None | ImageLoadingError | ImageLoadingConfigurationError:
        try:
            image = load_input_image(path, image_channel_mode="L")
            self._context.project_controller.set_density_image(image)
        except (ImageLoadingError, ImageLoadingConfigurationError) as error:
            return error

    def import_terrain_image(self, path: str) -> None | ImageLoadingError | ImageLoadingConfigurationError:
        try:
            image = load_input_image(path, image_channel_mode="RGB")
            self._context.project_controller.set_terrain_image(image)
        except (ImageLoadingError, ImageLoadingConfigurationError) as error:
            return error
