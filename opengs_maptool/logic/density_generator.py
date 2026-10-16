from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from opengs_maptool.context import ApplicationContext

import opengs_maptool.config as config
import numpy as np
from PIL import Image
from opengs_maptool.controllers.progress_controller import ProgressController


def normalize_density_image(task_ctx: ApplicationContext, progress_controller: ProgressController)-> None:
    with progress_controller.execute_as_only_phase():
        project = task_ctx.project
        if not project.can_density_image_be_generated(task_ctx):
            return

        w, h = project.land_image.size
        density_image = Image.new("L", (w, h), config.DEFAULT_DENSITY_GREY)

        task_ctx.project_controller.set_density_image(density_image)

def equator_density_image(task_ctx: ApplicationContext, progress_controller: ProgressController) -> None:
    phase1 = progress_controller.add_phase(step_weight=1, msg="Calculating density values")
    phase2 = progress_controller.add_phase(step_weight=1, msg="Assigning pixel values")
    phase3 = progress_controller.add_phase(step_weight=1, msg="Creating density image")

    with progress_controller.execute_phase(phase1):
        project = task_ctx.project
        if not project.can_density_image_be_generated(task_ctx):
            return

        w, h = project.land_image.size

        # Black (0) at equator (middle row), white (255) at top/bottom poles
        rows = np.linspace(0, 1, h)
        gradient = np.abs(rows - 0.5) * 2.0  # 0 at center, 1 at edges

    with progress_controller.execute_phase(phase2):
        pixel_values = (gradient * 255).astype(np.uint8)
        arr = np.tile(pixel_values[:, np.newaxis], (1, w))

    with progress_controller.execute_phase(phase3):
        density_image = Image.fromarray(arr, mode="L")
        task_ctx.project_controller.set_density_image(density_image)

# TODO: Move this function, it doesn't belong in this file
# -> if done, remove progress_controller argument
def remove_density_image(task_ctx: ApplicationContext, progress_controller: ProgressController) -> None:
    # This is instant, no need for a progress bar
    project = task_ctx.project
    if not project.can_density_image_be_removed(task_ctx):
        return

    task_ctx.project_controller.set_density_image(None)
