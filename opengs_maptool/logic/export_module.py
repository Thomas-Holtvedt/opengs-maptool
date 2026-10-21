from __future__ import annotations
from PIL import Image
import json
import csv
import cv2
import svgwrite
import numpy as np
import yaml
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Any
from enum import Enum
from opengs_maptool.models.project import Project
import opengs_maptool.logic.datastructure as ds
from opengs_maptool.services.logging_service import LOGGING_SERVICE


def export_image(
        path: str, image: Image.Image,
        data: list[ds.RegionMetadata] | None = None,
        raise_on_error: bool = False,
    ) -> None:
    """Export an image to the specified file path."""
    if not image or not path:
        return

    try:
        ext = path.lower().rsplit('.', 1)[-1]
        if ext == "svg":
            if data is not None:
                try:
                    _export_svg(path, image, data)
                except Exception as error:
                    LOGGING_SERVICE.loggers.export.send(f"Error exporting SVG image: {error}")
                    if raise_on_error:
                        raise
            else:
                message = f"Data is required for SVG image export, but none is provided for {path}"
                LOGGING_SERVICE.loggers.export.send(message)
                if raise_on_error:
                    raise ValueError(message)
        else:
            # Remove the alpha channel for JPEG image export
            if ext in ("jpg", "jpeg"):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3]) 
                """ TODO: fix this error (happens on jpg export of province image)
                background.paste(image, mask=image.split()[3])
                                                ~~~~~~~~~~~~~^^^
                IndexError: tuple index out of range
                """
                image = background
            
            image.save(path)
        
    except Exception as error:
        LOGGING_SERVICE.loggers.export.send(f"Error saving image: {error}")
        if raise_on_error:
            raise



FORMAT_ALIASES = {
    "yml": "yaml"
}

class ExportFormat(Enum):
    JSON = "json"
    CSV = "csv"
    YAML = "yaml"
    XML = "xml"

    @classmethod
    def get_by_path(cls, path: str, raise_on_unknown: bool = False) -> ExportFormat:
        """Return the export format corresponding to the file extension."""
        suffix = path.rpartition(".")[2].lower()
        if suffix in FORMAT_ALIASES:
            suffix = FORMAT_ALIASES[suffix]

        try:
            return cls(suffix) # use the Enum constructor to get the corresponding enum
        except ValueError as error:
            if raise_on_unknown:
                raise ValueError(f"Please specify a valid export format (JSON, CSV, YAML, XML), invalid file extension: {path}") from error
            return cls.JSON  # default to JSON if unknown extension


def export_territory_definitions(project: Project, path: str, fmt: ExportFormat) -> None:
    """Export territory definitions to the specified path in the given format."""
    territory_data = project.territory_data
    if not territory_data:
        LOGGING_SERVICE.loggers.export.send("No territory data to export.")
        return

    data: dict[str, dict[str, Any]] = {}
    for d in territory_data:
        data[d.territory_id] = d.serialize_territory_json()

    if fmt in (ExportFormat.JSON, ExportFormat.YAML, ExportFormat.XML):
        if fmt == ExportFormat.JSON:
            _write_json(path, data)
        elif fmt == ExportFormat.YAML:
            _write_yaml(path, data)
        elif fmt == ExportFormat.XML:
            root = ET.Element("territories")

            for territory_id, info in data.items():
                territory_element = ET.SubElement(root, "territory")
                territory_element.set("id", str(territory_id))

                for key, value in info.items():
                    element = ET.SubElement(territory_element, key)
                    element.text = str(value)

            rough_xml = ET.tostring(root, encoding="unicode")
            pretty_xml = minidom.parseString(rough_xml).toprettyxml(indent="    ")

            with open(path, "w", encoding="utf-8") as f:
                f.write(pretty_xml)

    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=';')
            keys = ds.RegionMetadata.TERRITORY_JSON_KEYS
            keys = ("id", *keys)

            w.writerow(keys)
            for territory_id, info in data.items():
                w.writerow(_get_csv_row_values(keys, info, id_value=territory_id, id_key="id"))


def export_territory_history(project: Project, path: str, fmt: ExportFormat) -> None:
    """Export territory history to the specified path in the given format."""
    territory_data = project.territory_data
    if not territory_data:
        LOGGING_SERVICE.loggers.export.send("No territory data to export.")
        return

    data: dict[str, dict[str, list[str]]] = {}
    for d in territory_data:
        data[d.territory_id] = {
            "provinces": d.province_ids or [],
        }

    if fmt in (ExportFormat.JSON, ExportFormat.YAML, ExportFormat.XML):
        if fmt == ExportFormat.JSON:
            _write_json(path, data)
        elif fmt == ExportFormat.YAML:
            _write_yaml(path, data)
        elif fmt == ExportFormat.XML:
            root = ET.Element("territories")

            for territory_id, info in data.items():
                territory_element = ET.SubElement(root, "territory")
                territory_element.set("id", str(territory_id))

                provinces_element = ET.SubElement(territory_element, "provinces")

                for province_id in info.get("provinces", []):
                    province_element = ET.SubElement(provinces_element, "province")
                    province_element.text = str(province_id)

            rough_xml = ET.tostring(root, encoding="unicode")
            pretty_xml = minidom.parseString(rough_xml).toprettyxml(indent="    ")

            with open(path, "w", encoding="utf-8") as f:
                f.write(pretty_xml)

    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(["id", "provinces"])
            for territory_id, info in data.items():
                provinces = ",".join(info.get("provinces", []))
                w.writerow([territory_id, provinces])


def export_province_definitions(project: Project, path: str, fmt: ExportFormat) -> None:
    """Export province definitions to the specified path in the given format."""
    province_data = project.province_data
    if not province_data:
        LOGGING_SERVICE.loggers.export.send("No province data to export.")
        return

    has_terrain = any((d.province_terrain is not None) for d in province_data)

    data: dict[str, dict[str, Any]] = {}
    for d in province_data:
        data[d.province_id] = d.serialize_province_json(include_terrain=has_terrain)

    if fmt in (ExportFormat.JSON, ExportFormat.YAML, ExportFormat.XML):
        if fmt == ExportFormat.JSON:
            _write_json(path, data)
        elif fmt == ExportFormat.YAML:
            _write_yaml(path, data)
        elif fmt == ExportFormat.XML:
            root = ET.Element("provinces")

            for province_id, info in data.items():
                province_element = ET.SubElement(root, "province")
                province_element.set("id", str(province_id))

                for key, value in info.items():
                    element = ET.SubElement(province_element, key)
                    element.text = str(value)

            rough_xml = ET.tostring(root, encoding="unicode")
            pretty_xml = minidom.parseString(rough_xml).toprettyxml(indent="    ")

            with open(path, "w", encoding="utf-8") as f:
                f.write(pretty_xml)

    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=';')
            keys = ds.RegionMetadata.PROVINCE_JSON_KEYS_WITH_TERRAIN if has_terrain else ds.RegionMetadata.PROVINCE_JSON_KEYS_WITHOUT_TERRAIN
            keys = ("id", *keys)
            w.writerow(keys)

            for province_id, info in data.items():
                w.writerow(_get_csv_row_values(keys, info, id_value=province_id, id_key="id"))

def _get_csv_row_values(keys: tuple[str, ...], data: dict[str, Any], id_value: Any, id_key: str = "id") -> list[Any]:
    values = []
    for key in keys:
        if key == id_key:
            values.append(id_value)
        else:
            values.append(data.get(key))
    return values

def _write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def _write_yaml(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False)

def _export_svg(path: str, source_image: Image.Image, data: list[ds.RegionMetadata]) -> None:
    """Export an image as an SVG file. Possibly raises exceptions if the export fails."""
    w, h = source_image.size
    drawing = svgwrite.Drawing(path, size=(w, h))

    for region in data:
        # OpenCV uses BGR format
        image = cv2.cvtColor(np.array(source_image), cv2.COLOR_RGB2BGR)
        target_color = np.array([region.B, region.G, region.R], dtype=np.uint8)

        mask = cv2.inRange(image, target_color, target_color)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            points = [(float(pt[0][0]), float(pt[0][1])) for pt in contour]

            color_hex = f"#{region.R:02x}{region.G:02x}{region.B:02x}"
            
            region_id = region.territory_id
            if region.region_level == ds.RegionLevel.PROVINCE:
                region_id = region.province_id

            drawing.add(drawing.polygon(points, fill=color_hex, stroke="none", id=region_id))

    drawing.save()
