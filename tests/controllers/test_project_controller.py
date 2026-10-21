from types import SimpleNamespace

import pytest

from opengs_maptool.controllers.project_controller import ProjectAttribute, ProjectController
from opengs_maptool.models.project import Project


@pytest.fixture
def controller():
    context = SimpleNamespace(project=Project())
    service = SimpleNamespace()
    return ProjectController(context, service)


def _changed_value(value):
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value + 1
    if isinstance(value, tuple):
        return tuple((channel + 1) % 256 for channel in value)
    if isinstance(value, str):
        return f"{value} updated"
    if isinstance(value, list):
        return [object()]
    return object()


@pytest.mark.parametrize("attribute", list(ProjectAttribute))
def test_attribute_setter_updates_project_marks_it_modified_and_emits_attribute(
    controller, attribute
):
    original = getattr(controller.get_project(), attribute.name)
    changed = _changed_value(original)
    emitted = []
    controller.project_was_modified.connect(emitted.append)

    setter_name = (
        f"set_project_{attribute.name}"
        if attribute.name in {"name", "description", "author"}
        else f"set_{attribute.name}"
    )
    getattr(controller, setter_name)(changed)

    assert getattr(controller.get_project(), attribute.name) == changed
    assert controller.is_project_modified()
    assert emitted == [attribute]


def test_metadata_and_color_setters_ignore_unchanged_values(controller):
    project = controller.get_project()
    emitted = []
    controller.project_was_modified.connect(emitted.append)

    controller.set_project_name(project.name)
    controller.set_project_description(project.description)
    controller.set_project_author(project.author)
    controller.set_land_color(project.land_color)

    assert emitted == []
    assert not controller.is_project_modified()


def test_create_project_emits_refresh_for_every_attribute(controller):
    created = Project(name="Created")
    controller._project_service.create = lambda: created
    emitted = []
    controller.project_was_modified.connect(emitted.append)

    result = controller.create_project()

    assert result is created
    assert controller.get_project() is created
    assert emitted == list(ProjectAttribute)
    assert controller.is_project_modified()


def test_load_project_emits_refresh_without_marking_project_modified(controller):
    loaded = Project(name="Loaded")
    controller._context.project.modified = True
    controller._project_service.load = lambda path: loaded
    emitted = []
    controller.project_was_modified.connect(emitted.append)

    result = controller.load_project("project.gsmap")

    assert result is loaded
    assert controller.get_project() is loaded
    assert emitted == list(ProjectAttribute)
    assert not controller.is_project_modified()