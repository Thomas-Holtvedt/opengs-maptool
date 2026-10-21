from __future__ import annotations
from typing import TYPE_CHECKING
import time

if TYPE_CHECKING:
    from opengs_maptool.context import ApplicationContext

from opengs_maptool.controllers.task_controller import ThreadTaskSlot
from opengs_maptool.services.command_core import register_command
from opengs_maptool.models.command_response import CommandResponse
from opengs_maptool.models.message import MessageType

@register_command("wait.tasks.completed", args=[])
def cmd_wait_tasks_completed(context: ApplicationContext) -> CommandResponse:
    """Waits until all background tasks are completed."""
    start_time = time.time()
    considered_slots = list(ThreadTaskSlot)
    considered_slots.remove(ThreadTaskSlot.execute_command)

    count = None
    def update_occupied_count():
        nonlocal count
        occupied = [context.task_controller.is_thread_slot_occupied(slot) for slot in considered_slots]
        count = sum(occupied)

    update_occupied_count()
    while count > 0: # This is in a background thread, so it's safe to sleep
        time.sleep(0.1)
        update_occupied_count()
    finish_time = time.time()

    return CommandResponse(
        f"Waited {finish_time - start_time:.2f} seconds for background tasks to complete",
        MessageType.NORMAL
    )
