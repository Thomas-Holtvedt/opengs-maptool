from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Literal
if TYPE_CHECKING:
    from opengs_maptool.logic.map_tool_protocol import MapToolProtocol

import json
from PIL import Image
from PyQt6.QtWidgets import QFileDialog
import csv


def export_image(parent_layout, image: Image.Image, text: str) -> None:
    if image:
        try:
            path, _ = QFileDialog.getSaveFileName(
                parent_layout, text, "", "PNG Files (*.png)")
            if not path:
                return
            if not path.lower().endswith(".png"):
                path += ".png"
            image.save(path)

        except Exception as error:
            print(f"Error saving image: {error}")


def export_territory_definitions(map_tool: MapToolProtocol) -> None:
    _, territory_data = map_tool.get_territory_pmap_and_data()
    if not territory_data:
        print("No territory data to export.")
        return

    path, fmt = _pick_file(map_tool, "Export Territory Definitions")
    if not path:
        return
    export_territory_definitions_to_path(territory_data, path, fmt)

def export_territory_definitions_to_path(territory_data: list[dict], path: str | Path, fmt: str) -> None:
    if fmt == "json":
        data = {}
        for d in territory_data:
            data[d["territory_id"]] = {
                "territory_type": d["territory_type"],
                "R": d["R"], "G": d["G"], "B": d["B"],
                "x": round(d["x"], 2), "y": round(d["y"], 2),
            }
        _write_json(path, data)
    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(["id", "territory_type", "R", "G", "B", "x", "y"])
            for d in territory_data:
                w.writerow([d["territory_id"], d["territory_type"],
                            d["R"], d["G"], d["B"],
                            round(d["x"], 2), round(d["y"], 2)])


def export_territory_history(map_tool: MapToolProtocol) -> None:
    _, territory_data = map_tool.get_territory_pmap_and_data()
    if not territory_data:
        print("No territory data to export.")
        return
    
    path, fmt = _pick_file(map_tool, "Export Territory History")
    if not path:
        return
    export_territory_history_to_path(territory_data, path, fmt)

def export_territory_history_to_path(territory_data: list[dict], path: str | Path, fmt: str) -> None:
    if fmt == "json":
        data = {}
        for d in territory_data:
            data[d["territory_id"]] = {
                "provinces": d.get("province_ids", []),
            }
        _write_json(path, data)
    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w: csv.Writer = csv.writer(f, delimiter=';')
            w.writerow(["id", "provinces"])
            for d in territory_data:
                provinces: str = ",".join(d.get("province_ids", []))
                w.writerow([d["territory_id"], provinces])


def export_province_definitions(map_tool: MapToolProtocol) -> None:
    province_data = map_tool.get_province_data()
    if not province_data:
        print("No province data to export.")
        return

    path, fmt = _pick_file(map_tool, "Export Province Definitions")
    if not path:
        return
    export_province_definitions_to_path(province_data, path, fmt)

def export_province_definitions_to_path(province_data: list[dict], path: str | Path, fmt: str) -> None:
    has_terrain = any("province_terrain" in d for d in province_data)

    if fmt == "json":
        data = {}
        for d in province_data:
            entry = {
                "province_type": d["province_type"],
                "R": d["R"], "G": d["G"], "B": d["B"],
                "x": round(d["x"], 2), "y": round(d["y"], 2),
            }
            if has_terrain:
                entry["province_terrain"] = d.get("province_terrain", "unknown")
            data[d["province_id"]] = entry
        _write_json(path, data)
    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=';')
            header = ["id", "province_type", "R", "G", "B", "x", "y"]
            if has_terrain:
                header.append("province_terrain")
            w.writerow(header)
            for d in province_data:
                row = [d["province_id"], d["province_type"],
                       d["R"], d["G"], d["B"],
                       round(d["x"], 2), round(d["y"], 2)]
                if has_terrain:
                    row.append(d.get("province_terrain", "unknown"))
                w.writerow(row)



def _pick_file(parent, title: str) -> tuple[None, None] | tuple[str, Literal["json", "csv"]]:
    """Open save dialog with JSON/CSV filter. Returns (path, format) or (None, None)."""
    path, selected_filter = QFileDialog.getSaveFileName(
        parent, title, "", "JSON Files (*.json);;CSV Files (*.csv)")
    if not path:
        return None, None

    # Determine format from extension, fall back to selected filter
    if path.lower().endswith(".json"):
        fmt = "json"
    elif path.lower().endswith(".csv"):
        fmt = "csv"
    elif "json" in selected_filter.lower():
        fmt = "json"
        path += ".json"
    else:
        fmt = "csv"
        path += ".csv"

    return path, fmt


def _write_json(path: str | Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
